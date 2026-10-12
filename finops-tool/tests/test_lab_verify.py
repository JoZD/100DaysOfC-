"""scripts.lab_verify compares Terraform's lab output with stored findings."""

from scripts.lab_verify import verify

LAB = {
    "aws_account_id": "222222222222",
    "expected_findings": [
        {"rule_id": "orphaned_ebs_volumes", "resource_id": "vol-1", "region": "us-east-1",
         "monthly_savings_usd": 0.08},
        {"rule_id": "unassociated_eips", "resource_id": "eipalloc-1", "region": "us-east-1",
         "monthly_savings_usd": 3.6},
    ],
    "controls": [{"rule_id": "unassociated_eips", "resource_id": "eipalloc-ctl",
                  "region": "us-east-1"}],
}
ACCOUNT = {"role_arn": "arn:aws:iam::222222222222:role/FinOps-ReadOnly",
           "last_scan_status": "ok", "last_scan_error": None}


def finding(rule_id, resource_id, savings):
    return {(rule_id, resource_id): {"monthly_savings_usd": savings}}


def test_passes_when_expected_found_and_controls_clean():
    findings = {**finding("orphaned_ebs_volumes", "vol-1", 0.08),
                **finding("unassociated_eips", "eipalloc-1", 3.6),
                **finding("orphaned_ebs_volumes", "vol-preexisting", 1.0)}
    assert verify(LAB, ACCOUNT, findings) == []


def test_reports_missing_wrong_savings_flagged_control_and_account_mismatch():
    findings = {**finding("orphaned_ebs_volumes", "vol-1", 0.10),
                **finding("unassociated_eips", "eipalloc-ctl", 3.6)}
    account = {**ACCOUNT, "role_arn": "arn:aws:iam::333333333333:role/FinOps-ReadOnly",
               "last_scan_status": "failed", "last_scan_error": "AccessDenied"}
    errors = verify(LAB, account, findings)
    assert any("333333333333" in e for e in errors)
    assert any("failed: AccessDenied" in e for e in errors)
    assert any(e.startswith("SAVINGS") and "vol-1" in e for e in errors)
    assert any(e.startswith("MISSING") and "eipalloc-1" in e for e in errors)
    assert any(e.startswith("FLAGGED") and "eipalloc-ctl" in e for e in errors)
