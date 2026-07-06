"use client";

import { PageShell } from "@/components/common/PageShell";
import { StatusDot } from "@/components/common/StatusDot";
import { useDroneStore } from "@/stores/droneStore";
import { useSwarmStore } from "@/stores/swarmStore";
import { Map as MapIcon } from "lucide-react";

export default function MapPage() {
  const drones = useDroneStore((s) => s.drones);
  const swarmState = useSwarmStore((s) => s.swarmState);

  return (
    <PageShell title="Field Map" description="Geographic swarm visualization">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4 h-full">
        <div className="lg:col-span-3 rounded-lg border border-neutral-800 bg-neutral-900 overflow-hidden">
          <div className="flex items-center justify-center h-full min-h-[500px] text-neutral-600">
            <div className="text-center">
              <MapIcon className="h-12 w-12 mx-auto mb-3" />
              <p className="text-sm">Map Container</p>
              <p className="text-xs text-neutral-700 mt-1">
                Mapbox GL will render here when configured.
              </p>
              <p className="text-xs text-neutral-700">
                {drones.length} drone marker
                {drones.length !== 1 ? "s" : ""} ready
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Drone Markers
          </h2>
          {drones.length === 0 ? (
            <p className="text-xs text-neutral-600">No drones to display.</p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {drones.map((drone) => (
                <div
                  key={drone.drone_id}
                  className="flex items-center justify-between text-xs border-b border-neutral-800 pb-2"
                >
                  <div className="flex items-center gap-2">
                    <StatusDot health={drone.health} size="sm" />
                    <span className="text-neutral-300">
                      Drone {drone.drone_id}
                    </span>
                  </div>
                  <span className="font-mono text-neutral-500">
                    {drone.position.altitude_m.toFixed(0)}m
                  </span>
                </div>
              ))}
            </div>
          )}

          {swarmState && (
            <div className="mt-4 pt-3 border-t border-neutral-800">
              <h3 className="text-xs font-medium text-neutral-400 mb-2">
                Environment
              </h3>
              <p className="text-xs text-neutral-500">
                Wind:{" "}
                {swarmState.environment_state.wind_speed_m_s.toFixed(1)} m/s
              </p>
              <p className="text-xs text-neutral-500">
                Condition: {swarmState.environment_state.condition}
              </p>
            </div>
          )}
        </div>
      </div>
    </PageShell>
  );
}
