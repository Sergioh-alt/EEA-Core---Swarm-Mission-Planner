"use client";

import { PageShell } from "@/components/common/PageShell";
import { Layers } from "lucide-react";

export default function PlanningPage() {
  return (
    <PageShell
      title="Mission Planning"
      description="Define mission parameters and waypoints"
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Planning Map
          </h2>
          <div className="flex items-center justify-center h-96 border border-dashed border-neutral-800 rounded-md text-neutral-600">
            <div className="text-center">
              <Layers className="h-8 w-8 mx-auto mb-2" />
              <p className="text-sm">Mission Planning Map</p>
              <p className="text-xs text-neutral-700 mt-1">
                Define waypoints, geofences, and mission areas.
              </p>
              <p className="text-[10px] text-neutral-700 mt-1">
                Planning data is submitted as intents. Hive decides acceptance.
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="text-sm font-medium text-neutral-300 mb-3">
              Mission Parameters
            </h2>
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
              No waypoints defined. Click on the map to add waypoints.
            </p>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
