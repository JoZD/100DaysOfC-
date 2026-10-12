import { Cloud, Plus } from "lucide-react";

import { ApiError, fetchAccounts } from "@/lib/api";
import { AppShell } from "@/components/app/AppShell";
import { AccountStatusPill, dateTime } from "@/components/accounts/shared";
import { AutoRefresh } from "@/components/accounts/forms";
import { NotConnectedView } from "@/components/dashboard/DashboardView";
import { EmptyState, PageHeader, SectionCard } from "@/components/dashboard/primitives";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { requireSession } from "@/lib/session";

const head = "text-xs font-medium tracking-wide text-muted-foreground uppercase";

export default async function AccountsPage() {
  const session = await requireSession();
  const accessToken = session.token;
  const user = { email: session.email, name: null };

  let accounts;
  try {
    accounts = await fetchAccounts(accessToken);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404)) {
      return <NotConnectedView user={user} />;
    }
    throw err;
  }

  const addButton = (
    <Button size="lg" nativeButton={false} render={<a href="/dashboard/accounts/new" />}>
      <Plus aria-hidden />
      Connect AWS account
    </Button>
  );

  return (
    <AppShell user={user} active="accounts">
      <AutoRefresh active={accounts.some((a) => a.last_scan_status === "running")} />
      <PageHeader
        title="AWS accounts"
        description="Each account is read through its own read-only IAM role, assumed with a unique ExternalId."
        actions={addButton}
      />
      <SectionCard title="Connected accounts" bodyClassName={accounts.length ? "px-0 py-0" : undefined}>
        {accounts.length === 0 ? (
          <EmptyState icon={Cloud} title="No AWS accounts connected yet" className="min-h-64">
            <p>Connect one to create its read-only role and run the first scan.</p>
          </EmptyState>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className={`pl-5 ${head}`}>Account</TableHead>
                <TableHead className={head}>AWS account ID</TableHead>
                <TableHead className={head}>Status</TableHead>
                <TableHead className={head}>Last scan</TableHead>
                <TableHead className={`pr-5 text-right ${head}`}>
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts.map((a) => (
                <TableRow key={a.id}>
                  <TableCell className="py-3 pl-5 font-medium">
                    <a href={`/dashboard/accounts/${a.id}`} className="hover:underline">
                      {a.name}
                    </a>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{a.aws_account_number}</TableCell>
                  <TableCell>
                    <AccountStatusPill account={a} />
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {a.last_scan_at && a.last_scan_status !== "running"
                      ? `${dateTime.format(new Date(a.last_scan_at))} UTC`
                      : "—"}
                  </TableCell>
                  <TableCell className="pr-5 text-right">
                    <Button variant="outline" size="sm" nativeButton={false} render={<a href={`/dashboard/accounts/${a.id}`} />}>
                      {a.verified_at ? "Manage" : "Finish setup"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </SectionCard>
    </AppShell>
  );
}
