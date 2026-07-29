/**
 * Field annotation geometry helpers (Phase 10D.3).
 *
 * Pure client-side conversions between image-pixel space (where the operator
 * draws) and the metric space (meters) stored in the Mission Definition
 * contract. These are coordinate transforms and measurements only — no
 * planning, routing, or optimization is performed here.
 */

import type { MetricPoint } from "@/contracts/mission";

export type PixelPoint = readonly [number, number];

/** Pixel → metric using the field's meters-per-pixel scale. */
export function pixelToMetric(p: PixelPoint, metersPerPixel: number): MetricPoint {
  return [p[0] * metersPerPixel, p[1] * metersPerPixel];
}

/** Metric → pixel (for rendering stored geometry on the image). */
export function metricToPixel(p: MetricPoint, metersPerPixel: number): PixelPoint {
  const mpp = metersPerPixel || 1;
  return [p[0] / mpp, p[1] / mpp];
}

/** Signed polygon area (shoelace), square meters. */
export function polygonAreaM2(points: readonly MetricPoint[]): number {
  if (points.length < 3) return 0;
  let sum = 0;
  for (let i = 0; i < points.length; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % points.length];
    sum += x1 * y2 - x2 * y1;
  }
  return Math.abs(sum) / 2;
}

/** Polygon area in hectares. */
export function polygonAreaHa(points: readonly MetricPoint[]): number {
  return polygonAreaM2(points) / 10000;
}

/** Format a metric polygon area for display. */
export function formatAreaHa(points: readonly MetricPoint[]): string {
  const ha = polygonAreaHa(points);
  if (ha >= 1) return `${ha.toFixed(2)} ha`;
  return `${polygonAreaM2(points).toFixed(0)} m²`;
}

/** SVG path "d" for a closed polygon in pixel coordinates. */
export function pixelPolygonPath(points: readonly PixelPoint[]): string {
  if (points.length === 0) return "";
  const [first, ...rest] = points;
  const move = `M ${first[0]} ${first[1]}`;
  const lines = rest.map((p) => `L ${p[0]} ${p[1]}`).join(" ");
  return `${move} ${lines} Z`.trim();
}
