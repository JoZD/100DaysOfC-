import { CircleAlert, CircleCheck, CircleDashed, type LucideIcon } from "lucide-react";

import type { ScanHealthCounts } from "@/lib/insights";
import { cn } from "@/lib/utils";

// Status colors ship with an icon + label, never color alone.
const ITEMS: {
  key: keyof ScanHealthCounts;
  label: string;
  title: string;
  icon: LucideIcon;
  tone: string;
}[] = [
  { key: "ok", label: "healthy", title: "Last live scan succeeded", icon: CircleCheck, tone: "text-status-good" },
  { key: "failed", label: "failing", title: "Last live scan errored", icon: CircleAlert, tone: "text-status-critical" },
  {
    key: "never",
    label: "never scanned",
    title: "No scan has run yet",
    icon: CircleDashed,
    tone: "text-muted-foreground",
  },
];

/** Compact scan-health summary: one chip per state, zero states dimmed. */
export function ScanHealth({ counts }: { counts: ScanHealthCounts }) {
  return (
    <ul aria-label="Scan health" className="flex flex-wrap items-center gap-2">
      {ITEMS.map(({ key, label, title, icon: Icon, tone }) => {
        const n = counts[key];
        return (
          <li
            key={key}
            title={title}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 text-xs",
              n === 0 && "text-muted-foreground",
            )}
          >
            <Icon aria-hidden className={cn("size-3.5", n > 0 ? tone : "text-muted-foreground/50")} />
            <span className="font-semibold tabular-nums">{n}</span>
            {label}
          </li>
        );
      })}
    </ul>
  );
}
