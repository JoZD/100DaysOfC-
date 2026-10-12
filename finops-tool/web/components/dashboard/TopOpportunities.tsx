import { ArrowRight } from "lucide-react";

import type { Finding } from "@/lib/api";
import { formatUsd, humanizeRuleId } from "@/lib/format";

export function TopOpportunities({ findings }: { findings: Finding[] }) {
  return (
    <ol className="-my-2 divide-y">
      {findings.map((f, i) => (
        <li key={f.id}>
          <a
            href={`#finding-row-${f.id}`}
            className="group flex items-center gap-3 rounded-md py-2.5 transition-colors hover:bg-muted/60"
          >
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium tabular-nums text-muted-foreground">
              {i + 1}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-mono text-xs">{f.resource_id}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {humanizeRuleId(f.rule_id)} · {f.aws_account_name}
                {typeof f.evidence.region === "string" ? ` · ${f.evidence.region}` : ""}
              </span>
            </span>
            <span className="shrink-0 text-sm font-medium tabular-nums">
              {formatUsd(f.monthly_savings_usd)}
              <span className="text-xs font-normal text-muted-foreground">/mo</span>
            </span>
            <ArrowRight
              aria-hidden
              className="size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
            />
          </a>
        </li>
      ))}
    </ol>
  );
}
