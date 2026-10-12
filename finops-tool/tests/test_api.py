"""API endpoints against the live dev DB, with sign-in stubbed out.
Uses a synthetic tenant (tests/conftest.py); never reads real tenant data."""

import uuid

import pytest
from fastapi.testclient import TestClient

from services.api.auth import AuthenticatedUser, get_current_user
from services.api.db import SessionLocal
from services.api.main import app
from tests.conftest import SYNTHETIC_AWS_NUMBER, create_synthetic_user, delete_synthetic_user
from tests.test_rls import _db_available

pytestmark = pytest.mark.skipif(not _db_available(), reason="dev Postgres not running")


def _client_for_user(user_id: str) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(user_id, None)
    return TestClient(app)


@pytest.fixture
def dev_user(synthetic_tenant):
    yield synthetic_tenant.user_id
    app.dependency_overrides.clear()


def test_findings_include_account(dev_user):
    findings = _client_for_user(dev_user).get("/findings").json()
    assert findings, "synthetic findings expected"
    assert {f["aws_account_name"] for f in findings} == {"synthetic"}
    assert all(f["aws_account_number"] == SYNTHETIC_AWS_NUMBER for f in findings)
    assert findings == sorted(findings, key=lambda f: -f["monthly_savings_usd"])


def test_summary_breaks_down_by_account(dev_user):
    summary = _client_for_user(dev_user).get("/summary").json()
    assert summary["findings_count"] == sum(a["findings_count"] for a in summary["by_account"])
    assert [a["aws_account_name"] for a in summary["by_account"]] == ["synthetic"]


def test_user_without_workspace_gets_404_and_unknown_user_401():
    with SessionLocal() as db:
        user_id = create_synthetic_user(db)
        db.commit()
    try:
        assert _client_for_user(user_id).get("/findings").status_code == 404
        assert _client_for_user(str(uuid.uuid4())).get("/findings").status_code == 401
    finally:
        app.dependency_overrides.clear()
        with SessionLocal() as db:
            delete_synthetic_user(db, user_id)
            db.commit()
