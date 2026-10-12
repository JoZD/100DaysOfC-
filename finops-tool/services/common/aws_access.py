"""Read-only AWS identity checks and the IAM documents a target account needs.

Everything here is shared by the dashboard onboarding API and the operator
diagnostic (scripts.check_aws_access). Errors are reduced to AWS error code +
message; credentials and request/response bodies are never returned or logged.
"""

import json
import os
import re
from dataclasses import dataclass, field

import boto3  # type: ignore[import-untyped]  # SDK stubs are not a runtime dependency.
from botocore.exceptions import (  # type: ignore[import-untyped]
    BotoCoreError,
    ClientError,
    NoCredentialsError,
)

from services.common.aws_session import assume_tenant_role
from services.inventory_collector.collector import list_enabled_regions

DEFAULT_ROLE_NAME = "FinOps-ReadOnly"
PERMISSIONS_POLICY_NAME = "finops-readonly"
# Every target role name starts with this prefix, so the scanner identity is
# granted once, for all customers: sts:AssumeRole on arn:aws:iam::*:role/FinOps-ReadOnly*.
# Access still needs each customer's trust policy (naming the scanner identity)
# and that account's unique, server-generated ExternalId.
TARGET_ROLE_PREFIX = "FinOps-ReadOnly"
SOURCE_ASSUME_RESOURCE = f"arn:aws:iam::*:role/{TARGET_ROLE_PREFIX}*"

# Exactly the APIs the production collectors call (services/inventory_collector).
TARGET_READ_ACTIONS = [
    "ec2:DescribeRegions",
    "ec2:DescribeVolumes",
    "ec2:DescribeAddresses",
]

_ASSUMED_ROLE_RE = re.compile(r"^arn:aws:sts::(\d{12}):assumed-role/([^/]+)/.+$")
_SSO_ROLE_PREFIX = "AWSReservedSSO_"


def home_region() -> str:
    return os.environ.get("AWS_REGION", "us-east-1")


def describe_error(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        err = exc.response.get("Error", {})
        return f"{err.get('Code', 'ClientError')}: {err.get('Message', '')}"[:500]
    return f"{type(exc).__name__}: {exc}"[:500]


@dataclass(frozen=True)
class SourceIdentity:
    """The VM identity that calls sts:AssumeRole, and how targets must trust it."""

    account_id: str
    caller_arn: str
    # Exact principal for the trust policy (role/user ARN), or None when the
    # identity is an IAM Identity Center role (path is not known from STS).
    principal_arn: str | None
    # For SSO roles: ArnLike pattern on aws:PrincipalArn with an account principal.
    principal_arn_pattern: str | None = None


def source_identity() -> SourceIdentity:
    """Resolve the ambient boto3 credentials (instance role, SSO, env...)."""
    caller = boto3.Session().client("sts", region_name=home_region()).get_caller_identity()
    account_id, arn = caller["Account"], caller["Arn"]
    override = os.environ.get("SOURCE_ROLE_ARN", "").strip()
    if override:
        return SourceIdentity(account_id, arn, override)
    match = _ASSUMED_ROLE_RE.match(arn)
    if not match:
        return SourceIdentity(account_id, arn, arn)  # IAM user or already a role ARN
    role_name = match.group(2)
    if role_name.startswith(_SSO_ROLE_PREFIX):
        pattern = f"arn:aws:iam::{account_id}:role/aws-reserved/sso.amazonaws.com/*{role_name}"
        return SourceIdentity(account_id, arn, None, pattern)
    # Roles with a non-default path need SOURCE_ROLE_ARN (STS drops the path).
    return SourceIdentity(account_id, arn, f"arn:aws:iam::{account_id}:role/{role_name}")


def trust_policy(source: SourceIdentity, external_id: str) -> dict:
    condition: dict = {"StringEquals": {"sts:ExternalId": external_id}}
    if source.principal_arn:
        principal = source.principal_arn
    else:
        principal = f"arn:aws:iam::{source.account_id}:root"
        condition["ArnLike"] = {"aws:PrincipalArn": source.principal_arn_pattern}
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": principal},
                "Action": "sts:AssumeRole",
                "Condition": condition,
            }
        ],
    }


def permissions_policy() -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "FinOpsInventoryReadOnly",
                "Effect": "Allow",
                "Action": TARGET_READ_ACTIONS,
                "Resource": "*",
            }
        ],
    }


def source_policy_statement() -> dict:
    """The scanner identity's only permission; the same for every customer."""
    return {
        "Sid": "AssumeFinOpsTargetRoles",
        "Effect": "Allow",
        "Action": "sts:AssumeRole",
        "Resource": SOURCE_ASSUME_RESOURCE,
    }


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=2)


@dataclass
class VerifyResult:
    ok: bool
    stage: str  # "source" | "assume_role" | "identity" | "permissions" | "done"
    source_arn: str | None = None
    target_account: str | None = None
    regions: list[str] = field(default_factory=list)
    error: str | None = None
    hint: str | None = None


_HINTS = {
    "source": (
        "The VM has no usable AWS credentials. Check the instance role / SSO login / "
        "credential override available to the api and scanner containers."
    ),
    "assume_role": (
        "AssumeRole was denied. Check that the role exists with this exact name, its trust "
        "policy names the VM identity and this ExternalId, and the VM identity's own policy "
        "allows sts:AssumeRole on this role ARN."
    ),
    "identity": "The assumed role belongs to a different account than the one registered.",
    "permissions": (
        "The role was assumed but cannot call ec2:DescribeRegions. Attach the permissions "
        "policy shown in step 2."
    ),
}


def verify_target(role_arn: str, external_id: str, session_name: str) -> VerifyResult:
    """AssumeRole + identity + region discovery. Read-only; writes nothing."""
    region = home_region()
    result = VerifyResult(ok=False, stage="source")
    try:
        result.source_arn = source_identity().caller_arn
    except (NoCredentialsError, BotoCoreError, ClientError) as exc:
        result.error, result.hint = describe_error(exc), _HINTS["source"]
        return result

    result.stage = "assume_role"
    try:
        target = assume_tenant_role(role_arn, external_id, session_name, region=region)
    except (BotoCoreError, ClientError) as exc:
        result.error, result.hint = describe_error(exc), _HINTS["assume_role"]
        return result

    result.stage = "identity"
    try:
        identity = target.client("sts", region_name=region).get_caller_identity()
    except (BotoCoreError, ClientError) as exc:
        result.error, result.hint = describe_error(exc), _HINTS["identity"]
        return result
    result.target_account = identity["Account"]
    if result.target_account != role_arn.split(":")[4]:
        result.error, result.hint = "Assumed identity is in another account", _HINTS["identity"]
        return result

    result.stage = "permissions"
    try:
        result.regions = list_enabled_regions(target, region)
    except (BotoCoreError, ClientError) as exc:
        result.error, result.hint = describe_error(exc), _HINTS["permissions"]
        return result

    result.stage, result.ok = "done", True
    return result
