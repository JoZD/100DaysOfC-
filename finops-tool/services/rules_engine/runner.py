"""Scan AWS accounts and store findings.

Accounts (role ARN + ExternalId) are read from the app DB — register them with
`python -m scripts.admin add-account`. The runner authenticates to STS with
whatever credentials the host provides: the EC2 instance role in production
(see docs/DEPLOY_DEBIAN.md), never long-lived keys.

Usage:
  python -m services.rules_engine.runner --all
  python -m services.rules_engine.runner --tenant acme
  python -m services.rules_engine.runner --tenant acme --account prod-payments --dry-run
"""

import argparse
import os
import re
import sys

import services.common.env  # noqa: F401  (loads .env)
from services.api.db import SessionLocal
from services.common.aws_session import assume_tenant_role
from services.common.duckdb_client import get_duckdb_connection
from services.common.models import Finding
from services.inventory_collector.collector import list_enabled_regions, load_inventory_views
from services.rules_engine.loader import load_rules, run_rule
from services.rules_engine.store import (
    AccountScanConfig,
    list_scan_targets,
    record_scan_result,
    replace_findings,
)


def scan_account(
    account: AccountScanConfig, home_region: str, regions: list[str] | None
) -> list[Finding]:
    # RoleSessionName allows [\w+=,.@-], max 64 chars.
    session_name = re.sub(r"[^\w+=,.@-]", "-", f"finops-{account.name}")[:64]
    session = assume_tenant_role(
        role_arn=account.role_arn,
        external_id=account.external_id,
        session_name=session_name,
        region=home_region,
    )
    scan_regions = regions or list_enabled_regions(session, home_region)

    con = get_duckdb_connection()
    try:
        counts = load_inventory_views(con, session, scan_regions)
        print(f"[{account.tenant_name}/{account.name}] inventory across "
              f"{len(scan_regions)} regions: {counts}")
        findings: list[Finding] = []
        for rule in load_rules():
            findings.extend(run_rule(con, rule, tenant_id=str(account.tenant_id)))
        return findings
    finally:
        con.close()


def scan_and_store(
    account: AccountScanConfig, home_region: str, regions: list[str] | None = None
) -> str | None:
    """Scan one account and persist the outcome; returns the error, if any.

    Used by the CLI loop below and by the dashboard's "Scan now". A failed
    collection records the error and keeps the account's previous findings.
    """
    label = f"{account.tenant_name}/{account.name}"
    # One broken account (role deleted, trust misconfigured, ...) must not
    # block the others. Only the exception type/message is logged — never
    # request/response bodies (CLAUDE.md).
    try:
        findings = scan_account(account, home_region, regions)
    except Exception as exc:  # noqa: BLE001 — isolate per-account failures
        error = f"{type(exc).__name__}: {exc}"[:1000]
        print(f"[{label}] scan FAILED: {error}", file=sys.stderr)
        db = SessionLocal()
        try:
            record_scan_result(db, account, error)
        finally:
            db.close()
        return error

    db = SessionLocal()
    try:
        count = replace_findings(db, account.tenant_id, account.id, findings)
        record_scan_result(db, account, None)
    finally:
        db.close()
    print(f"[{label}] stored {count} findings")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the FinOps rules engine")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true",
                        help="scan every scan_enabled account of every tenant")
    target.add_argument("--tenant", help="scan the scan_enabled accounts of this tenant")
    parser.add_argument("--account", help="with --tenant: scan only this account (by name)")
    parser.add_argument(
        "--regions",
        help="comma-separated regions to scan (default: every region enabled in the account)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print findings as JSON instead of writing them to the database",
    )
    args = parser.parse_args()
    if args.account and not args.tenant:
        parser.error("--account requires --tenant")

    home_region = os.environ.get("AWS_REGION", "us-east-1")
    regions = [r.strip() for r in args.regions.split(",") if r.strip()] if args.regions else None

    db = SessionLocal()
    try:
        accounts = list_scan_targets(db, args.tenant, args.account)
    finally:
        db.close()
    if not accounts:
        print("no scan_enabled AWS accounts registered — nothing to do")
        return

    failures = 0
    for account in accounts:
        if not args.dry_run:
            failures += scan_and_store(account, home_region, regions) is not None
            continue
        try:
            findings = scan_account(account, home_region, regions)
        except Exception as exc:  # noqa: BLE001 — isolate per-account failures
            failures += 1
            print(f"[{account.tenant_name}/{account.name}] scan FAILED: "
                  f"{type(exc).__name__}: {exc}"[:1000], file=sys.stderr)
            continue
        for finding in findings:
            print(finding.model_dump_json())

    if failures:
        sys.exit(f"{failures}/{len(accounts)} account scans failed")


if __name__ == "__main__":
    main()
