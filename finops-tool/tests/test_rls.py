"""Integration test: row-level security must actually isolate tenants.

This exists because of a real bug: the policy from 001 was silently
bypassed, first by the table owner (fixed by FORCE in 003) and then by the
superuser connection (fixed by the finops_app role in 004). aws_accounts
(005) holds role ARNs + ExternalIds, so it gets the same checks. Requires the
dev Postgres from docker-compose; skips when it isn't reachable.
"""

import pytest
from sqlalchemy import text

from services.api.db import SessionLocal, engine


def _db_available() -> bool:
    try:
        with engine.connect():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="dev Postgres not running")


@pytest.mark.parametrize("table", ["findings", "aws_accounts"])
def test_rls_hides_tenant_data_without_tenant_context(table):
    db = SessionLocal()
    try:
        assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
    finally:
        db.close()


@pytest.mark.parametrize("table", ["findings", "aws_accounts"])
def test_rls_hides_tenant_data_for_wrong_tenant(table):
    db = SessionLocal()
    try:
        db.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": "00000000-0000-0000-0000-000000000000"},
        )
        assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
    finally:
        db.close()


@pytest.mark.parametrize("table", ["findings", "aws_accounts"])
def test_rls_shows_tenant_data_for_correct_tenant(table, synthetic_tenant):
    db = SessionLocal()
    try:
        db.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(synthetic_tenant.id)},
        )
        assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() > 0
        # Other tenants' rows stay invisible.
        assert db.execute(
            text(f"SELECT count(*) FROM {table} WHERE tenant_id <> :t"),
            {"t": str(synthetic_tenant.id)},
        ).scalar() == 0
    finally:
        db.close()
