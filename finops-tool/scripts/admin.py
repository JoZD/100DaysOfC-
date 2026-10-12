"""Operator CLI: workspaces (tenants), dashboard users and the AWS accounts they own.

  python -m scripts.admin create-tenant --name acme
  python -m scripts.admin create-user --email ana@example.com --tenant acme
  python -m scripts.admin set-password --email ana@example.com
  python -m scripts.admin delete-user --email ana@example.com
  python -m scripts.admin gen-external-id
  python -m scripts.admin add-account --tenant acme --name prod-payments \\
      --role-arn arn:aws:iam::123456789012:role/FinOps-ReadOnly-prod-payments \\
      --external-id <same value given to the onboarding_role Terraform module>
  python -m scripts.admin list

Re-running create-tenant / add-account with the same name updates the row.
Inside the server, prefix with `docker compose run --rm api` (see docs/DEPLOY_DEBIAN.md).
"""

import argparse
import getpass
import re
import secrets
import sys

from sqlalchemy import text

from services.api.auth import MIN_PASSWORD_LENGTH, hash_password
from services.api.db import SessionLocal
from services.rules_engine.store import set_tenant_context

# Role names start with FinOps-ReadOnly: the scanner may assume only those.
ROLE_ARN_RE = re.compile(r"^arn:aws:iam::\d{12}:role/FinOps-ReadOnly[\w+=,.@-]*$")


def _tenant_id(db, name: str) -> str:
    tenant_id = db.execute(text("SELECT id FROM tenants WHERE name = :n"), {"n": name}).scalar()
    if tenant_id is None:
        raise SystemExit(f"no tenant named {name!r} — run create-tenant first")
    return str(tenant_id)


def create_tenant(db, args) -> None:
    tenant_id = db.execute(
        text(
            """
            INSERT INTO tenants (name) VALUES (:name)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """
        ),
        {"name": args.name},
    ).scalar()
    db.commit()
    print(f"tenant {args.name!r}: {tenant_id}")


def _read_password(args) -> str:
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("password: ")
        if getpass.getpass("repeat password: ") != password:
            raise SystemExit("passwords do not match")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    return password


def create_user(db, args) -> None:
    email = args.email.strip().lower()
    if "@" not in email:
        raise SystemExit("--email must be an email address")
    tenant_id = _tenant_id(db, args.tenant) if args.tenant else None
    if db.execute(text("SELECT 1 FROM users WHERE email = :e"), {"e": email}).first():
        raise SystemExit(f"user {email!r} exists — use set-password or set-tenant")
    user_id = db.execute(
        text("INSERT INTO users (email, password_hash, tenant_id) VALUES (:e, :h, :t) RETURNING id"),
        {"e": email, "h": hash_password(_read_password(args)), "t": tenant_id},
    ).scalar()
    db.commit()
    print(f"user {email!r}: {user_id}")
    if tenant_id is None:
        print("note: no --tenant — the user creates their workspace from the web on first sign-in")


def _require_user(db, email: str) -> None:
    if not db.execute(text("SELECT 1 FROM users WHERE email = :e"), {"e": email.lower()}).first():
        raise SystemExit(f"no user {email!r}")


def set_password(db, args) -> None:
    _require_user(db, args.email)
    db.execute(
        text("UPDATE users SET password_hash = :h WHERE email = :e"),
        {"h": hash_password(_read_password(args)), "e": args.email.lower()},
    )
    db.commit()
    print(f"password updated for {args.email.lower()!r} (existing sessions stay valid until they expire)")


def set_tenant(db, args) -> None:
    _require_user(db, args.email)
    db.execute(
        text("UPDATE users SET tenant_id = :t WHERE email = :e"),
        {"t": _tenant_id(db, args.tenant), "e": args.email.lower()},
    )
    db.commit()
    print(f"user {args.email.lower()!r} now belongs to tenant {args.tenant!r}")


def delete_user(db, args) -> None:
    _require_user(db, args.email)
    db.execute(text("DELETE FROM users WHERE email = :e"), {"e": args.email.lower()})
    db.commit()
    print(f"user {args.email.lower()!r} deleted (workspace data is kept)")


