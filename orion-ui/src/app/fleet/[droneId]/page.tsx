"use client";

import { useParams } from "next/navigation";
import { PageShell } from "@/components/common/PageShell";
import { StatusDot } from "@/components/common/StatusDot";
import { BatteryIndicator } from "@/components/common/BatteryIndicator";
import { useDroneStore } from "@/stores/droneStore";
import { formatCoordinate, formatAltitude, formatSpeed } from "@/lib/utils";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function DroneDetailPage() {
  const params = useParams();
  const droneId = Number(params.droneId);
  const drones = useDroneStore((s) => s.drones);
  const drone = drones.find((d) => d.drone_id === droneId);

  if (!drone) {
    return (
      <PageShell title={`Drone ${droneId}`} description="Drone Detail">
        <div className="flex items-center justify-center h-64">
          <p className="text-sm text-neutral-500">
            Drone {droneId} not found. Waiting for data...
          </p>
        </div>
      </PageShell>
    );
  }

  const speed = Math.sqrt(
    drone.velocity.vx ** 2 + drone.velocity.vy ** 2 + drone.velocity.vz ** 2
  );

  return (
    <PageShell
      title={`Drone ${drone.drone_id}`}
      description={`Mode: ${drone.mode}`}
      actions={
        <Link
          href="/fleet"
          className="flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-300"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to Fleet
        </Link>
      }
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">Status</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Health</span>
              <StatusDot health={drone.health} showLabel />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Armed</span>
              <span className="text-xs font-mono text-neutral-300">
                {drone.armed ? "YES" : "NO"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Mode</span>
              <span className="text-xs font-mono text-neutral-300">
                {drone.mode}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Task</span>
              <span className="text-xs font-mono text-neutral-300">
                {drone.current_task}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Comms</span>
              <span
                className={`text-xs font-mono ${
                  drone.communication_active
                    ? "text-emerald-400"
                    : "text-red-400"
                }`}
              >
                {drone.communication_active ? "ACTIVE" : "OFFLINE"}
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Position & Motion
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Latitude</span>
              <span className="text-xs font-mono text-neutral-300">
                {formatCoordinate(drone.position.latitude)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Longitude</span>
              <span className="text-xs font-mono text-neutral-300">
                {formatCoordinate(drone.position.longitude)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Altitude</span>
              <span className="text-xs font-mono text-neutral-300">
                {formatAltitude(drone.position.altitude_m)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Speed</span>
              <span className="text-xs font-mono text-neutral-300">
                {formatSpeed(speed)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Heading</span>
              <span className="text-xs font-mono text-neutral-300">
                {Math.round(drone.heading_deg)}&deg;
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Systems
          </h2>
          <div className="space-y-3">
            <div>
              <span className="text-xs text-neutral-500">Battery</span>
              <div className="mt-1">
                <BatteryIndicator
                  percentage={drone.battery_pct}
                  voltage={drone.battery_voltage}
                  size="md"
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">GPS</span>
              <span
                className={`text-xs font-mono ${
                  drone.gps_available ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {drone.gps_available
                  ? `OK (${drone.gps_accuracy_m.toFixed(1)}m)`
                  : "UNAVAILABLE"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
        <h2 className="text-sm font-medium text-neutral-300 mb-3">
          Telemetry Charts
        </h2>
        <div className="flex items-center justify-center h-48 text-neutral-600">
          <p className="text-sm">
            Telemetry charts will render here when connected to Digital Twin.
          </p>
        </div>
      </div>
    </PageShell>
  );
}
