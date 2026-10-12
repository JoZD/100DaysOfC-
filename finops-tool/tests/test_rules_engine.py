import duckdb
import pandas as pd

from services.rules_engine.loader import run_rule


def test_orphaned_ebs_rule_generates_expected_savings():
    con = duckdb.connect(":memory:")
    con.register(
        "ec2_volumes",
        pd.DataFrame(
            [
                {"volume_id": "vol-1", "size_gb": 100, "volume_type": "gp3", "state": "available"},
                {"volume_id": "vol-2", "size_gb": 50, "volume_type": "gp3", "state": "in-use"},
            ]
        ),
    )

    rule = {
        "id": "orphaned_ebs_volumes",
        "category": "waste",
        "risk": "low",
        "effort": "low",
        "remediation_action_template": "aws ec2 delete-volume --volume-id {resource_id}",
        "query": """
            SELECT volume_id AS resource_id, size_gb, volume_type,
                   ROUND(size_gb * 0.08, 2) AS monthly_savings_usd
            FROM ec2_volumes
            WHERE state = 'available'
        """,
    }

    findings = run_rule(con, rule, tenant_id="tenant-1")

    assert len(findings) == 1
    assert findings[0].resource_id == "vol-1"
    assert findings[0].monthly_savings_usd == 8.0
    assert findings[0].tenant_id == "tenant-1"
