import type { BarDatum } from "@/lib/insights";
import { formatUsd } from "@/lib/format";

/**
 * Single-series horizontal bar list (magnitude → one hue). Values are labeled
 * at the row end, so identity and amount never depend on color; the native
 * title tooltip repeats label, savings and finding count on hover.
 */
export function BarList({
  data,
  formatLabel = (d) => d.label,
  countNoun = "finding",
}: {
  data: BarDatum[];
  formatLabel?: (d: BarDatum) => string;
  countNoun?: string;
}) {
  const max = Math.max(...data.map((d) => d.value), 0);
  return (
    <ul className="flex flex-col gap-4">
      {data.map((d) => {
        const label = formatLabel(d);
        const pct = max > 0 ? (d.value / max) * 100 : 0;
        const count = `${d.count} ${countNoun}${d.count === 1 ? "" : "s"}`;
        return (
          <li key={d.key} title={`${label}: ${formatUsd(d.value)}/mo · ${count}`}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate">
                <span className="font-medium">{label}</span>
                {d.sublabel ? (
                  <span className="ml-2 font-mono text-xs text-muted-foreground">{d.sublabel}</span>
                ) : null}
              </span>
              <span className="shrink-0 tabular-nums">
                <span className="font-medium">{formatUsd(d.value)}</span>
                <span className="ml-2 text-xs text-muted-foreground">{count}</span>
              </span>
            </div>
            <div className="h-2 w-full rounded-r bg-chart-track">
              <div
                className="h-full rounded-r bg-chart-1"
                style={{ width: d.value > 0 ? `max(${pct}%, 2px)` : 0 }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