def add_account(db, args) -> None:
    if not ROLE_ARN_RE.match(args.role_arn):
        raise SystemExit("--role-arn must look like arn:aws:iam::<12 digits>:role/FinOps-ReadOnly[-suffix]")
    if len(args.external_id) < 16:
        raise SystemExit("--external-id should be at least 16 chars (use gen-external-id)")
    tenant_id = _tenant_id(db, args.tenant)
    set_tenant_context(db, tenant_id)
    account_id = db.execute(
        text(
            """
            INSERT INTO aws_accounts (tenant_id, name, role_arn, external_id, scan_enabled)
            VALUES (:tenant_id, :name, :role_arn, :external_id, :scan_enabled)
            ON CONFLICT (tenant_id, name) DO UPDATE SET
                role_arn = EXCLUDED.role_arn,
                external_id = EXCLUDED.external_id,
                scan_enabled = EXCLUDED.scan_enabled
            RETURNING id
            """
        ),
        {
            "tenant_id": tenant_id,
            "name": args.name,
            "role_arn": args.role_arn,
            "external_id": args.external_id,
            "scan_enabled": not args.disabled,
        },
    ).scalar()
    db.commit()
    print(f"account {args.tenant}/{args.name}: {account_id}")


def list_all(db, _args) -> None:
    tenants = db.execute(text("SELECT id, name FROM tenants ORDER BY name")).all()
    users = db.execute(text("SELECT email, tenant_id FROM users ORDER BY email")).all()
    if not tenants and not users:
        print("nothing yet — start with: python -m scripts.admin create-user -h")
        return
    for tenant_id, name in tenants:
        members = [email for email, t in users if t == tenant_id]
        print(f"{name}  (users: {', '.join(members) or '-'})")
        set_tenant_context(db, tenant_id)
        accounts = db.execute(
            text(
                "SELECT name, role_arn, scan_enabled, last_scan_at, last_scan_status, "
                "last_scan_error FROM aws_accounts WHERE tenant_id = :t ORDER BY name"
            ),
            {"t": str(tenant_id)},
        ).all()
        if not accounts:
            print("  (no AWS accounts — connect one from the web or with: "
                  "python -m scripts.admin add-account -h)")
        for a_name, arn, enabled, last_at, status, error in accounts:
            state = "enabled" if enabled else "disabled"
            last = f"{status} at {last_at:%Y-%m-%d %H:%M}" if last_at else "never scanned"
            print(f"  - {a_name}  {arn}  [{state}; {last}]")
            if error:
                print(f"      last error: {error}")
        db.commit()
    unassigned = [email for email, t in users if t is None]
    if unassigned:
        print(f"users without a workspace: {', '.join(unassigned)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create-tenant", help="create a tenant (workspace) if it does not exist")
    p.add_argument("--name", required=True)
    p.set_defaults(func=create_tenant)

    p = sub.add_parser("create-user", help="create a dashboard user (prompts for the password)")
    p.add_argument("--email", required=True)
    p.add_argument("--tenant", help="existing tenant to join; omit to create one from the web")
    p.add_argument("--password-stdin", action="store_true", help="read the password from stdin")
    p.set_defaults(func=create_user)

    p = sub.add_parser("set-password", help="change a user's password")
    p.add_argument("--email", required=True)
    p.add_argument("--password-stdin", action="store_true", help="read the password from stdin")
    p.set_defaults(func=set_password)

    p = sub.add_parser("set-tenant", help="move a user to another tenant")
    p.add_argument("--email", required=True)
    p.add_argument("--tenant", required=True)
    p.set_defaults(func=set_tenant)

    p = sub.add_parser("delete-user", help="delete a dashboard user")
    p.add_argument("--email", required=True)
    p.set_defaults(func=delete_user)

    p = sub.add_parser("add-account", help="register/update an AWS account under a tenant")
    p.add_argument("--tenant", required=True)
    p.add_argument("--name", required=True, help="friendly name, e.g. prod-payments")
    p.add_argument("--role-arn", required=True)
    p.add_argument("--external-id", required=True)
    p.add_argument("--disabled", action="store_true", help="register without scheduled scans")
    p.set_defaults(func=add_account)

    p = sub.add_parser("gen-external-id", help="print a random ExternalId")
    p.set_defaults(func=None)

    p = sub.add_parser("list", help="list tenants, users, accounts and last scan status")
    p.set_defaults(func=list_all)

    args = parser.parse_args()
    if args.func is None:
        print(secrets.token_hex(24))
        return
    db = SessionLocal()
    try:
        args.func(db, args)
    finally:
        db.close()


if __name__ == "__main__":
    main()
