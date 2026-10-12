import type { ReactNode } from "react";

import type { AwsAccount } from "@/lib/api";
import { CopyButton } from "@/components/CopyButton";
import { StatusPill } from "@/components/dashboard/primitives";

export const dateTime = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

type Status = { tone: "good" | "warning" | "serious" | "critical" | "neutral"; label: string };

export function accountStatus(a: Pick<AwsAccount, "verified_at" | "scan_enabled" | "last_scan_status" | "last_scan_at">): Status {
  if (a.last_scan_status === "running") return { tone: "warning", label: "Scanning…" };
  if (!a.verified_at) return { tone: "neutral", label: "Setup pending" };
  if (!a.scan_enabled) return { tone: "neutral", label: "Paused" };
  if (a.last_scan_status === "failed") return { tone: "critical", label: "Last scan failed" };
  if (a.last_scan_status === "ok") return { tone: "good", label: "Healthy" };
  return { tone: "good", label: "Connected" };
}

export function AccountStatusPill({ account }: { account: Parameters<typeof accountStatus>[0] }) {
  const s = accountStatus(account);
  return <StatusPill tone={s.tone}>{s.label}</StatusPill>;
}

/** Monospace block with a copy button; content stays selectable. */
export function CodeBlock({ code, label }: { code: string; label?: string }) {
  return (
    <div className="overflow-hidden rounded-lg border bg-muted/40">
      <div className="flex items-center justify-between gap-2 border-b bg-card px-3 py-1.5">
        <span className="text-xs font-medium text-muted-foreground">{label ?? ""}</span>
        <CopyButton text={code} />
      </div>
      <pre className="max-h-96 overflow-auto px-3 py-2.5 font-mono text-[12px] leading-relaxed whitespace-pre">
        {code}
      </pre>
    </div>
  );
}

export function Step({
  n,
  title,
  done,
  children,
}: {
  n: number;
  title: string;
  done?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="flex gap-4 rounded-xl border bg-card px-5 py-5 shadow-xs">
      <span
        aria-hidden
        className={
          "flex size-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold " +
          (done ? "bg-status-good text-white" : "bg-primary/10 text-primary")
        }
      >
        {done ? "✓" : n}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <h2 className="text-[15px] font-semibold tracking-tight">
          <span className="sr-only">Step {n}: </span>
          {title}
        </h2>
        {children}
      </div>
    </section>
  );
}
