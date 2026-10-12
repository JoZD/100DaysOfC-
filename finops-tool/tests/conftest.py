"""Shared fixtures. DB tests create and remove their own synthetic tenant, so they
never depend on (or read) the real data held in the local dev DB."""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import text

from services.api.db import SessionLocal
from services.common.models import Effort, Finding, Risk
from services.rules_engine.store import replace_findings, set_tenant_context

SYNTHETIC_AWS_NUMBER = "000000000000"


@dataclass(frozen=True)
class SyntheticTenant:
    id: uuid.UUID
    name: str
    user_id: str
    account_name: str


def create_synthetic_user(db, tenant_id=None) -> str:
    """A dashboard user with an unusable password; delete with delete_synthetic_user."""
    return str(db.execute(
        text("INSERT INTO users (email, password_hash, tenant_id) VALUES (:e, '!', :t) RETURNING id"),
        {"e": f"test-{uuid.uuid4().hex}@example.invalid", "t": None if tenant_id is None else str(tenant_id)},
    ).scalar_one())


def delete_synthetic_user(db, user_id: str) -> None:
    db.execute(text("DELETE FROM users WHERE id = CAST(:u AS uuid)"), {"u": user_id})


@pytest.fixture
def synthetic_tenant():
    from tests.test_rls import _db_available

    if not _db_available():
        pytest.skip("dev Postgres not running")
    suffix = uuid.uuid4().hex[:12]
    name, account_name = f"test-{suffix}", "synthetic"
    db = SessionLocal()
    tenant_id = None
    try:
        tenant_id = db.execute(
            text("INSERT INTO tenants (name) VALUES (:n) RETURNING id"), {"n": name}
        ).scalar_one()
        user_id = create_synthetic_user(db, tenant_id)
        set_tenant_context(db, tenant_id)
        account_id = db.execute(
            text(
                "INSERT INTO aws_accounts (tenant_id, name, role_arn, external_id, scan_enabled) "
                "VALUES (:t, :n, :arn, 'synthetic-external-id', false) RETURNING id"
            ),
            {
                "t": str(tenant_id),
                "n": account_name,
                "arn": f"arn:aws:iam::{SYNTHETIC_AWS_NUMBER}:role/synthetic",
            },
        ).scalar_one()
        db.commit()
        findings = [
            Finding(
                tenant_id=str(tenant_id),
                resource_id=resource_id,
                rule_id=rule_id,
                category="waste",
                monthly_savings_usd=savings,
                remediation_effort=Effort.low,
                risk=Risk.low,
                evidence={"region": "us-east-1"},
                remediation_action="# synthetic",
            )
            for resource_id, rule_id, savings in [
                ("vol-synthetic", "orphaned_ebs_volumes", 8.0),
                ("eipalloc-synthetic", "unassociated_eips", 3.6),
            ]
        ]
        replace_findings(db, tenant_id, account_id, findings)
        yield SyntheticTenant(tenant_id, name, user_id, account_name)
    finally:
        db.rollback()
        if tenant_id is not None:
            set_tenant_context(db, tenant_id)
            params = {"t": str(tenant_id)}
            db.execute(text("DELETE FROM findings WHERE tenant_id = :t"), params)
            db.execute(text("DELETE FROM aws_accounts WHERE tenant_id = :t"), params)
            db.execute(text("DELETE FROM users WHERE tenant_id = :t"), params)
            db.execute(text("DELETE FROM tenants WHERE id = :t"), params)
            db.commit()
        db.close()


@pytest.fixture(autouse=True)
def block_live_aws(monkeypatch):
    """All AWS tests must use moto/Stubber; HTTP transport must never reach AWS."""
    from botocore.httpsession import URLLib3Session

    def forbidden(*args, **kwargs):
        raise AssertionError("Live AWS HTTP transport is forbidden in tests")

    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setattr(URLLib3Session, "send", forbidden)
