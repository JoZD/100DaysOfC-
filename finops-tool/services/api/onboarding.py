"""Dashboard onboarding: create the signed-in user's workspace (tenant), register AWS
accounts, show the IAM role to create, verify AssumeRole and scan on demand.

The tenant is always the signed-in user's own (see tenancy.py). AWS access here
is read-only: STS GetCallerIdentity/AssumeRole and the collectors' Describe
calls. ExternalIds are generated server-side and only returned by the
per-account setup endpoint, never in listings.
"""

import os
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from services.api.auth import CurrentUser
from services.api.db import SessionLocal
from services.api.tenancy import resolve_tenant
from services.common import aws_access
from services.rules_engine.runner import scan_and_store
from services.rules_engine.store import get_account

router = APIRouter()

NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,62}$"
# The prefix keeps every role inside the scanner's one-time grant (aws_access).
ROLE_NAME_PATTERN = rf"^{aws_access.TARGET_ROLE_PREFIX}[\w+=,.@-]{{0,45}}$"
# A "running" mark older than this is treated as abandoned (e.g. API restart).
RUNNING_STALE_AFTER = timedelta(minutes=30)

ACCOUNT_COLUMNS = (
    "id, name, role_arn, split_part(role_arn, ':', 5) AS aws_account_number, "
    "scan_enabled, verified_at, last_scan_at, last_scan_status, last_scan_error, created_at"
)


def _session_name(prefix: str, name: str) -> str:
    # RoleSessionName allows [\w+=,.@-], max 64 chars.
    return re.sub(r"[^\w+=,.@-]", "-", f"finops-{prefix}-{name}")[:64]


def _role_arn(account_number: str, role_name: str) -> str:
    return f"arn:aws:iam::{account_number}:role/{role_name}"


def _load_account_row(db, tenant_id: str, account_id: uuid.UUID) -> dict:
    row = db.execute(
        text(f"SELECT {ACCOUNT_COLUMNS}, external_id FROM aws_accounts "
             "WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": str(account_id), "tenant_id": tenant_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="AWS account not found")
    return dict(row)


def _public(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "external_id"}


# --- Tenant ---------------------------------------------------------------------


class TenantCreate(BaseModel):
    name: str = Field(pattern=NAME_PATTERN)


@router.post("/tenant", status_code=201)
def create_tenant(body: TenantCreate, user: CurrentUser) -> dict:
    """Create a workspace for a signed-in user who has none yet, and join it."""
    if os.environ.get("ALLOW_TENANT_SIGNUP", "true").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=403, detail="Workspace sign-up is disabled on this server")
    with SessionLocal() as db:
        existing = db.execute(
            text("SELECT t.id, t.name FROM users u JOIN tenants t ON t.id = u.tenant_id "
                 "WHERE u.id = CAST(:u AS uuid)"),
            {"u": user.user_id},
        ).first()
        if existing:
            return {"id": str(existing[0]), "name": existing[1]}
        try:
            tenant_id: uuid.UUID = db.execute(
                text("INSERT INTO tenants (name) VALUES (:n) RETURNING id"), {"n": body.name}
            ).scalar_one()
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="That workspace name is taken") from exc
        joined = db.execute(
            text("UPDATE users SET tenant_id = :t WHERE id = CAST(:u AS uuid) RETURNING id"),
            {"t": str(tenant_id), "u": user.user_id},
        ).first()
        if joined is None:
            raise HTTPException(status_code=401, detail="User no longer exists")
        db.commit()
    return {"id": str(tenant_id), "name": body.name}


# --- VM identity ----------------------------------------------------------------


@router.get("/onboarding/source")
def onboarding_source(user: CurrentUser) -> dict:
    """Which AWS identity this server scans from. Read-only (GetCallerIdentity)."""
    with SessionLocal() as db:
        resolve_tenant(db, user.user_id)
    try:
        source = aws_access.source_identity()
    except (BotoCoreError, ClientError) as exc:
        return {"available": False, "error": aws_access.describe_error(exc)}
    return {
        "available": True,
        "account_id": source.account_id,
        "caller_arn": source.caller_arn,
        "principal_arn": source.principal_arn,
        "principal_arn_pattern": source.principal_arn_pattern,
    }


# --- Accounts -------------------------------------------------------------------


class AccountCreate(BaseModel):
    name: str = Field(pattern=NAME_PATTERN)
    account_number: str = Field(pattern=r"^\d{12}$")
    role_name: str = Field(default=aws_access.DEFAULT_ROLE_NAME, pattern=ROLE_NAME_PATTERN)


class AccountUpdate(BaseModel):
    scan_enabled: bool | None = None
    role_name: str | None = Field(default=None, pattern=ROLE_NAME_PATTERN)


@router.get("/accounts")
def list_accounts(user: CurrentUser) -> list[dict]:
    with SessionLocal() as db:
        tenant_id = resolve_tenant(db, user.user_id)
        rows = db.execute(
            text(f"SELECT {ACCOUNT_COLUMNS} FROM aws_accounts "
                 "WHERE tenant_id = :tenant_id ORDER BY name"),
            {"tenant_id": tenant_id},
        ).mappings().all()
        return [dict(r) for r in rows]


@router.post("/accounts", status_code=201)
def create_account(body: AccountCreate, user: CurrentUser) -> dict:
    """Register an account as pending; scans start after a successful verify."""
    with SessionLocal() as db:
        tenant_id = resolve_tenant(db, user.user_id)
        try:
            new_id: uuid.UUID = db.execute(
                text(
                    "INSERT INTO aws_accounts (tenant_id, name, role_arn, external_id, scan_enabled) "
                    "VALUES (:tenant_id, :name, :role_arn, :external_id, false) RETURNING id"
                ),
                {
                    "tenant_id": tenant_id,
                    "name": body.name,
                    "role_arn": _role_arn(body.account_number, body.role_name),
                    "external_id": secrets.token_hex(24),
                },
            ).scalar_one()
            db.commit()
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="An account with that name exists") from exc
    return {"id": str(new_id)}


