"""Read-only VM/AssumeRole diagnostic — the same check as the dashboard's "Verify".

Prints identity ARNs and region names, never credentials or AWS bodies.
Does not collect inventory, write findings or change scan status.

  python -m scripts.check_aws_access                              # VM identity only
  python -m scripts.check_aws_access --tenant acme --account prod
"""

import argparse

from services.api.db import SessionLocal
from services.common import aws_access
from services.rules_engine.store import list_scan_targets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tenant")
    parser.add_argument("--account")
    args = parser.parse_args()
    if bool(args.tenant) != bool(args.account):
        parser.error("--tenant and --account go together")

    if not args.account:
        source = aws_access.source_identity()
        print(f"VM identity: {source.caller_arn}")
        print(f"Trust principal: {source.principal_arn or source.principal_arn_pattern}")
        return

    with SessionLocal() as db:
        account, = list_scan_targets(db, args.tenant, args.account)
    result = aws_access.verify_target(account.role_arn, account.external_id, "finops-check")
    print(f"VM identity: {result.source_arn or '-'}")
    if not result.ok:
        raise SystemExit(f"FAILED at {result.stage}: {result.error}\nhint: {result.hint}")
    print(f"Target identity account: {result.target_account}")
    print(f"Enabled regions: {', '.join(result.regions)}")


if __name__ == "__main__":
    main()
