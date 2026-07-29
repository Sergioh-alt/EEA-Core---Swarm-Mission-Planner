"use client";

import { useCallback, useRef } from "react";
import type { MetricPoint, Obstacle, Zone } from "@/contracts/mission";
import {
  metricToPixel,
  pixelPolygonPath,
  type PixelPoint,
} from "@/lib/fieldGeometry";

export type DrawTool =
  | "select"
  | "boundary"
  | "crop"
  | "management"
  | "treatment"
  | "exclusion"
  | "obstacle";

/** Fill/stroke palette per geometry layer (visualization only). */
export const LAYER_STYLES: Record<
  string,
  { stroke: string; fill: string; label: string }
> = {
  boundary: { stroke: "#3b82f6", fill: "rgba(59,130,246,0.12)", label: "Boundary" },
  crop: { stroke: "#22c55e", fill: "rgba(34,197,94,0.16)", label: "Crop zone" },
  management: { stroke: "#eab308", fill: "rgba(234,179,8,0.16)", label: "Management zone" },
  treatment: { stroke: "#a855f7", fill: "rgba(168,85,247,0.16)", label: "Treatment zone" },
  exclusion: { stroke: "#ef4444", fill: "rgba(239,68,68,0.18)", label: "Exclusion zone" },
  obstacle: { stroke: "#f97316", fill: "rgba(249,115,22,0.22)", label: "Obstacle" },
};

interface FieldCanvasProps {
  imageUrl: string | null;
  width: number;
  height: number;
  metersPerPixel: number;
  boundary: readonly MetricPoint[];
  zones: readonly Zone[];
  obstacles: readonly Obstacle[];
  tool: DrawTool;
  draft: readonly PixelPoint[];
  selectedId: string | null;
  onCanvasClick: (point: PixelPoint) => void;
  onFinish: () => void;
  onSelect: (id: string | null) => void;
}

export function FieldCanvas({
  imageUrl,
  width,
  height,
  metersPerPixel,
  boundary,
  zones,
  obstacles,
  tool,
  draft,
  selectedId,
  onCanvasClick,
  onFinish,
  onSelect,
}: FieldCanvasProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const drawing = tool !== "select";

  const toSvgPoint = useCallback(
    (clientX: number, clientY: number): PixelPoint | null => {
      const svg = svgRef.current;
      if (!svg) return null;
      const ctm = svg.getScreenCTM();
      if (!ctm) return null;
      const pt = svg.createSVGPoint();
      pt.x = clientX;
      pt.y = clientY;
      const local = pt.matrixTransform(ctm.inverse());
      return [Math.round(local.x), Math.round(local.y)];
    },
    []
  );

  const handleClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!drawing) return;
      const point = toSvgPoint(e.clientX, e.clientY);
      if (point) onCanvasClick(point);
    },
    [drawing, toSvgPoint, onCanvasClick]
  );

  const boundaryPx = boundary.map((p) => metricToPixel(p, metersPerPixel));
  const draftStyle = LAYER_STYLES[tool] ?? LAYER_STYLES.boundary;

  return (
    <div className="relative h-full w-full overflow-auto rounded-md border border-neutral-800 bg-neutral-950">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        className={drawing ? "block w-full cursor-crosshair" : "block w-full"}
        onClick={handleClick}
        onDoubleClick={(e) => {
          e.preventDefault();
          if (drawing) onFinish();
        }}
      >
        {imageUrl ? (
          <image
            href={imageUrl}
            x={0}
            y={0}
            width={width}
            height={height}
            preserveAspectRatio="xMidYMid meet"
          />
        ) : (
          <rect x={0} y={0} width={width} height={height} fill="#0a0a0a" />
        )}

        {/* Boundary */}
        {boundaryPx.length >= 2 && (
          <path
            d={pixelPolygonPath(boundaryPx)}
            stroke={LAYER_STYLES.boundary.stroke}
            fill={LAYER_STYLES.boundary.fill}
            strokeWidth={2}
            vectorEffect="non-scaling-stroke"
          />
        )}

        {/* Zones */}
        {zones.map((z) => {
          const pts = z.boundary_points.map((p) =>
            metricToPixel(p, metersPerPixel)
          );
          if (pts.length < 2) return null;
          const style = LAYER_STYLES[z.kind] ?? LAYER_STYLES.crop;
          const selected = z.zone_id === selectedId;
          return (
            <path
              key={z.zone_id}
              d={pixelPolygonPath(pts)}
              stroke={style.stroke}
              fill={style.fill}
              strokeWidth={selected ? 4 : 2}
              strokeDasharray={z.enabled === false ? "6 4" : undefined}
              vectorEffect="non-scaling-stroke"
              className={tool === "select" ? "cursor-pointer" : ""}
              onClick={(e) => {
                if (tool === "select") {
                  e.stopPropagation();
                  onSelect(z.zone_id);
                }
              }}
            />
          );
        })}

        {/* Obstacles */}
        {obstacles.map((o) => {
          const pts = o.points.map((p) => metricToPixel(p, metersPerPixel));
          if (pts.length < 2) return null;
          const style = LAYER_STYLES.obstacle;
          const selected = o.obstacle_id === selectedId;
          return (
            <path
              key={o.obstacle_id}
              d={pixelPolygonPath(pts)}
              stroke={style.stroke}
              fill={style.fill}
              strokeWidth={selected ? 4 : 2}
              vectorEffect="non-scaling-stroke"
              className={tool === "select" ? "cursor-pointer" : ""}
              onClick={(e) => {
                if (tool === "select") {
                  e.stopPropagation();
                  onSelect(o.obstacle_id);
                }
              }}
            />
          );
        })}

        {/* In-progress draft */}
        {draft.length > 0 && (
          <>
            <polyline
              points={draft.map((p) => `${p[0]},${p[1]}`).join(" ")}
              stroke={draftStyle.stroke}
              fill="none"
              strokeWidth={2}
              strokeDasharray="4 3"
              vectorEffect="non-scaling-stroke"
            />
            {draft.map((p, i) => (
              <circle
                key={i}
                cx={p[0]}
                cy={p[1]}
                r={4}
                fill={draftStyle.stroke}
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </>
        )}
      </svg>
    </div>
  );
}
