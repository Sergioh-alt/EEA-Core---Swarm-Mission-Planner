"use client";

import { useEffect, useState } from "react";
import { getTwinRESTClient } from "@/lib/restClient";
import { isLiveMode } from "@/lib/config";
import { useDroneStore } from "@/stores/droneStore";
import { useAlertStore } from "@/stores/alertStore";
import { useMissionStore } from "@/stores/missionStore";
import type { AnalyticsData } from "@/contracts/types";

const POLL_INTERVAL_MS = 3000;

/**
 * Provides analytics for the Analytics screen.
 *
 * LIVE mode: fetches the backend-computed `/api/twin/analytics` payload (the
 * only source of truth). Dev fallback: reshapes telemetry already streamed
 * into the stores — a pure presentation-time aggregation, never invented
 * business metrics.
 */
export function useAnalytics(): { data: AnalyticsData | null; live: boolean } {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const drones = useDroneStore((s) => s.drones);
  const droneHistories = useDroneStore((s) => s.droneHistories);
  const alerts = useAlertStore((s) => s.alerts);
  const missionStatus = useMissionStore((s) => s.status);
  const progress = useMissionStore((s) => s.progress);
  const startTime = useMissionStore((s) => s.startTime);

  useEffect(() => {
    if (!isLiveMode()) return;
    let cancelled = false;
    const fetchAnalytics = () => {
      getTwinRESTClient()
        .getAnalytics()
        .then((a) => {
          if (!cancelled) setData(a);
        })
        .catch(() => {});
    };
    fetchAnalytics();
    const timer = setInterval(fetchAnalytics, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (isLiveMode()) return;
    // Dev fallback: reshape streamed telemetry into the analytics contract.
    const battery_trends: Record<
      string,
      { version: number; timestamp_ms: number; battery_pct: number }[]
    > = {};
    for (const [id, hist] of Object.entries(droneHistories)) {
      battery_trends[id] = hist.map((h, i) => ({
        version: i,
        timestamp_ms: h.timestamp_ms,
        battery_pct: h.battery_pct,
      }));
    }
    const alert_frequency: Record<string, number> = {
      INFO: 0,
      WARNING: 0,
      CRITICAL: 0,
    };
    for (const a of alerts) {
      alert_frequency[a.severity] = (alert_frequency[a.severity] ?? 0) + 1;
    }
    setData({
      snapshot_count: 0,
      battery_trends,
      fleet_utilization: [
        {
          version: 0,
          timestamp_ms: Date.now(),
          active_drones: drones.filter((d) => d.communication_active).length,
          failed_drones: drones.filter((d) => !d.communication_active).length,
          total_drones: drones.length,
        },
      ],
      alert_frequency,
      mission: {
        mission_id: null,
        status: missionStatus,
        progress,
        duration_ms: startTime ? Date.now() - startTime : 0,
      },
    });
  }, [drones, droneHistories, alerts, missionStatus, progress, startTime]);

  return { data, live: isLiveMode() };
}
