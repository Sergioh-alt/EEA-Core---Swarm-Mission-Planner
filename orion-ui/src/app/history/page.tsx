"use client";

/**
 * Execution history (Phase 10D.7).
 *
 * Past and ongoing executions of saved missions, kept strictly apart from the
 * Mission Library: planned figures come from the executed Mission Package and
 * runtime figures are mirrored from the Digital Twin, which stays the source
 * of truth for anything running.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { History } from "lucide-react";
import { PageShell } from "@/components/common/PageShell";
import { EmptyState } from "@/components/common/EmptyState";
import { getPipelineClient } from "@/lib/pipelineClient";
import type { ExecutionRecord } from "@/contracts/mission";

const STATUS_STYLES: Record<string, string> = {
  running: "border-blue-800 text-blue-300",
  completed: "border-emerald-800 text-emerald-300",
  interrupted: "border-amber-800 text-amber-300",
};

/** Poll while an execution is open, so the record closes in front of the operator. */
const REFRESH_MS = 3000;

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

export default function HistoryPage() {
  const [records, setRecords] = useState<ExecutionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRecords(await getPipelineClient().listExecutions());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  return (
    <PageShell
      title="Execution History"
      description="Executions of saved missions — separate from the reusable Mission Library"
      actions={
        <Link
          href="/library"
          className="rounded-md border border-neutral-700 px-2.5 py-1.5 text-[11px] text-neutral-300 transition-colors hover:bg-neutral-800"
        >
          Mission Library
        </Link>
      }
    >
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-400"
        >
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-xs text-neutral-500">Loading execution history…</p>
      ) : records.length === 0 ? (
        <EmptyState
          icon={<History className="h-8 w-8" />}
          title="No executions yet"
          description="Execute a saved mission — or wait for a schedule — and its record appears here."
        />
      ) : (
        <div className="space-y-3">
          {records.map((record) => (
            <div
              key={record.execution_id}
              className="rounded-lg border border-neutral-800 bg-neutral-900 p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  href={`/library/${record.entry_id}`}
                  className="text-sm font-medium text-neutral-100 hover:text-blue-300"
                >
                  {record.mission_name}
                </Link>
                <span
                  className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${
                    STATUS_STYLES[record.status] ?? STATUS_STYLES.running
                  }`}
                >
                  {record.status}
                </span>
                <span className="rounded border border-neutral-700 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-neutral-400">
                  {record.trigger}
                </span>
              </div>

              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-neutral-500">
                <span>{new Date(record.started_ms).toLocaleString()}</span>
                <span>{record.field_name || "—"}</span>
                <span>{record.operation_type || "—"}</span>
                <span>{record.products.join(", ") || "no products"}</span>
                <span>{record.drone_count} drones</span>
                <span>{record.route_count} routes</span>
                <span>duration {formatDuration(record.duration_ms)}</span>
              </div>

              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-neutral-400">
                {record.planned.coverage_pct !== null && (
                  <span>planned coverage {record.planned.coverage_pct.toFixed(1)} %</span>
                )}
                {record.planned.duration_formatted && (
                  <span>planned {record.planned.duration_formatted}</span>
                )}
                {record.planned.total_liquid_l !== null && (
                  <span>{record.planned.total_liquid_l.toFixed(1)} L</span>
                )}
                {record.planned.total_battery_cycles !== null && (
                  <span>{record.planned.total_battery_cycles} battery cycles</span>
                )}
                {record.planned.area_ha !== null && (
                  <span>{record.planned.area_ha.toFixed(2)} ha</span>
                )}
                {typeof record.runtime.progress === "number" && (
                  <span>
                    runtime progress {(record.runtime.progress * 100).toFixed(0)} %
                  </span>
                )}
              </div>

              {record.runtime.last_event && (
                <p className="mt-1 text-[11px] text-neutral-500">
                  {record.runtime.last_event}
                </p>
              )}
              {record.warnings.map((warning) => (
                <p key={warning} className="mt-1 text-[11px] text-amber-400">
                  {warning}
                </p>
              ))}
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
}
