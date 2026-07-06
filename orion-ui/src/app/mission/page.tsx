"use client";

import { PageShell } from "@/components/common/PageShell";
import { MissionStatusBadge } from "@/components/common/MissionStatusBadge";
import { useSwarmStore } from "@/stores/swarmStore";
import { useMissionStore } from "@/stores/missionStore";
import { formatTimestamp } from "@/lib/utils";
import { Target } from "lucide-react";

export default function MissionPage() {
  const swarmState = useSwarmStore((s) => s.swarmState);
  const events = useMissionStore((s) => s.events);
  const progress = useMissionStore((s) => s.progress);

  return (
    <PageShell
      title="Mission Control"
      description="Active mission monitoring and control"
      actions={
        swarmState && (
          <MissionStatusBadge status={swarmState.mission_status} />
        )
      }
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="text-sm font-medium text-neutral-300 mb-3">
              Mission Progress
            </h2>
            <div className="relative h-3 w-full rounded-full bg-neutral-800">
              <div
                className="absolute inset-y-0 left-0 rounded-full bg-blue-600 transition-all"
                style={{ width: `${Math.min(100, progress)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-neutral-500 text-right">
              {Math.round(progress)}%
            </p>
          </div>

          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="text-sm font-medium text-neutral-300 mb-3">
              Mission Map
            </h2>
            <div className="flex items-center justify-center h-64 text-neutral-600 border border-dashed border-neutral-800 rounded-md">
              <div className="text-center">
                <Target className="h-8 w-8 mx-auto mb-2" />
                <p className="text-sm">
                  Mission map view will render when connected.
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="text-sm font-medium text-neutral-300 mb-3">
              Intent Controls
            </h2>
            <div className="flex items-center gap-2">
              <button
                className="rounded-md bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
                disabled={
                  !swarmState ||
                  swarmState.mission_status === "RUNNING"
                }
              >
                Start Mission
              </button>
              <button
                className="rounded-md bg-amber-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-600 disabled:opacity-50"
                disabled={
                  !swarmState ||
                  swarmState.mission_status !== "RUNNING"
                }
              >
                Pause
              </button>
              <button
                className="rounded-md bg-red-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
                disabled={
                  !swarmState || swarmState.mission_status === "IDLE"
                }
              >
                Stop
              </button>
            </div>
            <p className="mt-2 text-[10px] text-neutral-600">
              Intents are submitted to the backend handler. Hive decides
              acceptance.
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Event Log
          </h2>
          {events.length === 0 ? (
            <p className="text-xs text-neutral-600">No events yet.</p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-start gap-2 text-xs border-b border-neutral-800 pb-2"
                >
                  <span className="font-mono text-neutral-600 shrink-0">
                    {formatTimestamp(event.timestamp_ms)}
                  </span>
                  <span className="text-neutral-400">{event.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </PageShell>
  );
}
