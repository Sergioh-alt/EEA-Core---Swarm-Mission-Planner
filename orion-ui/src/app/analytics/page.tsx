"use client";

import { PageShell } from "@/components/common/PageShell";


export default function AnalyticsPage() {
  return (
    <PageShell
      title="Analytics"
      description="Mission and fleet performance analytics"
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Mission History
          </h2>
          <div className="flex items-center justify-center h-48 border border-dashed border-neutral-800 rounded-md text-neutral-600">
            <p className="text-xs">
              Mission history chart will render from Digital Twin snapshots.
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Fleet Performance
          </h2>
          <div className="flex items-center justify-center h-48 border border-dashed border-neutral-800 rounded-md text-neutral-600">
            <p className="text-xs">
              Fleet performance metrics from aggregated drone state history.
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Alert Frequency
          </h2>
          <div className="flex items-center justify-center h-48 border border-dashed border-neutral-800 rounded-md text-neutral-600">
            <p className="text-xs">
              Alert frequency distribution over time.
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Battery Trends
          </h2>
          <div className="flex items-center justify-center h-48 border border-dashed border-neutral-800 rounded-md text-neutral-600">
            <p className="text-xs">
              Battery consumption trends across missions.
            </p>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
