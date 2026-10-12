from fastapi import FastAPI
from sqlalchemy import text

from services.api import onboarding, session
from services.api.auth import CurrentUser
from services.api.db import SessionLocal
from services.api.tenancy import resolve_tenant as _resolve_tenant

app = FastAPI(title="FinOps Tool API")
app.include_router(session.router)
app.include_router(onboarding.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/findings")
def list_findings(user: CurrentUser) -> list[dict]:
    db = SessionLocal()
    try:
        tenant_id = _resolve_tenant(db, user.user_id)
        rows = db.execute(
            text(
                "SELECT f.*, a.name AS aws_account_name, "
                "split_part(a.role_arn, ':', 5) AS aws_account_number "
                "FROM findings f JOIN aws_accounts a "
                "ON a.id = f.aws_account_id AND a.tenant_id = f.tenant_id "
                "WHERE f.tenant_id = :tenant_id "
                "ORDER BY f.monthly_savings_usd DESC"
            ),
            {"tenant_id": str(tenant_id)},
        ).mappings().all()
        findings = []
        for row in rows:
            item = dict(row)
            # NUMERIC comes back as Decimal, which pydantic v2 serializes as a
            # JSON string; the frontend contract (web/lib/api.ts) is a number.
            item["monthly_savings_usd"] = float(item["monthly_savings_usd"])
            findings.append(item)
        return findings
    finally:
        db.close()


@app.get("/summary")
def findings_summary(user: CurrentUser) -> dict:
    """Tenant-wide aggregates for the dashboard KPI row.

    Casting to float8/int in SQL keeps Decimal out of the JSON layer
    (pydantic v2 would serialize it as a string).
    """
    db = SessionLocal()
    try:
        tenant_id = _resolve_tenant(db, user.user_id)
        totals = db.execute(
            text(
                "SELECT count(*)::int AS findings_count, "
                "coalesce(sum(monthly_savings_usd), 0)::float8 AS total_monthly_savings_usd "
                "FROM findings WHERE tenant_id = :tenant_id"
            ),
            {"tenant_id": tenant_id},
        ).mappings().one()
        by_rule = db.execute(
            text(
                "SELECT rule_id, count(*)::int AS findings_count, "
                "coalesce(sum(monthly_savings_usd), 0)::float8 AS monthly_savings_usd "
                "FROM findings WHERE tenant_id = :tenant_id "
                "GROUP BY rule_id ORDER BY monthly_savings_usd DESC"
            ),
            {"tenant_id": tenant_id},
        ).mappings().all()
        # LEFT JOIN so accounts with zero findings (or never scanned) still show.
        by_account = db.execute(
            text(
                "SELECT a.id AS aws_account_id, a.name AS aws_account_name, "
                "a.scan_enabled, a.verified_at, "
                "split_part(a.role_arn, ':', 5) AS aws_account_number, "
                "a.last_scan_at, a.last_scan_status, "
                "count(f.id)::int AS findings_count, "
                "coalesce(sum(f.monthly_savings_usd), 0)::float8 AS monthly_savings_usd "
                "FROM aws_accounts a LEFT JOIN findings f "
                "ON f.aws_account_id = a.id AND f.tenant_id = a.tenant_id "
                "WHERE a.tenant_id = :tenant_id "
                "GROUP BY a.id ORDER BY monthly_savings_usd DESC, a.name"
            ),
            {"tenant_id": tenant_id},
        ).mappings().all()
        return {
            "findings_count": totals["findings_count"],
            "total_monthly_savings_usd": totals["total_monthly_savings_usd"],
            "by_rule": [dict(row) for row in by_rule],
            "by_account": [dict(row) for row in by_account],
        }
    finally:
        db.close()
