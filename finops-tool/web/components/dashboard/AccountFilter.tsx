"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { ChevronDown } from "lucide-react";

import type { AccountSummary } from "@/lib/api";

/** Narrows the whole overview to one AWS account via ?account=<number>. */
export function AccountFilter({ accounts }: { accounts: AccountSummary[] }) {
  const router = useRouter();
  const params = useSearchParams();
  const current = params.get("account") ?? "";

  function onChange(value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set("account", value);
    else next.delete("account");
    const qs = next.toString();
    router.push(qs ? `/dashboard?${qs}` : "/dashboard");
  }

  return (
    <label className="relative inline-flex items-center">
      <span className="sr-only">Filter by AWS account</span>
      <select
        value={current}
        onChange={(e) => onChange(e.target.value)}
        disabled={accounts.length === 0}
        className="h-9 appearance-none rounded-lg border bg-card py-0 pr-9 pl-3 text-sm font-medium shadow-xs outline-none transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-60"
      >
        <option value="">All accounts ({accounts.length})</option>
        {accounts.map((a) => (
          <option key={a.aws_account_number} value={a.aws_account_number}>
            {a.aws_account_name} · {a.aws_account_number}
          </option>
        ))}
      </select>
      <ChevronDown aria-hidden className="pointer-events-none absolute right-3 size-4 text-muted-foreground" />
    </label>
  );
}
