"use client";

import { useDroneStore } from "@/stores/droneStore";
import { StatusDot } from "@/components/common/StatusDot";
import { BatteryIndicator } from "@/components/common/BatteryIndicator";
import { cn, formatAltitude, formatSpeed } from "@/lib/utils";
import { Crosshair, Radio, Navigation, WifiOff } from "lucide-react";
import type { DroneState } from "@/contracts/types";

export function FleetPanel() {
  const drones = useDroneStore((s) => s.drones);
  const selectedDroneId = useDroneStore((s) => s.selectedDroneId);
  const selectDrone = useDroneStore((s) => s.selectDrone);

  return (
    <div className="flex flex-col h-full bg-neutral-950 border-r border-neutral-800">
      <div className="px-3 py-2.5 border-b border-neutral-800">
        <h2 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
          Fleet Status
        </h2>
        <p className="text-[10px] text-neutral-600 mt-0.5">
          {drones.length} drone{drones.length !== 1 ? "s" : ""} active
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {drones.length === 0 ? (
          <div className="p-4 text-center text-xs text-neutral-600">
            No drones connected
          </div>
        ) : (
          <div className="space-y-0.5 p-1.5">
            {(drones as DroneState[]).map((drone) => (
              <FleetDroneCard
                key={drone.drone_id}
                drone={drone}
                isSelected={drone.drone_id === selectedDroneId}
                onSelect={() =>
                  selectDrone(
                    drone.drone_id === selectedDroneId
                      ? null
                      : drone.drone_id
                  )
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface FleetDroneCardProps {
  drone: DroneState;
  isSelected: boolean;
  onSelect: () => void;
}

function FleetDroneCard({ drone, isSelected, onSelect }: FleetDroneCardProps) {
  const speed = Math.sqrt(
    drone.velocity.vx ** 2 + drone.velocity.vy ** 2 + drone.velocity.vz ** 2
  );

  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full rounded-md p-2.5 text-left transition-all",
        isSelected
          ? "bg-blue-600/15 border border-blue-500/40 ring-1 ring-blue-500/20"
          : "bg-neutral-900/50 border border-neutral-800 hover:bg-neutral-800/80 hover:border-neutral-700"
      )}
    >
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <StatusDot health={drone.health} size="sm" />
          <span className="text-xs font-medium text-neutral-200">
            Drone {drone.drone_id}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {isSelected && (
            <Crosshair className="h-3 w-3 text-blue-400" />
          )}
          {drone.communication_active ? (
            <Radio className="h-3 w-3 text-green-500" />
          ) : (
            <WifiOff className="h-3 w-3 text-red-500" />
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px]">
        <div className="flex items-center gap-1 text-neutral-500">
          <span>BAT</span>
          <BatteryIndicator percentage={drone.battery_pct} size="xs" showLabel={false} />
          <span className="text-neutral-400 font-mono">{Math.round(drone.battery_pct)}%</span>
        </div>
        <div className="flex items-center gap-1 text-neutral-500">
          <Navigation className="h-2.5 w-2.5" />
          <span className="text-neutral-400">{Math.round(drone.heading_deg)}°</span>
        </div>
        <div className="text-neutral-500">
          ALT{" "}
          <span className="text-neutral-400">
            {formatAltitude(drone.position.altitude_m)}
          </span>
        </div>
        <div className="text-neutral-500">
          SPD{" "}
          <span className="text-neutral-400">{formatSpeed(speed)}</span>
        </div>
      </div>

      <div className="mt-1.5 flex items-center justify-between text-[10px]">
        <span
          className={cn(
            "rounded px-1.5 py-0.5 font-medium",
            drone.gps_available
              ? "bg-green-500/10 text-green-400"
              : "bg-red-500/10 text-red-400"
          )}
        >
          GPS {drone.gps_available ? "OK" : "LOST"}
        </span>
        <span className="text-neutral-600 font-mono">
          {drone.mode}
        </span>
      </div>
    </button>
  );
}
