"use client";

import { PageShell } from "@/components/common/PageShell";
import { Layers } from "lucide-react";

export default function PlanningPage() {
  return (
    <PageShell
      title="Mission Planning"
      description="Reference view of the planned mission profile"
      actions={
        <span className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[10px] font-medium uppercase tracking-wider text-neutral-400">
          Preview
        </span>
      }
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Planning Map
          </h2>
          <div className="flex items-center justify-center h-96 border border-dashed border-neutral-800 rounded-md text-neutral-600">
            <div className="max-w-sm text-center px-4">
              <Layers className="h-8 w-8 mx-auto mb-2" />
              <p className="text-sm">Interactive planning not enabled</p>
              <p className="text-xs text-neutral-700 mt-1">
                The demonstration mission follows a fixed coverage route owned
                by the Digital Twin. Operator control is available through
                intents on the Mission Control screen.
              </p>
              <p className="text-[10px] text-neutral-700 mt-1">
                Route generation and allocation are backend responsibilities —
                Hive is the sole decision authority.
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="text-sm font-medium text-neutral-300 mb-3">
              Mission Parameters
            </h2>
            <p className="text-[10px] text-neutral-600 mb-3">
              Reference profile for the demonstration mission (read-only).
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-neutral-500 block mb-1">
                  Mission Type
                </label>
                <div className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-400">
                  Survey
                </div>
              </div>
              <div>
                <label className="text-xs text-neutral-500 block mb-1">
                  Altitude (m)
                </label>
                <div className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-400">
                  50
                </div>
              </div>
              <div>
                <label className="text-xs text-neutral-500 block mb-1">
                  Speed (m/s)
                </label>
                <div className="rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-400">
                  5.0
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="text-sm font-medium text-neutral-300 mb-3">
              Waypoints
            </h2>
            <p className="text-xs text-neutral-600">
              Waypoints are defined by the backend route planner and streamed
              to Mission Control as the executed coverage path.
            </p>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
