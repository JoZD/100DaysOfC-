import type { AccountSummary, Finding } from "@/lib/api";

// Dashboard aggregates, derived from the API's /findings + /summary payloads so
// the account filter narrows every section consistently. Pure presentation
// math: savings figures come from the rules engine; nothing is re-estimated.

export interface BarDatum {
  key: string;
  label: string;
  sublabel?: string;
  value: number;
  count: number;
}

export interface ScanHealthCounts {
  ok: number;
  failed: number;
  never: number;
}

export interface DashboardInsights {
  accounts: AccountSummary[];
  findings: Finding[];
  monthlySavings: number;
  findingsCount: number;
  resourcesCount: number;
  topRule: BarDatum | null;
  byAccount: BarDatum[];
  byRule: BarDatum[];
  byCategory: BarDatum[];
  topOpportunities: Finding[];
  scanHealth: ScanHealthCounts;
  latestDetection: string | null;
}

function groupBy(
  findings: Finding[],
  keyOf: (f: Finding) => string,
  labelOf: (f: Finding) => string,
): BarDatum[] {
  const groups = new Map<string, BarDatum>();
  for (const f of findings) {
    const key = keyOf(f);
    const g = groups.get(key) ?? { key, label: labelOf(f), value: 0, count: 0 };
    g.value += f.monthly_savings_usd;
    g.count += 1;
    groups.set(key, g);
  }
  return [...groups.values()].sort((a, b) => b.value - a.value || b.count - a.count);
}

export function buildInsights(
  allAccounts: AccountSummary[],
  allFindings: Finding[],
  accountNumber: string | null,
): DashboardInsights {
  const accounts = accountNumber
    ? allAccounts.filter((a) => a.aws_account_number === accountNumber)
    : allAccounts;
  const findings = accountNumber
    ? allFindings.filter((f) => f.aws_account_number === accountNumber)
    : allFindings;

  const byRule = groupBy(findings, (f) => f.rule_id, (f) => f.rule_id);
  const byCategory = groupBy(findings, (f) => f.category, (f) => f.category);
  const byAccount: BarDatum[] = accounts
    .map((a) => ({
      key: a.aws_account_number,
      label: a.aws_account_name,
      sublabel: a.aws_account_number,
      value: a.monthly_savings_usd,
      count: a.findings_count,
    }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));

  const scanHealth: ScanHealthCounts = { ok: 0, failed: 0, never: 0 };
  for (const a of accounts) {
    if (!a.last_scan_at || a.last_scan_status === "running") scanHealth.never += 1;
    else if (a.last_scan_status === "failed") scanHealth.failed += 1;
    else scanHealth.ok += 1;
  }

  const latestDetection = findings.reduce<string | null>(
    (latest, f) => (latest === null || f.detected_at > latest ? f.detected_at : latest),
    null,
  );

  return {
    accounts,
    findings,
    monthlySavings: findings.reduce((sum, f) => sum + f.monthly_savings_usd, 0),
    findingsCount: findings.length,
    resourcesCount: new Set(findings.map((f) => `${f.aws_account_id}/${f.resource_id}`)).size,
    topRule: byRule[0] ?? null,
    byAccount,
    byRule,
    byCategory,
    // /findings is already sorted by savings, descending.
    topOpportunities: findings.slice(0, 5),
    scanHealth,
    latestDetection,
  };
}
