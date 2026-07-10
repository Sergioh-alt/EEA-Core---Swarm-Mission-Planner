"use client";

import { useDroneStore } from "@/stores/droneStore";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Battery, Mountain, Gauge } from "lucide-react";

const CHART_COLORS = ["#22c55e", "#3b82f6", "#f59e0b"];
const MAX_DISPLAY_POINTS = 60;

interface ChartDataPoint {
  time: number;
  [key: string]: number;
}

export function TelemetryPanel() {
  const droneHistories = useDroneStore((s) => s.droneHistories);
  const selectedDroneId = useDroneStore((s) => s.selectedDroneId);

  const droneIds = selectedDroneId
    ? [selectedDroneId]
    : Object.keys(droneHistories).map(Number).slice(0, 3);

  const batteryData = buildChartData(droneHistories, droneIds, "battery_pct");
  const altitudeData = buildChartData(droneHistories, droneIds, "altitude_m");
  const speedData = buildChartData(droneHistories, droneIds, "speed");

  return (
    <div className="flex flex-col h-full bg-neutral-950 border-l border-neutral-800">
      <div className="px-3 py-2.5 border-b border-neutral-800">
        <h2 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
          Telemetry
        </h2>
        <p className="text-[10px] text-neutral-600 mt-0.5">
          {selectedDroneId
            ? `Drone ${selectedDroneId}`
            : `All drones (${droneIds.length})`}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-0.5 p-2">
        <TelemetryChart
          title="Battery"
          icon={<Battery className="h-3 w-3" />}
          data={batteryData}
          droneIds={droneIds}
          unit="%"
          domain={[0, 100]}
        />
        <TelemetryChart
          title="Altitude"
          icon={<Mountain className="h-3 w-3" />}
          data={altitudeData}
          droneIds={droneIds}
          unit="m"
          domain={[0, 50]}
        />
        <TelemetryChart
          title="Speed"
          icon={<Gauge className="h-3 w-3" />}
          data={speedData}
          droneIds={droneIds}
          unit="m/s"
          domain={[0, 8]}
        />
      </div>
    </div>
  );
}

interface TelemetryChartProps {
  title: string;
  icon: React.ReactNode;
  data: ChartDataPoint[];
  droneIds: number[];
  unit: string;
  domain: [number, number];
}

function TelemetryChart({
  title,
  icon,
  data,
  droneIds,
  unit,
  domain,
}: TelemetryChartProps) {
  return (
    <div className="rounded-md bg-neutral-900/50 border border-neutral-800 p-2">
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-neutral-500">{icon}</span>
        <span className="text-[10px] font-medium text-neutral-400">
          {title}
        </span>
        <span className="text-[9px] text-neutral-600 ml-auto">{unit}</span>
      </div>
      <div className="h-[80px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 2, right: 4, bottom: 2, left: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
            <XAxis
              dataKey="time"
              tick={false}
              axisLine={{ stroke: "#404040" }}
              tickLine={false}
            />
            <YAxis
              domain={domain}
              tick={{ fontSize: 8, fill: "#737373" }}
              axisLine={{ stroke: "#404040" }}
              tickLine={false}
              width={24}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#171717",
                border: "1px solid #404040",
                borderRadius: "4px",
                fontSize: "10px",
              }}
              labelFormatter={() => ""}
              formatter={(value: number) => [
                `${value.toFixed(1)} ${unit}`,
              ]}
            />
            {droneIds.map((id, idx) => (
              <Line
                key={id}
                type="monotone"
                dataKey={`drone_${id}`}
                stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function buildChartData(
  histories: Record<number, Array<{ timestamp_ms: number; battery_pct: number; altitude_m: number; speed: number }>>,
  droneIds: number[],
  field: "battery_pct" | "altitude_m" | "speed"
): ChartDataPoint[] {
  if (droneIds.length === 0) return [];

  const maxLen = Math.min(
    MAX_DISPLAY_POINTS,
    Math.max(...droneIds.map((id) => (histories[id] ?? []).length), 0)
  );

  const data: ChartDataPoint[] = [];
  for (let i = 0; i < maxLen; i++) {
    const point: ChartDataPoint = { time: i };
    for (const id of droneIds) {
      const hist = histories[id] ?? [];
      const offset = hist.length - maxLen;
      const entry = hist[offset + i];
      if (entry) {
        point[`drone_${id}`] = entry[field];
      }
    }
    data.push(point);
  }
  return data;
}
