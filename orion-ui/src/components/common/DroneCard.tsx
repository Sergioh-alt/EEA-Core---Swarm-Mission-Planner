"use client";

import { cn } from "@/lib/utils";
import { StatusDot } from "./StatusDot";
import { BatteryIndicator } from "./BatteryIndicator";
import { formatAltitude, formatSpeed } from "@/lib/utils";
import type { DroneState } from "@/contracts/types";

interface DroneCardProps {
  drone: DroneState;
  selected?: boolean;
  onClick?: () => void;
  className?: string;
}

function computeSpeed(drone: DroneState): number {
  return Math.sqrt(
    drone.velocity.vx ** 2 +
      drone.velocity.vy ** 2 +
      drone.velocity.vz ** 2
  );
}

export function DroneCard({
  drone,
  selected = false,
  onClick,
  className,
}: DroneCardProps) {
  const speed = computeSpeed(drone);
  const isOffline = !drone.communication_active;

  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full rounded-lg border p-3 text-left transition-colors",
        selected
          ? "border-blue-500 bg-blue-950/30"
          : "border-neutral-800 bg-neutral-900 hover:border-neutral-700",
        isOffline && "opacity-60",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusDot health={drone.health} size="sm" />
          <span className="text-sm font-medium text-neutral-200">
            Drone {drone.drone_id}
          </span>
        </div>
        <span className="text-xs font-mono text-neutral-500">
          {drone.mode}
        </span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <div>
          <span className="text-[10px] text-neutral-600 uppercase">Alt</span>
          <p className="text-xs font-mono text-neutral-300">
            {formatAltitude(drone.position.altitude_m)}
          </p>
        </div>
        <div>
          <span className="text-[10px] text-neutral-600 uppercase">Speed</span>
          <p className="text-xs font-mono text-neutral-300">
            {formatSpeed(speed)}
          </p>
        </div>
      </div>
      <div className="mt-2">
        <BatteryIndicator
          percentage={drone.battery_pct}
          size="sm"
          showLabel={true}
        />
      </div>
      {isOffline && (
        <div className="mt-1">
          <span className="text-[10px] font-medium text-red-400">
            OFFLINE
          </span>
        </div>
      )}
    </button>
  );
}
