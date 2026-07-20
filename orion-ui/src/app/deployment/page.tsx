"use client";

import { useState } from "react";
import { PageShell } from "@/components/common/PageShell";
import { StatusDot } from "@/components/common/StatusDot";
import { useDroneStore } from "@/stores/droneStore";
import { useSwarmStore } from "@/stores/swarmStore";
import { useMissionStore } from "@/stores/missionStore";
import { HealthLevel, MissionStatus } from "@/contracts/types";
import { getTwinRESTClient } from "@/lib/restClient";
import { Rocket } from "lucide-react";

export default function DeploymentPage() {
  const drones = useDroneStore((s) => s.drones);
  const swarmState = useSwarmStore((s) => s.swarmState);
  const status = useMissionStore((s) => s.status);
  const [pending, setPending] = useState(false);

  const running = status === MissionStatus.RUNNING;
  const deployDisabled = !swarmState || drones.length === 0 || running || pending;

  // Deployment is intent submission only — the backend (Hive) is the sole
  // decision authority for accepting or rejecting the deployment.
  const onDeploy = async () => {
    setPending(true);
    try {
      await getTwinRESTClient().submitIntent({
        intent_type: "START_MISSION",
        payload: {},
        user_id: "operator",
        timestamp_ms: Date.now(),
      });
    } catch {
      // Rejected / unreachable — connection status reflects transport health.
    } finally {
      setPending(false);
    }
  };

  return (
    <PageShell
      title="Deployment"
      description="Pre-flight checks and mission deployment"
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Pre-flight Checklist
          </h2>
          <div className="space-y-2">
            {[
              {
                label: "Digital Twin Connected",
                ok: swarmState !== null,
              },
              {
                label: "Drones Detected",
                ok: drones.length > 0,
              },
              {
                label: "All Drones Healthy",
                ok:
                  drones.length > 0 &&
                  drones.every((d) => d.health === "OK"),
              },
              {
                label: "GPS Available (all)",
                ok:
                  drones.length > 0 &&
                  drones.every((d) => d.gps_available),
              },
              {
                label: "Comms Active (all)",
                ok:
                  drones.length > 0 &&
                  drones.every((d) => d.communication_active),
              },
              {
                label: "Battery > 80% (all)",
                ok:
                  drones.length > 0 &&
                  drones.every((d) => d.battery_pct > 80),
              },
            ].map((check, i) => (
              <div
                key={i}
                className="flex items-center justify-between text-xs border-b border-neutral-800 pb-2"
              >
                <span className="text-neutral-400">{check.label}</span>
                <StatusDot
                  health={check.ok ? HealthLevel.OK : HealthLevel.WARNING}
                  size="sm"
                  showLabel
                />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Deployment Actions
          </h2>
          <div className="space-y-3">
            <button
              onClick={onDeploy}
              className="w-full rounded-md bg-blue-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-50 flex items-center justify-center gap-2"
              disabled={deployDisabled}
            >
              <Rocket className="h-4 w-4" />
              {pending
                ? "Submitting…"
                : running
                  ? "Mission Deployed"
                  : "Deploy Mission"}
            </button>
            <p className="text-[10px] text-neutral-600 text-center">
              Deployment intent will be submitted to the backend handler.
              Hive is the sole decision authority.
            </p>
          </div>
        </div>

        <div className="lg:col-span-2 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Fleet Status for Deployment
          </h2>
          {drones.length === 0 ? (
            <p className="text-xs text-neutral-600">
              No drones available for deployment.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {drones.map((drone) => (
                <div
                  key={drone.drone_id}
                  className="flex items-center justify-between rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <StatusDot health={drone.health} size="sm" />
                    <span className="text-neutral-300">
                      Drone {drone.drone_id}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-neutral-500 font-mono">
                    <span>{Math.round(drone.battery_pct)}%</span>
                    <span>{drone.armed ? "ARMED" : "DISARMED"}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </PageShell>
  );
}