@router.get("/accounts/{account_id}")
def account_setup(account_id: uuid.UUID, user: CurrentUser) -> dict:
    """Account detail plus the exact IAM documents the customer must create."""
    with SessionLocal() as db:
        tenant_id = resolve_tenant(db, user.user_id)
        row = _load_account_row(db, tenant_id, account_id)
    try:
        source: aws_access.SourceIdentity | None = aws_access.source_identity()
        source_error = None
    except (BotoCoreError, ClientError) as exc:
        source, source_error = None, aws_access.describe_error(exc)
    placeholder = aws_access.SourceIdentity("<VM_ACCOUNT_ID>", "", "<VM_ROLE_ARN>")
    role_arn = row["role_arn"]
    return {
        **_public(row),
        "role_name": role_arn.split(":role/", 1)[1],
        "external_id": row["external_id"],
        "source": None if source is None else {
            "account_id": source.account_id,
            "caller_arn": source.caller_arn,
            "principal_arn": source.principal_arn,
            "principal_arn_pattern": source.principal_arn_pattern,
        },
        "source_error": source_error,
        "permissions_policy_name": aws_access.PERMISSIONS_POLICY_NAME,
        "trust_policy": aws_access.trust_policy(source or placeholder, row["external_id"]),
        "permissions_policy": aws_access.permissions_policy(),
        "source_policy_statement": aws_access.source_policy_statement(),
    }


@router.patch("/accounts/{account_id}")
def update_account(
    account_id: uuid.UUID, body: AccountUpdate, user: CurrentUser
) -> dict:
    with SessionLocal() as db:
        tenant_id = resolve_tenant(db, user.user_id)
        row = _load_account_row(db, tenant_id, account_id)
        params = {"id": str(account_id), "tenant_id": tenant_id}
        if body.role_name is not None:
            # A different role must be verified again before it is scanned.
            params["role_arn"] = _role_arn(row["aws_account_number"], body.role_name)
            db.execute(
                text("UPDATE aws_accounts SET role_arn = :role_arn, verified_at = NULL, "
                     "scan_enabled = false WHERE id = :id AND tenant_id = :tenant_id"),
                params,
            )
        if body.scan_enabled is not None:
            if body.scan_enabled and (row["verified_at"] is None or body.role_name is not None):
                raise HTTPException(status_code=409, detail="Verify the connection first")
            db.execute(
                text("UPDATE aws_accounts SET scan_enabled = :enabled "
                     "WHERE id = :id AND tenant_id = :tenant_id"),
                {**params, "enabled": body.scan_enabled},
            )
        db.commit()
        return _public(_load_account_row(db, resolve_tenant(db, user.user_id), account_id))


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: uuid.UUID, user: CurrentUser) -> Response:
    """Forget the account and its findings. Nothing is changed in AWS."""
    with SessionLocal() as db:
        tenant_id = resolve_tenant(db, user.user_id)
        _load_account_row(db, tenant_id, account_id)
        params = {"id": str(account_id), "tenant_id": tenant_id}
        db.execute(text("DELETE FROM findings WHERE aws_account_id = :id AND tenant_id = :tenant_id"),
                   params)
        db.execute(text("DELETE FROM aws_accounts WHERE id = :id AND tenant_id = :tenant_id"), params)
        db.commit()
    return Response(status_code=204)


@router.post("/accounts/{account_id}/verify")
def verify_account(account_id: uuid.UUID, user: CurrentUser) -> dict:
    """AssumeRole with the stored ExternalId and list regions; enables scans on success."""
    with SessionLocal() as db:
        tenant_id = resolve_tenant(db, user.user_id)
        row = _load_account_row(db, tenant_id, account_id)
    result = aws_access.verify_target(
        row["role_arn"], row["external_id"], _session_name("verify", row["name"])
    )
    if result.ok:
        with SessionLocal() as db:
            tenant_id = resolve_tenant(db, user.user_id)
            db.execute(
                text("UPDATE aws_accounts SET verified_at = now(), scan_enabled = true "
                     "WHERE id = :id AND tenant_id = :tenant_id"),
                {"id": str(account_id), "tenant_id": tenant_id},
            )
            db.commit()
    return {
        "ok": result.ok,
        "stage": result.stage,
        "source_arn": result.source_arn,
        "target_account": result.target_account,
        "regions": result.regions,
        "error": result.error,
        "hint": result.hint,
    }


@router.post("/accounts/{account_id}/scan", status_code=202)
def scan_now(
    account_id: uuid.UUID, background: BackgroundTasks, user: CurrentUser
) -> dict:
    """Run the production scanner for one account in the background."""
    with SessionLocal() as db:
        tenant_id = resolve_tenant(db, user.user_id)
        row = _load_account_row(db, tenant_id, account_id)
        if row["verified_at"] is None:
            raise HTTPException(status_code=409, detail="Verify the connection first")
        started = row["last_scan_at"]
        if (row["last_scan_status"] == "running" and started is not None
                and datetime.now(UTC) - started < RUNNING_STALE_AFTER):
            raise HTTPException(status_code=409, detail="A scan is already running")
        account = get_account(db, tenant_id, str(account_id))
        db.execute(
            text("UPDATE aws_accounts SET last_scan_status = 'running', last_scan_at = now(), "
                 "last_scan_error = NULL WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": str(account_id), "tenant_id": tenant_id},
        )
        db.commit()
    assert account is not None
    background.add_task(scan_and_store, account, aws_access.home_region())
    return {"status": "running"}
