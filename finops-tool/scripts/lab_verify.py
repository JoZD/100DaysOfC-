"""Check a real scan against the waste lab Terraform created (infra/envs/lab).

  terraform -chdir=infra/envs/lab output -json lab > /tmp/lab-a.json
  docker compose run --rm -T api python -m scripts.lab_verify \\
      --tenant <workspace> --account <name> < /tmp/lab-a.json

Passes when every expected resource has a finding with the expected savings and
no control resource is flagged. Findings for other resources already in the
account are listed but do not fail the check. Reads the DB only; no AWS calls.
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

from services.api.db import SessionLocal
from services.rules_engine.store import set_tenant_context


def load_findings(db, tenant: str, account: str) -> tuple[dict, dict]:
    tenant_id = db.execute(text("SELECT id FROM tenants WHERE name = :n"), {"n": tenant}).scalar()
    if tenant_id is None:
        raise SystemExit(f"no tenant named {tenant!r} — see: python -m scripts.admin list")
    set_tenant_context(db, tenant_id)
    row = db.execute(
        text(
            "SELECT id, role_arn, last_scan_at, last_scan_status, last_scan_error "
            "FROM aws_accounts WHERE tenant_id = :t AND name = :n"
        ),
        {"t": str(tenant_id), "n": account},
    ).mappings().first()
    if row is None:
        raise SystemExit(f"no account {account!r} in tenant {tenant!r}")
    findings = db.execute(
        text(
            "SELECT rule_id, resource_id, monthly_savings_usd, evidence FROM findings "
            "WHERE tenant_id = :t AND aws_account_id = :a"
        ),
        {"t": str(tenant_id), "a": str(row["id"])},
    ).mappings().all()
    db.commit()
    return dict(row), {(f["rule_id"], f["resource_id"]): dict(f) for f in findings}


def verify(lab: dict, account: dict, findings: dict) -> list[str]:
    errors: list[str] = []
    registered = account["role_arn"].split(":")[4]
    if registered != lab["aws_account_id"]:
        errors.append(f"lab is in account {lab['aws_account_id']}, "
                      f"but the registered role is in {registered}")
    if account["last_scan_status"] != "ok":
        errors.append(f"last scan status is {account['last_scan_status'] or 'never scanned'}"
                      + (f": {account['last_scan_error']}" if account["last_scan_error"] else ""))

    expected_keys = set()
    for exp in lab["expected_findings"]:
        key = (exp["rule_id"], exp["resource_id"])
        expected_keys.add(key)
        found = findings.get(key)
        if found is None:
            errors.append(f"MISSING  {exp['rule_id']:<22} {exp['resource_id']} ({exp['region']})")
            continue
        savings = float(found["monthly_savings_usd"])
        if abs(savings - float(exp["monthly_savings_usd"])) > 0.01:
            errors.append(f"SAVINGS  {exp['resource_id']}: stored ${savings:.2f}, "
                          f"expected ${float(exp['monthly_savings_usd']):.2f}")
        else:
            print(f"ok       {exp['rule_id']:<22} {exp['resource_id']} ${savings:.2f}/mo")

    for ctl in lab["controls"]:
        if (ctl["rule_id"], ctl["resource_id"]) in findings:
            errors.append(f"FLAGGED  control {ctl['resource_id']} must not be a "
                          f"{ctl['rule_id']} finding")
        else:
            print(f"ok       control {ctl['resource_id']} not flagged")

    for rule_id, resource_id in sorted(findings.keys() - expected_keys):
        print(f"other    {rule_id:<22} {resource_id} (not created by the lab)")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tenant", required=True, help="workspace name (scripts.admin list)")
    parser.add_argument("--account", required=True, help="account name in FinOps Tool")
    parser.add_argument("--file", help="terraform output -json lab (default: stdin)")
    args = parser.parse_args()

    raw = Path(args.file).read_text() if args.file else sys.stdin.read()
    lab = json.loads(raw)
    db = SessionLocal()
    try:
        account, findings = load_findings(db, args.tenant, args.account)
    finally:
        db.close()

    scanned = account["last_scan_at"]
    last = f"{scanned:%Y-%m-%d %H:%M} UTC" if scanned else "never"
    print(f"account {args.tenant}/{args.account}: last scan {last}")
    errors = verify(lab, account, findings)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        sys.exit(f"lab verification FAILED ({len(errors)} problem(s))")
    print(f"lab verification passed: {len(lab['expected_findings'])} expected findings, "
          f"{len(lab['controls'])} controls")


if __name__ == "__main__":
    main()
