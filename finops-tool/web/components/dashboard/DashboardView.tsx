import { Suspense } from "react";
import {
  Building2,
  CalendarRange,
  CircleDollarSign,
  Clock,
  Cloud,
  Plus,
  ListChecks,
  Receipt,
  SearchCheck,
  Trophy,
} from "lucide-react";

import type { Finding, Summary } from "@/lib/api";
import { formatUsd, humanizeRuleId } from "@/lib/format";
import { buildInsights } from "@/lib/insights";
import { AppShell, type ViewUser } from "@/components/app/AppShell";
import { WorkspaceForm } from "@/components/accounts/forms";
import { Button } from "@/components/ui/button";
import { AccountsTable } from "@/components/AccountsTable";
import { FindingsTable } from "@/components/FindingsTable";
import { AccountFilter } from "@/components/dashboard/AccountFilter";
import { BarList } from "@/components/dashboard/BarList";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { ScanHealth } from "@/components/dashboard/ScanHealth";
import { TopOpportunities } from "@/components/dashboard/TopOpportunities";
import { EmptyState, PageHeader, SectionCard } from "@/components/dashboard/primitives";

const asOf = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

const PAGE_TITLE = "Overview";
const PAGE_DESCRIPTION = "Savings opportunities across your AWS accounts, ranked by monthly impact.";

export type { ViewUser };

/** Shown when the signed-in user has no workspace yet (API 404). */
export function NotConnectedView({ user }: { user: ViewUser }) {
  return (
    <AppShell user={user}>
      <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} />
      <SectionCard
        title="Create your workspace"
        description="Your user is not part of a workspace yet. Create one, or ask the operator to add you to an existing one."
      >
        <div className="py-2">
          <WorkspaceForm />
        </div>
      </SectionCard>
    </AppShell>
  );
}

export function DashboardView({
  user,
  summary,
  findings,
  accountFilter,
}: {
  user: ViewUser;
  summary: Summary;
  findings: Finding[];
  accountFilter: string | null;
}) {
  const insights = buildInsights(summary.by_account, findings, accountFilter);
  const hasAccounts = summary.by_account.length > 0;
  const hasFindings = insights.findingsCount > 0;
  const scopeLabel = accountFilter
    ? (insights.accounts[0]?.aws_account_name ?? accountFilter)
    : `${insights.accounts.length} AWS account${insights.accounts.length === 1 ? "" : "s"}`;

  const actions = (
    <>
      {insights.latestDetection ? (
        <span className="inline-flex h-9 items-center gap-2 rounded-lg border bg-card px-3 text-sm text-muted-foreground shadow-xs">
          <Clock aria-hidden className="size-4" />
          Data as of {asOf.format(new Date(insights.latestDetection))} UTC
        </span>
      ) : null}
      <Suspense>
        <AccountFilter accounts={summary.by_account} />
      </Suspense>
    </>
  );

  if (!hasAccounts) {
    return (
      <AppShell user={user} active="overview">
        <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} actions={actions} />
        <SectionCard title="Connect your first AWS account" description="FinOps Tool has nothing to analyze yet.">
          <EmptyState icon={Cloud} title="No AWS accounts connected yet" className="min-h-64">
            <p>Connect an account: we generate the read-only IAM role to create, verify it, and run the first scan.</p>
            <div className="mt-4">
              <Button size="lg" nativeButton={false} render={<a href="/dashboard/accounts/new" />}>
                <Plus aria-hidden />
                Connect AWS account
              </Button>
            </div>
          </EmptyState>
        </SectionCard>
      </AppShell>
    );
  }

  const accountsSection = (
    <SectionCard
      id="accounts"
      title="AWS accounts"
      description="Scan status and savings per connected account."
      action={<ScanHealth counts={insights.scanHealth} />}
      bodyClassName="px-0 py-0"
    >
      <AccountsTable accounts={insights.accounts} />
    </SectionCard>
  );

  const kpis = (
    <section aria-label="Key metrics" className="grid grid-cols-2 gap-4 lg:grid-cols-6">
      <KpiCard
        hero
        className="col-span-2"
        icon={CircleDollarSign}
        label="Estimated monthly savings"
        value={formatUsd(insights.monthlySavings)}
        hint={`If every open finding in ${scopeLabel} is remediated`}
      />
      <KpiCard
        icon={CalendarRange}
        label="Annualized"
        value={formatUsd(insights.monthlySavings * 12)}
        hint="Monthly savings × 12"
      />
      <KpiCard
        icon={ListChecks}
        label="Open findings"
        value={insights.findingsCount}
        hint={`${insights.resourcesCount} resource${insights.resourcesCount === 1 ? "" : "s"} affected`}
      />
      <KpiCard
        icon={Trophy}
        label="Top rule"
        value={insights.topRule ? formatUsd(insights.topRule.value) : "—"}
        hint={insights.topRule ? humanizeRuleId(insights.topRule.key) : "No findings yet"}
      />
      <KpiCard
        icon={Building2}
        label="AWS accounts"
        value={insights.accounts.length}
        hint={
          insights.scanHealth.failed > 0
            ? `${insights.scanHealth.failed} failing scan${insights.scanHealth.failed === 1 ? "" : "s"}`
            : `${insights.byAccount.filter((a) => a.count > 0).length} with findings`
        }
      />
    </section>
  );

  if (!hasFindings) {
    return (
      <AppShell user={user} active="overview">
        <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} actions={actions} />
        {kpis}
        <SectionCard id="findings" title="Findings" description="Savings opportunities detected by the rules engine.">
          <EmptyState icon={SearchCheck} title="No findings yet" className="min-h-56">
            <p>
              Nothing to optimize in {scopeLabel}, or it hasn&apos;t been scanned yet. Findings appear after
              the next successful scan.
            </p>
          </EmptyState>
        </SectionCard>
        {accountsSection}
      </AppShell>
    );
  }

  return (
    <AppShell user={user} active="overview">
      <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} actions={actions} />
      {kpis}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <SectionCard
          className="lg:col-span-2"
          title="Savings by account"
          description="Estimated monthly savings per connected account."
        >
          <BarList data={insights.byAccount} />
        </SectionCard>
        <SectionCard title="Savings by rule" description="Which detections are worth the most.">
          <BarList data={insights.byRule} formatLabel={(d) => humanizeRuleId(d.key)} />
        </SectionCard>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <SectionCard
          className="lg:col-span-2"
          title="Top opportunities"
          description="The highest-value actions right now. Open one to see its evidence and fix."
          action={
            <a href="#findings" className="text-sm font-medium text-primary hover:underline">
              View all findings
            </a>
          }
        >
          <TopOpportunities findings={insights.topOpportunities} />
        </SectionCard>
        <SectionCard title="Actual spend" description="Billed cost by service and account.">
          <EmptyState icon={Receipt} title="Cost data not connected yet">
            Real spend appears here once Cost &amp; Usage Report ingestion is enabled.
          </EmptyState>
        </SectionCard>
      </div>

      {accountsSection}

      <SectionCard
        id="findings"
        title="Findings"
        description="Read-only detections sorted by estimated monthly savings. Click a row for evidence and the remediation command."
        bodyClassName="px-0 py-0"
        action={
          <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">
            {insights.findingsCount} open
          </span>
        }
      >
        <FindingsTable findings={insights.findings} />
      </SectionCard>
    </AppShell>
  );
}
