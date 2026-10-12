"""Web onboarding flow: workspace, account registration, verify, scan, removal.
AWS is moto only; tenants are synthetic and removed afterwards."""

from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import text

from services.api.db import SessionLocal
from services.api.main import app
from services.common import aws_access
from services.rules_engine.store import set_tenant_context
from tests.conftest import create_synthetic_user, delete_synthetic_user
from tests.test_api import _client_for_user
from tests.test_rls import _db_available


def _identity(arn: str) -> dict:
    return {"Account": arn.split(":")[4], "Arn": arn, "UserId": "x"}


@pytest.mark.parametrize(
    ("caller", "principal", "pattern"),
    [
        ("arn:aws:sts::111111111111:assumed-role/vm-role/i-0abc", "arn:aws:iam::111111111111:role/vm-role", None),
        ("arn:aws:iam::111111111111:user/ops", "arn:aws:iam::111111111111:user/ops", None),
        ("arn:aws:sts::111111111111:assumed-role/AWSReservedSSO_Ops_abc123/me@example.com", None,
         "arn:aws:iam::111111111111:role/aws-reserved/sso.amazonaws.com/*AWSReservedSSO_Ops_abc123"),
    ],
)
def test_source_identity_trust_principal(monkeypatch, caller, principal, pattern):
    monkeypatch.delenv("SOURCE_ROLE_ARN", raising=False)
    with patch("services.common.aws_access.boto3.Session") as session:
        session.return_value.client.return_value.get_caller_identity.return_value = _identity(caller)
        source = aws_access.source_identity()
    assert (source.principal_arn, source.principal_arn_pattern) == (principal, pattern)
    trust = aws_access.trust_policy(source, "ext-id-0123456789abcdef")["Statement"][0]
    assert trust["Action"] == "sts:AssumeRole"
    assert trust["Condition"]["StringEquals"] == {"sts:ExternalId": "ext-id-0123456789abcdef"}
    if pattern:
        assert trust["Principal"] == {"AWS": "arn:aws:iam::111111111111:root"}
        assert trust["Condition"]["ArnLike"] == {"aws:PrincipalArn": pattern}
    else:
        assert trust["Principal"] == {"AWS": principal}


def test_permissions_policy_is_read_only():
    actions = aws_access.permissions_policy()["Statement"][0]["Action"]
    assert actions == aws_access.TARGET_READ_ACTIONS
    assert all(a.split(":")[1].startswith("Describe") for a in actions)


def _remove_user_and_workspace(user_id: str) -> None:
    with SessionLocal() as db:
        tenant_id = db.execute(
            text("SELECT tenant_id FROM users WHERE id = CAST(:u AS uuid)"), {"u": user_id}
        ).scalar()
        delete_synthetic_user(db, user_id)
        if tenant_id:
            set_tenant_context(db, tenant_id)
            for table in ("findings", "aws_accounts"):
                db.execute(text(f"DELETE FROM {table} WHERE tenant_id = :t"), {"t": str(tenant_id)})
            db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": str(tenant_id)})
        db.commit()


@pytest.fixture
def new_user():
    """A signed-in user with no workspace yet; removed with anything it created."""
    if not _db_available():
        pytest.skip("Postgres not running")
    with SessionLocal() as db:
        user_id = create_synthetic_user(db)
        db.commit()
    yield user_id
    app.dependency_overrides.clear()
    _remove_user_and_workspace(user_id)


@pytest.fixture
def aws(monkeypatch):
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(var, "testing")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("SOURCE_ROLE_ARN", raising=False)
    with mock_aws():
        yield


