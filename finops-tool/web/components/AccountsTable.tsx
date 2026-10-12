import type { AccountSummary } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { StatusPill } from "@/components/dashboard/primitives";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const dateTime = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

function ScanStatus({ account }: { account: AccountSummary }) {
  if (account.last_scan_status === "running") {
    return <StatusPill tone="warning">Scanning…</StatusPill>;
  }
  if (!account.verified_at) {
    return <StatusPill tone="neutral">Setup pending</StatusPill>;
  }
  if (!account.last_scan_at) {
    return <StatusPill tone="neutral">Never scanned</StatusPill>;
  }
  const failed = account.last_scan_status === "failed";
  return (
    <span className="flex flex-wrap items-center gap-2">
      <StatusPill tone={failed ? "critical" : "good"}>{failed ? "Failed" : "Healthy"}</StatusPill>
      <span className="text-xs text-muted-foreground">
        {dateTime.format(new Date(account.last_scan_at))} UTC
      </span>
    </span>
  );
}

export function AccountsTable({ accounts }: { accounts: AccountSummary[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-5 text-xs font-medium tracking-wide text-muted-foreground uppercase">Account</TableHead>
          <TableHead className="text-xs font-medium tracking-wide text-muted-foreground uppercase">AWS account</TableHead>
          <TableHead className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Scan status</TableHead>
          <TableHead className="text-right text-xs font-medium tracking-wide text-muted-foreground uppercase">Findings</TableHead>
          <TableHead className="pr-5 text-right text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Monthly savings
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {accounts.map((a) => (
          <TableRow key={a.aws_account_id}>
            <TableCell className="py-3 pl-5 font-medium">
              <a href={`/dashboard/accounts/${a.aws_account_id}`} className="hover:underline">
                {a.aws_account_name}
              </a>
            </TableCell>
            <TableCell className="font-mono text-xs text-muted-foreground">{a.aws_account_number}</TableCell>
            <TableCell>
              <ScanStatus account={a} />
            </TableCell>
            <TableCell className="text-right tabular-nums">{a.findings_count}</TableCell>
            <TableCell className="pr-5 text-right font-medium tabular-nums">
              {formatUsd(a.monthly_savings_usd)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
