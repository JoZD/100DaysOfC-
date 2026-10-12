"""Real persistence and CLI paths; only synthetic tenants and mocked AWS are used."""

import argparse
import sys
import uuid

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import text

from scripts import admin, check_aws_access
from services.api.db import SessionLocal
from services.rules_engine import runner
from services.rules_engine.store import list_scan_targets, set_tenant_context
from tests.conftest import create_synthetic_user
from tests.test_api import _client_for_user
from tests.test_rls import _db_available

pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not running")


@pytest.fixture
def empty_tenants():
    from services.api.main import app

    names = [f"test-production-{uuid.uuid4().hex}" for _ in range(2)]
    ids = []
    with SessionLocal() as db:
        try:
            for name in names:
                admin.create_tenant(db, argparse.Namespace(name=name))
                ids.append(admin._tenant_id(db, name))
            yield names, ids
        finally:
            app.dependency_overrides.clear()
            db.rollback()
            for tenant_id in ids:
                set_tenant_context(db, tenant_id)
                for table in ("findings", "aws_accounts", "users"):
                    db.execute(text(f"DELETE FROM {table} WHERE tenant_id = :t"), {"t": tenant_id})
                db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tenant_id})
            db.commit()


def add(db, tenant, name, number, *, disabled=False):
    admin.add_account(db, argparse.Namespace(
        tenant=tenant, name=name,
        role_arn=f"arn:aws:iam::{number}:role/FinOps-ReadOnly-test",
        external_id="synthetic-external-id-123", disabled=disabled,
    ))


def test_empty_tenant_returns_no_accounts_findings_or_savings(empty_tenants):
    _, ids = empty_tenants
    with SessionLocal() as db:
        user_id = create_synthetic_user(db, ids[0])
        db.commit()
    client = _client_for_user(user_id)
    assert client.get("/findings").json() == []
    assert client.get("/summary").json() == {
        "findings_count": 0, "total_monthly_savings_usd": 0,
        "by_rule": [], "by_account": [],
    }


def test_onboarding_upsert_enable_disable_and_account_isolation(empty_tenants):
    names, ids = empty_tenants
    with SessionLocal() as db:
        add(db, names[0], "first", "123456789012")
        add(db, names[0], "second", "234567890123", disabled=True)
        add(db, names[1], "first", "345678901234")
        targets = list_scan_targets(db, names[0])
        assert [a.name for a in targets] == ["first"]
        assert targets[0].external_id == "synthetic-external-id-123"
        assert str(targets[0].tenant_id) == ids[0]
        # Explicit account selection is an intentional manual override of scheduling.
        assert list_scan_targets(db, names[0], "second")[0].name == "second"
        add(db, names[0], "first", "123456789012", disabled=True)
        assert list_scan_targets(db, names[0]) == []
        set_tenant_context(db, ids[0])
        assert db.execute(text("SELECT count(*) FROM aws_accounts")).scalar_one() == 2
        assert len(list_scan_targets(db, names[1])) == 1


def test_real_runner_persists_replaces_and_preserves_other_accounts(empty_tenants, monkeypatch):
    names, ids = empty_tenants
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with SessionLocal() as db:
        add(db, names[0], "first", "123456789012")
        add(db, names[0], "second", "123456789012")
        add(db, names[1], "other", "123456789012")
    with mock_aws():
        boto3.client("ec2", region_name="us-east-1").create_volume(
            AvailabilityZone="us-east-1a", Size=100, VolumeType="gp3"
        )
        for name in names:
            monkeypatch.setattr(sys, "argv", ["runner", "--tenant", name,
                                               "--regions", "us-east-1"])
            runner.main()
        monkeypatch.setattr(sys, "argv", ["runner", "--tenant", names[0],
                                           "--account", "first", "--regions", "us-east-1"])
        runner.main()  # replacement, not duplicates
        with SessionLocal() as db:
            for tenant_id, expected in zip(ids, [2, 1], strict=True):
                set_tenant_context(db, tenant_id)
                assert db.execute(text("SELECT count(*) FROM findings")).scalar_one() == expected
                assert set(db.execute(text("SELECT last_scan_status FROM aws_accounts")).scalars()) == {"ok"}
            db.rollback()
        # Diagnostic exercises the same AssumeRole helper and does not write.
        monkeypatch.setattr(sys, "argv", ["check", "--tenant", names[0], "--account", "first"])
        check_aws_access.main()
        # Collection failure on first account must not clear findings or block second.
        original_scan = runner.scan_account

        def fail_first(account, home_region, regions):
            if account.name == "first":
                raise RuntimeError("synthetic collection failure")
            return original_scan(account, home_region, regions)

        monkeypatch.setattr(runner, "scan_account", fail_first)
        monkeypatch.setattr(sys, "argv", ["runner", "--tenant", names[0], "--regions", "us-east-1"])
        with pytest.raises(SystemExit, match="1/2"):
            runner.main()
        with SessionLocal() as db:
            set_tenant_context(db, ids[0])
            assert db.execute(text("SELECT count(*) FROM findings")).scalar_one() == 2
            assert dict(db.execute(text("SELECT name, last_scan_status FROM aws_accounts")).all()) == {
                "first": "failed", "second": "ok",
            }


def test_fresh_database_migrations_are_empty_and_idempotent(monkeypatch):
    """Build a disposable DB from unchanged migration history, never reset the app DB."""
    from sqlalchemy import create_engine

    from scripts import apply_migrations

    database_name = f"finops_install_{uuid.uuid4().hex}"
    admin_engine = create_engine(apply_migrations.engine.url, isolation_level="AUTOCOMMIT")
    fresh_engine = None
    created = False
    try:
        with admin_engine.connect() as conn:
            conn.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
            created = True
        fresh_engine = create_engine(apply_migrations.engine.url.set(database=database_name))
        monkeypatch.setattr(apply_migrations, "engine", fresh_engine)
        # Roles are cluster-wide; never rotate the real app role's password in a test.
        monkeypatch.delenv("APP_DB_PASSWORD", raising=False)
        apply_migrations.main()
        apply_migrations.main()
        with fresh_engine.connect() as conn:
            migration_count = len(list(apply_migrations.MIGRATIONS_DIR.glob("*.sql")))
            assert conn.execute(text("SELECT count(*) FROM schema_migrations")).scalar_one() == migration_count
            for table in ("tenants", "users", "aws_accounts", "findings"):
                assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
            assert conn.execute(text(
                "SELECT coalesce(sum(monthly_savings_usd), 0) FROM findings"
            )).scalar_one() == 0
            assert conn.execute(text(
                "SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class "
                "WHERE relname IN ('aws_accounts', 'findings')"
            )).scalar_one()
    finally:
        if fresh_engine is not None:
            fresh_engine.dispose()
        if created:
            with admin_engine.connect() as conn:
                conn.exec_driver_sql(f'DROP DATABASE "{database_name}"')
        admin_engine.dispose()
