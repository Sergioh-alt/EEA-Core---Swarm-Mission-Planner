"use client";

import { useMissionStore, type MissionEvent } from "@/stores/missionStore";
import { useSwarmStore } from "@/stores/swarmStore";
import { MissionStatusBadge } from "@/components/common/MissionStatusBadge";
import { cn, formatTimestamp, formatDuration } from "@/lib/utils";
import { MissionStatus } from "@/contracts/types";
import { Clock, Target, CheckCircle2, AlertCircle, Pause, Play } from "lucide-react";

const EVENT_ICONS: Record<MissionEvent["type"], React.ReactNode> = {
  START: <Play className="h-3 w-3 text-green-400" />,
  PAUSE: <Pause className="h-3 w-3 text-yellow-400" />,
  RESUME: <Play className="h-3 w-3 text-blue-400" />,
  STOP: <AlertCircle className="h-3 w-3 text-red-400" />,
  FAILURE: <AlertCircle className="h-3 w-3 text-red-500" />,
  RECOVERY: <CheckCircle2 className="h-3 w-3 text-green-500" />,
  MILESTONE: <Target className="h-3 w-3 text-blue-400" />,
};

export function MissionStatusPanel() {
  const status = useMissionStore((s) => s.status);
  const progress = useMissionStore((s) => s.progress);
  const missionId = useMissionStore((s) => s.missionId);
  const startTime = useMissionStore((s) => s.startTime);
  const events = useMissionStore((s) => s.events);
  const swarmState = useSwarmStore((s) => s.swarmState);

  const elapsed = startTime ? Date.now() - startTime : 0;

  return (
    <div className="flex flex-col h-full rounded-lg bg-neutral-900/50 border border-neutral-800 overflow-hidden">
      <div className="px-3 py-2.5 border-b border-neutral-800 flex items-center justify-between">
        <h2 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
          Mission
        </h2>
        <MissionStatusBadge status={status} />
      </div>

      <div className="px-3 py-2 border-b border-neutral-800/50">
        <div className="flex items-center justify-between text-[10px] mb-1.5">
          <span className="text-neutral-500">
            {missionId || "No active mission"}
          </span>
          {startTime && (
            <span className="flex items-center gap-1 text-neutral-500">
              <Clock className="h-2.5 w-2.5" />
              {formatDuration(elapsed)}
            </span>
          )}
        </div>

        <div className="relative w-full h-2 rounded-full bg-neutral-800 overflow-hidden">
          <div
            className={cn(
              "absolute inset-y-0 left-0 rounded-full transition-all duration-500",
              status === MissionStatus.RUNNING
                ? "bg-gradient-to-r from-blue-600 to-cyan-500"
                : status === MissionStatus.COMPLETED
                  ? "bg-green-500"
                  : status === MissionStatus.FAILED
                    ? "bg-red-500"
                    : "bg-neutral-700"
            )}
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>
        <div className="flex justify-between mt-1 text-[9px] text-neutral-600">
          <span>{Math.round(progress * 100)}% complete</span>
          <span>
            {swarmState
              ? `${swarmState.active_drones}/${swarmState.total_drones} drones`
              : "—"}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="px-3 py-2">
          <h3 className="text-[10px] font-medium text-neutral-500 uppercase tracking-wider mb-1.5">
            Event Log
          </h3>
          {events.length === 0 ? (
            <p className="text-[10px] text-neutral-600 text-center py-3">
              No events yet
            </p>
          ) : (
            <div className="space-y-1">
              {[...events].reverse().slice(0, 20).map((event) => (
                <div
                  key={event.id}
                  className="flex items-start gap-2 rounded px-1.5 py-1 hover:bg-neutral-800/50"
                >
                  <div className="mt-0.5">
                    {EVENT_ICONS[event.type]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] text-neutral-300 truncate">
                      {event.message}
                    </p>
                    <p className="text-[9px] text-neutral-600">
                      {formatTimestamp(event.timestamp_ms)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
