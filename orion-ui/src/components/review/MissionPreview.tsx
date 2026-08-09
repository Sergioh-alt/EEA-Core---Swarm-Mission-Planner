"use client";

/**
 * Read-only execution preview (Phase 10D.6).
 *
 * Draws the planned routes, drone starting positions, coverage order and
 * flight sequence *exactly as they appear in the Mission Package*. It is a
 * visualization: it never starts the Digital Twin, creates simulation state,
 * or calls any runtime/intent endpoint — it receives a package and renders it.
 */

import { useMemo } from "react";
import type { MissionPackage } from "@/contracts/mission";
import {
  executionOf,
  routeSummariesOf,
  timelineOf,
  type ExecutionRouteView,
} from "@/lib/missionPackageView";

const ROUTE_COLORS = [
  "#60a5fa",
  "#34d399",
  "#f59e0b",
  "#f472b6",
  "#a78bfa",
  "#22d3ee",
];

const VIEW_W = 640;
const VIEW_H = 420;
const PAD = 16;

interface Projector {
  readonly px: (x: number) => number;
  readonly py: (y: number) => number;
}

function projector(points: readonly (readonly [number, number])[]): Projector {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const minX = xs.length ? Math.min(...xs) : 0;
  const maxX = xs.length ? Math.max(...xs) : 1;
  const minY = ys.length ? Math.min(...ys) : 0;
  const maxY = ys.length ? Math.max(...ys) : 1;
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const scale = Math.min((VIEW_W - 2 * PAD) / spanX, (VIEW_H - 2 * PAD) / spanY);
  const offX = (VIEW_W - spanX * scale) / 2;
  const offY = (VIEW_H - spanY * scale) / 2;
  return {
    px: (x) => offX + (x - minX) * scale,
    // Metric Y grows north; SVG Y grows down.
    py: (y) => VIEW_H - (offY + (y - minY) * scale),
  };
}

function polyline(route: ExecutionRouteView, project: Projector): string {
  return route.waypoints
    .map((w) => `${project.px(w.x).toFixed(1)},${project.py(w.y).toFixed(1)}`)
    .join(" ");
}

export function MissionPreview({ pkg }: { pkg: MissionPackage }) {
  const execution = useMemo(() => executionOf(pkg), [pkg]);
  const summaries = useMemo(() => routeSummariesOf(pkg), [pkg]);
  const timeline = useMemo(() => timelineOf(pkg), [pkg]);

  const project = useMemo(() => {
    const points = [
      ...execution.fieldPolygon,
      ...execution.routes.flatMap((r) =>
        r.waypoints.map((w) => [w.x, w.y] as const)
      ),
    ];
    return projector(points);
  }, [execution]);

  if (execution.fieldPolygon.length === 0 && execution.routes.length === 0) {
    return (
      <p className="text-[11px] text-neutral-500">
        The Mission Package contains no execution geometry to preview.
      </p>
    );
  }

  const polygonPoints = execution.fieldPolygon
    .map(([x, y]) => `${project.px(x).toFixed(1)},${project.py(y).toFixed(1)}`)
    .join(" ");

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-neutral-500">
        Read-only visualization of the deployed geometry. Nothing is simulated
        or started here — the Digital Twin remains untouched until deployment.
      </p>

      <div className="rounded-md border border-neutral-800 bg-neutral-950 p-2">
        <svg
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          className="h-auto w-full"
          role="img"
          aria-label="Planned mission routes preview"
        >
          {polygonPoints && (
            <polygon
              points={polygonPoints}
              fill="rgba(34,197,94,0.06)"
              stroke="#22c55e"
              strokeWidth={1.5}
            />
          )}
          {execution.routes.map((route, i) => {
            const color = ROUTE_COLORS[i % ROUTE_COLORS.length];
            const start = route.waypoints[0];
            return (
              <g key={route.droneId}>
                <polyline
                  points={polyline(route, project)}
                  fill="none"
                  stroke={color}
                  strokeWidth={1.4}
                  strokeOpacity={0.9}
                />
                {start && (
                  <>
                    <circle
                      cx={project.px(start.x)}
                      cy={project.py(start.y)}
                      r={5}
                      fill={color}
                    />
                    <text
                      x={project.px(start.x) + 8}
                      y={project.py(start.y) - 6}
                      fill={color}
                      fontSize={11}
                    >
                      D{route.droneId} start
                    </text>
                  </>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="flex flex-wrap gap-3">
        {execution.routes.map((route, i) => (
          <div
            key={route.droneId}
            className="flex items-center gap-1.5 text-[10px] text-neutral-400"
          >
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: ROUTE_COLORS[i % ROUTE_COLORS.length] }}
            />
            Drone {route.droneId} · {route.waypoints.length} waypoints
          </div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-md border border-neutral-800">
        <table className="w-full text-left text-[11px]">
          <thead className="bg-neutral-900 text-neutral-400">
            <tr>
              <th className="px-2 py-1 font-normal">Sequence</th>
              <th className="px-2 py-1 font-normal">Drone</th>
              <th className="px-2 py-1 font-normal">Sector</th>
              <th className="px-2 py-1 font-normal">Passes</th>
              <th className="px-2 py-1 font-normal">Distance</th>
              <th className="px-2 py-1 font-normal">Est. time</th>
              <th className="px-2 py-1 font-normal">Timeline</th>
            </tr>
          </thead>
          <tbody className="text-neutral-300">
            {summaries.map((route, i) => {
              const dt = timeline.drones.find((d) => d.droneId === route.droneId);
              return (
                <tr key={`${route.droneId}-${i}`} className="border-t border-neutral-800">
                  <td className="px-2 py-1 text-neutral-500">#{i + 1}</td>
                  <td className="px-2 py-1">D{route.droneId ?? "—"}</td>
                  <td className="px-2 py-1">{route.sectorId ?? "—"}</td>
                  <td className="px-2 py-1">{route.numPasses ?? "—"}</td>
                  <td className="px-2 py-1">
                    {route.totalDistanceM != null
                      ? `${route.totalDistanceM.toFixed(0)} m`
                      : "—"}
                  </td>
                  <td className="px-2 py-1">
                    {route.estimatedTimeMin != null
                      ? `${route.estimatedTimeMin.toFixed(1)} min`
                      : "—"}
                  </td>
                  <td className="px-2 py-1">{dt?.durationFormatted ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {timeline.summary && (
        <p className="text-[11px] text-neutral-400">{timeline.summary}</p>
      )}
    </div>
  );
}
