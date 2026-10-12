"""Production boundaries: no alternate scanner, no deployment seed, consistent branding."""

import ast
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.stub import Stubber

from services.api.main import app
from services.common.aws_session import assume_tenant_role
from services.inventory_collector.collector import collect_ec2_volumes, list_enabled_regions

ROOT = Path(__file__).resolve().parents[1]
RETIRED_MODULES = ("raw_import", "snapshot_replay")
# Split so repo-wide searches for these names stay clean.
RETIRED_NAMES = ("test" + "finops", "cloud" + "forge", "work" + "os", "auth" + "kit")
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".css", ".json", ".md", ".sql", ".yml", ".yaml", ".tf",
                 ".sh", ".toml", ".example", ".mjs"}
RETIRED_CLIS = ("import_raw_aws", "export_aws_snapshot", "replay_snapshot")


def test_retired_code_and_cli_are_absent():
    for name in RETIRED_MODULES:
        assert not (ROOT / "services" / name).exists()
    for name in RETIRED_CLIS:
        assert not (ROOT / "scripts" / f"{name}.py").exists()
    for directory in ("services", "scripts"):
        for path in (ROOT / directory).rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert not any(name in (node.module or "") for name in RETIRED_MODULES)
                elif isinstance(node, ast.Import):
                    assert not any(name in alias.name for name in RETIRED_MODULES
                                   for alias in node.names)


def test_no_retired_names_anywhere():
    skip = {"node_modules", ".next", ".venv", ".git", "__pycache__", ".terraform"}
    for path in ROOT.rglob("*"):
        if skip.intersection(path.parts) or not path.is_file():
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {"Dockerfile", ".gitignore", ".dockerignore"}:
            content = path.read_text().lower()
            assert not [n for n in RETIRED_NAMES if n in content], path


def test_visible_branding_and_empty_ui():
    assert app.title == "FinOps Tool API"
    for path in ("web/app/layout.tsx", "web/app/login/page.tsx", "web/components/app/TopNav.tsx"):
        assert "FinOps Tool" in (ROOT / path).read_text()
    view = (ROOT / "web/components/dashboard/DashboardView.tsx").read_text()
    assert "No AWS accounts connected yet" in view
    assert "/dashboard/accounts/new" in view
    assert "if (!hasAccounts)" in view
    assert not list((ROOT / "scripts").glob("*seed*"))


def test_source_credentials_resolved_per_job_and_external_id_preserved():
    source, target = MagicMock(), MagicMock()
    source.client.return_value.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "temporary-test-key",
            "SecretAccessKey": "temporary-test-secret",
            "SessionToken": "temporary-test-token",
        }
    }
    with patch("services.common.aws_session.boto3.Session",
               side_effect=[source, target, source, target]) as factory:
        for _ in range(2):
            assert assume_tenant_role(
                "arn:aws:iam::123456789012:role/finops-test", "external-test-id", "job"
            ) is target
        assert factory.call_args_list[0].kwargs == {}
        assert factory.call_args_list[2].kwargs == {}
        assert factory.call_args_list[1].kwargs == {
            "aws_access_key_id": "temporary-test-key",
            "aws_secret_access_key": "temporary-test-secret",
            "aws_session_token": "temporary-test-token",
            "region_name": "us-east-1",
        }
    source.client.assert_called_with("sts", region_name="us-east-1")
    source.client.return_value.assume_role.assert_called_with(
        RoleArn="arn:aws:iam::123456789012:role/finops-test",
        ExternalId="external-test-id", RoleSessionName="job", DurationSeconds=900,
    )


