"use client";

import { useMemo } from "react";
import { PageShell } from "@/components/common/PageShell";
import { useAnalytics } from "@/hooks/useAnalytics";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const SERIES_COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#8b5cf6", "#ec4899"];
const SEVERITY_COLORS: Record<string, string> = {
  INFO: "#3b82f6",
  WARNING: "#f59e0b",
  CRITICAL: "#ef4444",
};

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
      <h2 className="text-sm font-medium text-neutral-300 mb-3">{title}</h2>
      {children}
    </div>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center h-48 border border-dashed border-neutral-800 rounded-md text-neutral-600">
      <p className="text-xs px-4 text-center">{message}</p>
    </div>
  );
}

export default function AnalyticsPage() {
  const { data, live } = useAnalytics();

  const batteryChart = useMemo(() => {
    if (!data) return { rows: [], ids: [] as string[] };
    const ids = Object.keys(data.battery_trends);
    const maxLen = Math.max(
      0,
      ...ids.map((id) => data.battery_trends[id].length)
    );
    const rows: Record<string, number>[] = [];
    for (let i = 0; i < maxLen; i++) {
      const row: Record<string, number> = { step: i };
      for (const id of ids) {
        const pt = data.battery_trends[id][i];
        if (pt) row[`d${id}`] = Math.round(pt.battery_pct);
      }
      rows.push(row);
    }
    return { rows, ids };
  }, [data]);

  const alertRows = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.alert_frequency).map(([severity, count]) => ({
      severity,
      count,
    }));
  }, [data]);

  const fleetRows = useMemo(() => {
    if (!data) return [];
    return data.fleet_utilization.map((f, i) => ({
      step: i,
      active: f.active_drones,
      failed: f.failed_drones,
      total: f.total_drones,
    }));
  }, [data]);

  const missionDurationMin = data
    ? Math.round((data.mission.duration_ms / 60000) * 10) / 10
    : 0;

  return (
    <PageShell
      title="Analytics"
      description="Mission and fleet performance analytics"
    >
      {!live && (
        <div className="mb-4 rounded-md border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-400">
          Development mode — charts aggregate streamed telemetry. Set
          NEXT_PUBLIC_TWIN_API_URL to view backend-computed Digital Twin analytics.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-4 sm:grid-cols-4">
        <Stat label="Snapshots" value={data ? String(data.snapshot_count) : "—"} />
        <Stat
          label="Mission Progress"
          value={data ? `${Math.round(data.mission.progress * 100)}%` : "—"}
        />
        <Stat label="Mission Status" value={data ? data.mission.status : "—"} />
        <Stat label="Duration (min)" value={data ? String(missionDurationMin) : "—"} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Battery Trends">
          {batteryChart.rows.length ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={batteryChart.rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                <XAxis dataKey="step" stroke="#525252" fontSize={10} />
                <YAxis stroke="#525252" fontSize={10} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: "#171717", border: "1px solid #404040", fontSize: 11 }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {batteryChart.ids.map((id, i) => (
                  <Line
                    key={id}
                    type="monotone"
                    dataKey={`d${id}`}
                    name={`Drone ${id}`}
                    stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                    dot={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart message="No battery telemetry recorded yet." />
          )}
        </Card>

        <Card title="Fleet Utilization">
          {fleetRows.length ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={fleetRows}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                <XAxis dataKey="step" stroke="#525252" fontSize={10} />
                <YAxis stroke="#525252" fontSize={10} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#171717", border: "1px solid #404040", fontSize: 11 }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Area type="monotone" dataKey="active" name="Active" stroke="#22c55e" fill="#22c55e33" isAnimationActive={false} />
                <Area type="monotone" dataKey="failed" name="Failed" stroke="#ef4444" fill="#ef444433" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart message="No fleet utilization data yet." />
          )}
        </Card>

        <Card title="Alert Frequency">
          {alertRows.some((r) => r.count > 0) ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={alertRows}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                <XAxis dataKey="severity" stroke="#525252" fontSize={10} />
                <YAxis stroke="#525252" fontSize={10} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#171717", border: "1px solid #404040", fontSize: 11 }}
                  cursor={{ fill: "#ffffff08" }}
                />
                <Bar dataKey="count" name="Alerts" isAnimationActive={false}>
                  {alertRows.map((r) => (
                    <Bar key={r.severity} dataKey="count" fill={SEVERITY_COLORS[r.severity]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart message="No alerts recorded yet." />
          )}
        </Card>

        <Card title="Mission Summary">
          <div className="h-48 flex flex-col justify-center gap-3">
            <ProgressBar label="Coverage progress" value={data ? data.mission.progress : 0} />
            <div className="grid grid-cols-2 gap-3 text-xs text-neutral-400">
              <div>
                <div className="text-neutral-500">Status</div>
                <div className="text-neutral-200 font-mono">{data?.mission.status ?? "—"}</div>
              </div>
              <div>
                <div className="text-neutral-500">Duration</div>
                <div className="text-neutral-200 font-mono">{missionDurationMin} min</div>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </PageShell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-3">
      <div className="text-[10px] uppercase tracking-wider text-neutral-500">{label}</div>
      <div className="text-lg font-semibold text-neutral-100 mt-1">{value}</div>
    </div>
  );
}

function ProgressBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-neutral-500 mb-1">
        <span>{label}</span>
        <span>{Math.round(value * 100)}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-neutral-800">
        <div
          className="h-2 rounded-full bg-blue-600"
          style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }}
        />
      </div>
    </div>
  );
}
