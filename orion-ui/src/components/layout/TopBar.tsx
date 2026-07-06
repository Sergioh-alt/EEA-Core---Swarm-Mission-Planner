"use client";

import { cn } from "@/lib/utils";
import { ConnectionBadge } from "@/components/common/ConnectionBadge";
import { MissionStatusBadge } from "@/components/common/MissionStatusBadge";
import { useSwarmStore } from "@/stores/swarmStore";
import { useAlertStore } from "@/stores/alertStore";
import { AlertTriangle } from "lucide-react";
import Link from "next/link";

export function TopBar() {
  const swarmState = useSwarmStore((s) => s.swarmState);
  const unreadCount = useAlertStore((s) => s.unreadCount);

  return (
    <header className="flex h-12 items-center justify-between border-b border-neutral-800 bg-neutral-950 px-4">
      <div className="flex items-center gap-4">
        {swarmState && (
          <>
            <MissionStatusBadge status={swarmState.mission_status} />
            <span className="text-xs text-neutral-500">
              {swarmState.active_drones}/{swarmState.total_drones} active
            </span>
          </>
        )}
      </div>

      <div className="flex items-center gap-4">
        <ConnectionBadge />

        <Link
          href="/alerts"
          className={cn(
            "relative flex items-center gap-1 text-xs",
            unreadCount > 0
              ? "text-amber-400"
              : "text-neutral-500"
          )}
        >
          <AlertTriangle className="h-4 w-4" />
          {unreadCount > 0 && (
            <span className="absolute -right-2 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-600 text-[10px] font-bold text-white">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </Link>

        {swarmState && swarmState.active_failures.length > 0 && (
          <span className="text-xs text-red-400 font-mono">
            {swarmState.active_failures.length} failure
            {swarmState.active_failures.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>
    </header>
  );
}
