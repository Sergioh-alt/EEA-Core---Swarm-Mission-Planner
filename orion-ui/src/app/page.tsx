"use client";

import Link from "next/link";
import { PageShell } from "@/components/common/PageShell";
import { MetricCard } from "@/components/common/MetricCard";
import { StatusDot } from "@/components/common/StatusDot";
import { MissionStatusBadge } from "@/components/common/MissionStatusBadge";
import { useSwarmStore } from "@/stores/swarmStore";
import { useAlertStore } from "@/stores/alertStore";
import { Plane, AlertTriangle, Activity, Battery, Radio } from "lucide-react";

export default function DashboardPage() {
  const swarmState = useSwarmStore((s) => s.swarmState);
  const unreadAlerts = useAlertStore((s) => s.unreadCount);

  if (!swarmState) {
    return (
      <PageShell title="Dashboard" description="Swarm Mission Overview">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <Activity className="h-8 w-8 text-neutral-600 mx-auto mb-3" />
            <p className="text-sm text-neutral-500">
              Waiting for Digital Twin connection...
            </p>
          </div>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="Dashboard"
      description="Swarm Mission Overview"
      actions={<MissionStatusBadge status={swarmState.mission_status} />}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Active Drones"
          value={`${swarmState.active_drones}/${swarmState.total_drones}`}
          icon={<Plane className="h-4 w-4" />}
        />
        <MetricCard
          label="Global Health"
          value={swarmState.global_health}
          icon={<StatusDot health={swarmState.global_health} />}
        />
        <MetricCard
          label="Active Failures"
          value={swarmState.active_failures.length}
          icon={<AlertTriangle className="h-4 w-4" />}
        />
        <MetricCard
          label="Unread Alerts"
          value={unreadAlerts}
          icon={<Battery className="h-4 w-4" />}
        />
      </div>

      <div className="mt-4">
        <Link
          href="/control"
          className="inline-flex items-center gap-2 rounded-md bg-blue-600/20 border border-blue-500/30 px-4 py-2 text-sm text-blue-400 hover:bg-blue-600/30 transition-colors"
        >
          <Radio className="h-4 w-4" />
          Open Mission Control
        </Link>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Fleet Summary
          </h2>
          <div className="space-y-2 text-sm text-neutral-400">
            <p>
              Total: {swarmState.total_drones} | Active:{" "}
              {swarmState.active_drones} | Failed: {swarmState.failed_drones}
            </p>
            {swarmState.drone_states.length > 0 ? (
              <div className="space-y-1">
                {swarmState.drone_states.map((drone) => (
                  <div
                    key={drone.drone_id}
                    className="flex items-center justify-between py-1"
                  >
                    <div className="flex items-center gap-2">
                      <StatusDot health={drone.health} size="sm" />
                      <span>Drone {drone.drone_id}</span>
                    </div>
                    <span className="font-mono text-xs">
                      {Math.round(drone.battery_pct)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-neutral-600">No drones connected</p>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Environment
          </h2>
          <div className="space-y-2 text-sm text-neutral-400">
            <p>
              Wind: {swarmState.environment_state.wind_speed_m_s.toFixed(1)} m/s
              @ {Math.round(swarmState.environment_state.wind_direction_deg)}
              &deg;
            </p>
            <p>Condition: {swarmState.environment_state.condition}</p>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
