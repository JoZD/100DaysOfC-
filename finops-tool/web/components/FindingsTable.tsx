"use client";

import { Fragment, useEffect, useState } from "react";
import { ChevronRight } from "lucide-react";

import type { Finding } from "@/lib/api";
import { formatUsd, humanizeRuleId } from "@/lib/format";
import { CopyButton } from "@/components/CopyButton";
import { StatusPill } from "@/components/dashboard/primitives";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// Risk is a state, so it wears the reserved status palette (label first, dot
// second). Effort is not good/bad, so it stays neutral.
const RISK_TONE = { low: "good", medium: "warning", high: "critical" } as const;

const COLUMN_COUNT = 9;
const ROW_ID_PREFIX = "finding-row-";

const HEAD = "text-xs font-medium tracking-wide text-muted-foreground uppercase";

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatEvidence(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function FindingDetail({ finding }: { finding: Finding }) {
  const evidence = Object.entries(finding.evidence);
  return (
    <div className="grid gap-6 py-2 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
      <section aria-label="Evidence">
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Evidence
        </h3>
        {evidence.length === 0 ? (
          <p className="text-sm text-muted-foreground">No evidence recorded.</p>
        ) : (
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            {evidence.map(([key, value]) => (
              <Fragment key={key}>
                <dt className="text-muted-foreground">{key}</dt>
                <dd className="break-all font-mono text-xs leading-5">{formatEvidence(value)}</dd>
              </Fragment>
            ))}
          </dl>
        )}
      </section>
      <section aria-label="Remediation">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Remediation
          </h3>
          <CopyButton text={finding.remediation_action} label="Copy command" />
        </div>
        <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded-lg border bg-muted/50 p-3 font-mono text-xs">
          {finding.remediation_action}
        </pre>
        <p className="mt-2 text-xs text-muted-foreground">
          FinOps Tool never runs this. Review it and run it yourself.
        </p>
      </section>
    </div>
  );
}

export function FindingsTable({ findings }: { findings: Finding[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Deep links (#finding-row-<id>, e.g. from "Top opportunities") open that row.
  useEffect(() => {
    function openFromHash() {
      const hash = decodeURIComponent(window.location.hash.slice(1));
      if (!hash.startsWith(ROW_ID_PREFIX)) return;
      const id = hash.slice(ROW_ID_PREFIX.length);
      setExpanded((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));
    }
    openFromHash();
    window.addEventListener("hashchange", openFromHash);
    return () => window.removeEventListener("hashchange", openFromHash);
  }, []);

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-10 pl-4">
            <span className="sr-only">Details</span>
          </TableHead>
          <TableHead className={HEAD}>Account</TableHead>
          <TableHead className={HEAD}>Region</TableHead>
          <TableHead className={HEAD}>Resource</TableHead>
          <TableHead className={HEAD}>Rule</TableHead>
          <TableHead className={HEAD}>Category</TableHead>
          <TableHead className={`text-right ${HEAD}`}>Monthly savings</TableHead>
          <TableHead className={HEAD}>Effort</TableHead>
          <TableHead className={`pr-5 ${HEAD}`}>Risk</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {findings.map((f) => {
          const isOpen = expanded.has(f.id);
          const detailId = `finding-${f.id}`;
          return (
            <Fragment key={f.id}>
              <TableRow
                id={`${ROW_ID_PREFIX}${f.id}`}
                className="cursor-pointer"
                data-state={isOpen ? "selected" : undefined}
                onClick={() => toggle(f.id)}
              >
                <TableCell className="pl-4">
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={detailId}
                    aria-label={isOpen ? "Hide details" : "Show details"}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggle(f.id);
                    }}
                    className="flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <ChevronRight
                      aria-hidden
                      className={`size-4 transition-transform ${isOpen ? "rotate-90" : ""}`}
                    />
                  </button>
                </TableCell>
                <TableCell className="py-3">
                  <div className="font-medium">{f.aws_account_name}</div>
                  <div className="font-mono text-xs text-muted-foreground">{f.aws_account_number}</div>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {typeof f.evidence.region === "string" ? f.evidence.region : "—"}
                </TableCell>
                <TableCell className="font-mono text-xs">{f.resource_id}</TableCell>
                <TableCell>{humanizeRuleId(f.rule_id)}</TableCell>
                <TableCell className="text-muted-foreground">{capitalize(f.category)}</TableCell>
                <TableCell className="text-right font-medium tabular-nums">
                  {formatUsd(f.monthly_savings_usd)}
                </TableCell>
                <TableCell className="text-muted-foreground">{capitalize(f.remediation_effort)}</TableCell>
                <TableCell className="pr-5">
                  <StatusPill tone={RISK_TONE[f.risk]}>{capitalize(f.risk)}</StatusPill>
                </TableCell>
              </TableRow>
              {isOpen ? (
                <TableRow id={detailId} className="hover:bg-transparent">
                  <TableCell colSpan={COLUMN_COUNT} className="whitespace-normal bg-muted/30 px-5">
                    <FindingDetail finding={f} />
                  </TableCell>
                </TableRow>
              ) : null}
            </Fragment>
          );
        })}
      </TableBody>
    </Table>
  );
}