def test_real_collector_pagination_and_region_discovery():
    import boto3

    # Explicit synthetic credentials + Stubber; any unexpected API call fails closed.
    client = boto3.client("ec2", region_name="us-east-1", aws_access_key_id="testing",
                          aws_secret_access_key="testing", aws_session_token="testing")
    session = MagicMock()
    session.client.return_value = client
    with Stubber(client) as stub:
        stub.add_response("describe_regions", {"Regions": [
            {"RegionName": "us-west-2"}, {"RegionName": "us-east-1"},
        ]}, {"AllRegions": False})
        stub.add_response("describe_volumes", {"Volumes": [{
            "VolumeId": "vol-one", "Size": 10, "VolumeType": "gp3", "State": "available",
        }], "NextToken": "page2"}, {})
        stub.add_response("describe_volumes", {"Volumes": [{
            "VolumeId": "vol-two", "Size": 20, "VolumeType": "gp2", "State": "in-use",
        }]}, {"NextToken": "page2"})
        assert list_enabled_regions(session, "us-east-1") == ["us-east-1", "us-west-2"]
        rows = collect_ec2_volumes(session, "us-east-1")
        assert [r["volume_id"] for r in rows] == ["vol-one", "vol-two"]
        stub.assert_no_pending_responses()


def test_iam_policies_match_current_scanner():
    source = json.loads((ROOT / "infra/policies/source-identity.json").read_text())
    target = json.loads((ROOT / "infra/policies/target-readonly.json").read_text())
    trust = json.loads((ROOT / "infra/policies/target-trust.json").read_text())
    from services.common.aws_access import SOURCE_ASSUME_RESOURCE

    assert source["Statement"][0]["Action"] == ["sts:AssumeRole"]
    assert source["Statement"][0]["Resource"] == [SOURCE_ASSUME_RESOURCE]
    for tf in ("infra/envs/scanner_identity/main.tf", "infra/modules/platform_host/main.tf"):
        assert f'resources = ["{SOURCE_ASSUME_RESOURCE}"]' in (ROOT / tf).read_text(), tf
    assert set(target["Statement"][0]["Action"]) == {
        "ec2:DescribeRegions", "ec2:DescribeVolumes", "ec2:DescribeAddresses",
    }
    assert trust["Statement"][0]["Condition"]["StringEquals"]["sts:ExternalId"]


@pytest.mark.parametrize("value", ["", None])
def test_missing_external_id_never_constructs_an_aws_client(value):
    with patch("services.common.aws_session.boto3.Session") as factory:
        with pytest.raises(ValueError):
            assume_tenant_role("arn:aws:iam::123456789012:role/test", value, "job")
        factory.assert_not_called()


def test_only_web_can_be_published_beyond_loopback():
    import yaml

    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    for name, service in compose["services"].items():
        for port in service.get("ports", []):
            if name == "web":
                assert port.startswith("${WEB_BIND_ADDRESS:-127.0.0.1}:"), port
            else:
                assert port.startswith("127.0.0.1:"), (name, port)


def test_target_actions_single_source_of_truth():
    from services.common.aws_access import TARGET_READ_ACTIONS

    template = json.loads((ROOT / "infra/policies/target-readonly.json").read_text())
    assert sorted(template["Statement"][0]["Action"]) == sorted(TARGET_READ_ACTIONS)
    terraform = (ROOT / "infra/modules/onboarding_role/main.tf").read_text()
    assert all(f'"{action}"' in terraform for action in TARGET_READ_ACTIONS)


def test_containers_never_get_the_operator_aws_directory_by_default():
    import yaml

    override = yaml.safe_load((ROOT / "docker-compose.aws-profile.yml").read_text())
    for name in ("scanner", "api"):
        service = override["services"][name]
        # Explicit directory only: ~/.aws may hold the operator's IAM user keys.
        assert service["volumes"][0]["source"].startswith("${AWS_PROFILE_DIR:?"), name
        # A shell-exported AWS_PROFILE must not leak into the containers.
        assert service["environment"]["AWS_PROFILE"].startswith("${FINOPS_AWS_PROFILE"), name
    scanner_role = (ROOT / "infra/envs/scanner_identity/main.tf").read_text()
    assert scanner_role.count("actions") == 2 and scanner_role.count('["sts:AssumeRole"]') == 2