def test_web_onboarding_end_to_end(new_user, aws):
    client = _client_for_user(new_user)
    assert client.get("/accounts").status_code == 404
    created = client.post("/tenant", json={"name": f"ws-{new_user[-8:]}"})
    assert created.status_code == 201
    assert client.post("/tenant", json={"name": "ignored"}).json() == created.json()

    assert client.post("/accounts", json={"name": "bad", "account_number": "12"}).status_code == 422
    account_id = client.post(
        "/accounts", json={"name": "prod", "account_number": "123456789012"}
    ).json()["id"]
    assert client.post(
        "/accounts", json={"name": "prod", "account_number": "123456789012"}
    ).status_code == 409

    [listed] = client.get("/accounts").json()
    assert "external_id" not in listed
    assert listed["scan_enabled"] is False and listed["verified_at"] is None
    assert listed["role_arn"] == "arn:aws:iam::123456789012:role/FinOps-ReadOnly"

    setup = client.get(f"/accounts/{account_id}").json()
    assert len(setup["external_id"]) >= 16
    trust = setup["trust_policy"]["Statement"][0]
    assert trust["Condition"]["StringEquals"]["sts:ExternalId"] == setup["external_id"]
    assert setup["source_policy_statement"]["Resource"] == "arn:aws:iam::*:role/FinOps-ReadOnly*"

    assert client.patch(f"/accounts/{account_id}", json={"scan_enabled": True}).status_code == 409
    assert client.post(f"/accounts/{account_id}/scan").status_code == 409

    boto3.client("ec2", region_name="us-east-1").create_volume(
        AvailabilityZone="us-east-1a", Size=100, VolumeType="gp3"
    )
    verify = client.post(f"/accounts/{account_id}/verify").json()
    assert verify["ok"], verify
    assert verify["target_account"] == "123456789012"
    assert "us-east-1" in verify["regions"]

    [listed] = client.get("/accounts").json()
    assert listed["scan_enabled"] is True and listed["verified_at"]

    # TestClient runs background tasks before returning.
    with patch("services.rules_engine.runner.list_enabled_regions", return_value=["us-east-1"]):
        assert client.post(f"/accounts/{account_id}/scan").status_code == 202
    [listed] = client.get("/accounts").json()
    assert listed["last_scan_status"] == "ok", listed["last_scan_error"]
    summary = client.get("/summary").json()
    assert summary["findings_count"] == 1
    assert summary["by_account"][0]["aws_account_id"] == account_id

    # Another user with their own workspace sees nothing of this tenant.
    with SessionLocal() as db:
        other = create_synthetic_user(db)
        db.commit()
    try:
        other_client = _client_for_user(other)
        assert other_client.post("/tenant", json={"name": f"ws-other-{other[-8:]}"}).status_code == 201
        assert other_client.get(f"/accounts/{account_id}").status_code == 404
        assert other_client.get("/accounts").json() == []
    finally:
        _remove_user_and_workspace(other)
    client = _client_for_user(new_user)

    paused = client.patch(f"/accounts/{account_id}", json={"scan_enabled": False}).json()
    assert paused["scan_enabled"] is False
    assert client.patch(
        f"/accounts/{account_id}", json={"role_name": "other-role"}
    ).status_code == 422  # outside the scanner's FinOps-ReadOnly* grant
    renamed = client.patch(f"/accounts/{account_id}", json={"role_name": "FinOps-ReadOnly-v2"}).json()
    assert renamed["role_arn"].endswith(":role/FinOps-ReadOnly-v2") and renamed["verified_at"] is None

    assert client.delete(f"/accounts/{account_id}").status_code == 204
    assert client.get("/accounts").json() == []
    assert client.get("/summary").json()["findings_count"] == 0


def test_verify_reports_missing_credentials(new_user, monkeypatch):
    client = _client_for_user(new_user)
    client.post("/tenant", json={"name": f"ws-{new_user[-8:]}"})
    account_id = client.post(
        "/accounts", json={"name": "prod", "account_number": "123456789012"}
    ).json()["id"]
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/nonexistent")
    monkeypatch.setenv("AWS_CONFIG_FILE", "/nonexistent")
    result = client.post(f"/accounts/{account_id}/verify").json()
    assert result["ok"] is False and result["stage"] == "source"
    assert result["hint"]
    assert client.get("/accounts").json()[0]["scan_enabled"] is False
