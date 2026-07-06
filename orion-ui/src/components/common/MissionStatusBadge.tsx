"use client";

import { cn } from "@/lib/utils";
import type { MissionStatus } from "@/contracts/types";

const MISSION_STYLES: Record<MissionStatus, string> = {
  IDLE: "bg-neutral-800 text-neutral-400 border-neutral-700",
  RUNNING: "bg-emerald-900/50 text-emerald-300 border-emerald-700",
  PAUSED: "bg-amber-900/50 text-amber-300 border-amber-700",
  FAILED: "bg-red-900/50 text-red-300 border-red-700",
  COMPLETED: "bg-blue-900/50 text-blue-300 border-blue-700",
};

interface MissionStatusBadgeProps {
  status: MissionStatus;
  className?: string;
}

export function MissionStatusBadge({
  status,
  className,
}: MissionStatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        MISSION_STYLES[status],
        className
      )}
    >
      {status}
    </span>
  );
}
