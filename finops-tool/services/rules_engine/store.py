import json
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.common.models import Finding


@dataclass(frozen=True)
class AccountScanConfig:
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    name: str
    role_arn: str
    external_id: str


def set_tenant_context(db: Session, tenant_id: uuid.UUID | str) -> None:
    """Arm RLS for the current transaction only (set_config(..., true))."""
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def list_scan_targets(
    db: Session, tenant_name: str | None = None, account_name: str | None = None
) -> list[AccountScanConfig]:
    """AWS accounts to scan, walked tenant by tenant.

    aws_accounts is RLS-protected, so there is no cross-tenant query here:
    each tenant's accounts are read under that tenant's own context.
    Explicitly named accounts are returned even if scan_enabled is false.
    """
    if tenant_name is not None:
        tenants = db.execute(
            text("SELECT id, name FROM tenants WHERE name = :name"), {"name": tenant_name}
        ).all()
        if not tenants:
            raise LookupError(f"No tenant named {tenant_name!r} — see `python -m scripts.admin -h`")
    else:
        tenants = db.execute(text("SELECT id, name FROM tenants ORDER BY name")).all()

    targets: list[AccountScanConfig] = []
    for tenant_id, t_name in tenants:
        set_tenant_context(db, tenant_id)
        if account_name is not None:
            rows = db.execute(
                text(
                    "SELECT id, name, role_arn, external_id FROM aws_accounts "
                    "WHERE tenant_id = :tenant_id AND name = :name"
                ),
                {"tenant_id": str(tenant_id), "name": account_name},
            ).all()
        else:
            rows = db.execute(
                text(
                    "SELECT id, name, role_arn, external_id FROM aws_accounts "
                    "WHERE tenant_id = :tenant_id AND scan_enabled ORDER BY name"
                ),
                {"tenant_id": str(tenant_id)},
            ).all()
        targets.extend(AccountScanConfig(r[0], tenant_id, t_name, *r[1:]) for r in rows)
        db.commit()  # ends the transaction, and with it the tenant context

    if account_name is not None and not targets:
        raise LookupError(f"No AWS account named {account_name!r} in tenant {tenant_name!r}")
    return targets


def get_account(db: Session, tenant_id: str, account_id: str) -> AccountScanConfig | None:
    """One account of one tenant; the caller already armed the tenant context."""
    row = db.execute(
        text(
            "SELECT a.id, a.tenant_id, t.name, a.name, a.role_arn, a.external_id "
            "FROM aws_accounts a JOIN tenants t ON t.id = a.tenant_id "
            "WHERE a.id = :id AND a.tenant_id = :tenant_id"
        ),
        {"id": account_id, "tenant_id": tenant_id},
    ).first()
    return AccountScanConfig(*row) if row else None


def record_scan_result(db: Session, account: AccountScanConfig, error: str | None) -> None:
    set_tenant_context(db, account.tenant_id)
    db.execute(
        text(
            "UPDATE aws_accounts SET last_scan_at = now(), last_scan_status = :status, "
            "last_scan_error = :error WHERE id = :id AND tenant_id = :tenant_id"
        ),
        {
            "status": "failed" if error else "ok",
            "error": error,
            "id": str(account.id),
            "tenant_id": str(account.tenant_id),
        },
    )
    db.commit()


def replace_findings(
    db: Session, tenant_id: uuid.UUID, aws_account_id: uuid.UUID, findings: list[Finding]
) -> int:
    """Replace one AWS account's findings with the latest run's results.

    Delete-and-insert keeps the table an exact mirror of the last scan —
    resolved findings disappear instead of lingering as stale rows. History
    will come later as a separate scan_runs table, not by keeping old rows here.
    Scoped per account so scanning one account never wipes another's findings.
    """
    set_tenant_context(db, tenant_id)
    params = {"tenant_id": str(tenant_id), "aws_account_id": str(aws_account_id)}
    db.execute(
        text("DELETE FROM findings WHERE tenant_id = :tenant_id AND aws_account_id = :aws_account_id"),
        params,
    )
    for f in findings:
        db.execute(
            text(
                """
                INSERT INTO findings
                    (tenant_id, aws_account_id, resource_id, rule_id, category,
                     monthly_savings_usd, remediation_effort, risk, evidence,
                     remediation_action, detected_at)
                VALUES
                    (:tenant_id, :aws_account_id, :resource_id, :rule_id, :category,
                     :monthly_savings_usd, :remediation_effort, :risk, :evidence,
                     :remediation_action, :detected_at)
                """
            ),
            {
                **params,
                "resource_id": f.resource_id,
                "rule_id": f.rule_id,
                "category": f.category,
                "monthly_savings_usd": f.monthly_savings_usd,
                "remediation_effort": f.remediation_effort.value,
                "risk": f.risk.value,
                "evidence": json.dumps(f.evidence, default=str),
                "remediation_action": f.remediation_action,
                "detected_at": f.detected_at,
            },
        )
    db.commit()
    return len(findings)
