import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  hero = false,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon: LucideIcon;
  /** The one number the page leads with: larger figure, exactly one per view. */
  hero?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col rounded-xl border bg-card p-5 shadow-xs", className)}>
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <span
          className={cn(
            "flex size-6 items-center justify-center rounded-md",
            hero ? "bg-accent text-accent-foreground" : "bg-muted text-muted-foreground",
          )}
        >
          <Icon aria-hidden className="size-3.5" />
        </span>
        {label}
      </div>
      <div
        className={cn(
          "mt-4 font-semibold tracking-tight",
          hero ? "text-5xl leading-none" : "truncate text-2xl leading-tight sm:text-[28px]",
        )}
      >
        {value}
      </div>
      {hint ? <div className="mt-auto pt-3 text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  );
}
