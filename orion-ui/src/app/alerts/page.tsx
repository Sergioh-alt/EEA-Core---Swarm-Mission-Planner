"use client";

import { PageShell } from "@/components/common/PageShell";
import { AlertBadge } from "@/components/common/AlertBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { useAlertStore } from "@/stores/alertStore";
import { formatTimestamp } from "@/lib/utils";
import { Bell } from "lucide-react";
import type { AlertSeverity } from "@/contracts/types";

const FILTER_OPTIONS: Array<{ label: string; value: AlertSeverity | "ALL" }> = [
  { label: "All", value: "ALL" },
  { label: "Critical", value: "CRITICAL" },
  { label: "Warning", value: "WARNING" },
  { label: "Info", value: "INFO" },
];

export default function AlertsPage() {
  const alerts = useAlertStore((s) => s.alerts);
  const filter = useAlertStore((s) => s.filter);
  const setFilter = useAlertStore((s) => s.setFilter);
  const markAllRead = useAlertStore((s) => s.markAllRead);

  const filteredAlerts = alerts.filter((alert) => {
    if (filter.severity !== "ALL" && alert.severity !== filter.severity) {
      return false;
    }
    if (filter.activeOnly && !alert.active) {
      return false;
    }
    return true;
  });

  return (
    <PageShell
      title="Alerts"
      description={`${alerts.length} total alerts`}
      actions={
        <button
          onClick={markAllRead}
          className="text-xs text-neutral-500 hover:text-neutral-300"
        >
          Mark all read
        </button>
      }
    >
      <div className="flex items-center gap-2 mb-4">
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setFilter({ severity: opt.value })}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              filter.severity === opt.value
                ? "bg-neutral-700 text-neutral-200"
                : "text-neutral-500 hover:text-neutral-300"
            }`}
          >
            {opt.label}
          </button>
        ))}
        <span className="mx-2 text-neutral-800">|</span>
        <button
          onClick={() => setFilter({ activeOnly: !filter.activeOnly })}
          className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
            filter.activeOnly
              ? "bg-neutral-700 text-neutral-200"
              : "text-neutral-500 hover:text-neutral-300"
          }`}
        >
          Active only
        </button>
      </div>

      {filteredAlerts.length === 0 ? (
        <EmptyState
          title="No alerts"
          description="No alerts match the current filter."
          icon={<Bell className="h-10 w-10" />}
        />
      ) : (
        <div className="space-y-2">
          {filteredAlerts.map((alert) => (
            <div
              key={alert.id}
              className={`rounded-lg border p-3 ${
                alert.active
                  ? "border-neutral-700 bg-neutral-900"
                  : "border-neutral-800 bg-neutral-950 opacity-60"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertBadge severity={alert.severity} />
                  <span className="text-sm text-neutral-300">
                    {alert.message}
                  </span>
                </div>
                <span className="text-xs font-mono text-neutral-600">
                  {formatTimestamp(alert.timestamp_ms)}
                </span>
              </div>
              <div className="flex items-center gap-4 mt-1 text-xs text-neutral-600">
                <span>Source: {alert.source}</span>
                <span>Category: {alert.category}</span>
                {!alert.active && alert.resolved_ms && (
                  <span>
                    Resolved: {formatTimestamp(alert.resolved_ms)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
}
