from pathlib import Path

import duckdb
import yaml

from services.common.models import Finding

CATALOG_DIR = Path(__file__).resolve().parents[2] / "rules" / "catalog"


def load_rules() -> list[dict]:
    rules = []
    for path in sorted(CATALOG_DIR.glob("*.yaml")):
        with open(path) as f:
            rules.append(yaml.safe_load(f))
    return rules


def run_rule(con: duckdb.DuckDBPyConnection, rule: dict, tenant_id: str) -> list[Finding]:
    """Execute one rule's query and turn each row into a Finding.

    The query contract (see CLAUDE.md): it must return `resource_id` and
    `monthly_savings_usd` columns. Every other column becomes evidence.
    """
    rows = con.execute(rule["query"]).fetchdf()
    findings = []
    for _, row in rows.iterrows():
        # .item() unwraps numpy scalars so evidence stays plain-JSON types.
        row_dict = {k: (v.item() if hasattr(v, "item") else v) for k, v in row.to_dict().items()}
        resource_id = str(row_dict.pop("resource_id"))
        monthly_savings_usd = float(row_dict.pop("monthly_savings_usd"))
        findings.append(
            Finding(
                tenant_id=tenant_id,
                resource_id=resource_id,
                rule_id=rule["id"],
                category=rule["category"],
                monthly_savings_usd=monthly_savings_usd,
                remediation_effort=rule["effort"],
                risk=rule["risk"],
                evidence=row_dict,
                # Templates may reference resource_id or any evidence column (e.g. {region}).
                remediation_action=rule["remediation_action_template"].format(
                    resource_id=resource_id, **row_dict
                ),
            )
        )
    return findings
