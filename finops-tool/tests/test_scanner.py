"""End-to-end scan path against moto's mocked AWS: AssumeRole (with
ExternalId) -> multi-region inventory -> every catalog rule -> Findings.
No real AWS account or database needed."""

import uuid

import boto3
import pytest
from moto import mock_aws

from services.common.aws_session import assume_tenant_role
from services.common.duckdb_client import get_duckdb_connection
from services.inventory_collector.collector import load_inventory_views
from services.rules_engine.loader import load_rules, run_rule
from services.rules_engine.runner import scan_account
from services.rules_engine.store import AccountScanConfig

ROLE_ARN = "arn:aws:iam::123456789012:role/FinOps-ReadOnly-test"


@pytest.fixture
def aws(monkeypatch):
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(var, "testing")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield


def _account() -> AccountScanConfig:
    return AccountScanConfig(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        tenant_name="acme",
        name="prod",
        role_arn=ROLE_ARN,
        external_id="x" * 24,
    )


def test_empty_account_runs_every_rule_without_errors(aws):
    # Regression: empty inventories used to register a frame with no real
    # columns, so rule SQL failed with a binder error.
    session = assume_tenant_role(ROLE_ARN, "x" * 24, "test")
    con = get_duckdb_connection()
    counts = load_inventory_views(con, session, ["us-east-1"])
    assert counts == {"ec2_volumes": 0, "ec2_addresses": 0}
    for rule in load_rules():
        assert run_rule(con, rule, tenant_id="t") == []


def test_scan_account_finds_waste_across_regions(aws):
    use1 = boto3.client("ec2", region_name="us-east-1")
    euw1 = boto3.client("ec2", region_name="eu-west-1")
    use1.create_volume(AvailabilityZone="us-east-1a", Size=100, VolumeType="gp3")  # orphaned
    euw1.create_volume(AvailabilityZone="eu-west-1a", Size=50, VolumeType="gp2")  # orphaned
    alloc = euw1.allocate_address(Domain="vpc")["AllocationId"]  # unassociated

    findings = scan_account(_account(), "us-east-1", ["us-east-1", "eu-west-1"])

    by_rule: dict[str, list] = {}
    for f in findings:
        by_rule.setdefault(f.rule_id, []).append(f)

    ebs = sorted(by_rule["orphaned_ebs_volumes"], key=lambda f: f.evidence["region"])
    assert [(f.evidence["region"], f.monthly_savings_usd) for f in ebs] == [
        ("eu-west-1", 5.0),   # 50 GB gp2 @ 0.10
        ("us-east-1", 8.0),   # 100 GB gp3 @ 0.08
    ]
    assert "--region us-east-1" in ebs[1].remediation_action

    (eip,) = by_rule["unassociated_eips"]
    assert eip.resource_id == alloc
    assert eip.remediation_action.startswith(
        f"aws ec2 release-address --region eu-west-1 --allocation-id {alloc}"
    )


def test_assume_role_requires_external_id():
    with pytest.raises(ValueError):
        assume_tenant_role(ROLE_ARN, "", "test")
