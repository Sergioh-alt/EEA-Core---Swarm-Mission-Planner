/**
 * Typed read-only views over a Mission Package (Phase 10D.6).
 *
 * The package sub-objects mirror the backend `core/` result shapes and are
 * typed as records on the wire. These helpers narrow them safely so Mission
 * Review can *display* Planning Core values without recomputing any of them:
 * every number here is read, never derived.
 */

import type { MissionPackage } from "@/contracts/mission";

function obj(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function str(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function numOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function boolOrNull(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function strList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

export interface RecommendationView {
  readonly goNoGo: string | null;
  readonly feasible: boolean | null;
  readonly confidencePct: number | null;
  readonly coveragePct: number | null;
  readonly estimatedDuration: string | null;
  readonly recommendedDrones: number | null;
  readonly summary: string | null;
  readonly operationalNotes: readonly string[];
  readonly optimizationSuggestions: readonly string[];
}

export function recommendationOf(pkg: MissionPackage): RecommendationView {
  const r = obj(pkg.recommendation);
  return {
    goNoGo: str(r.go_no_go),
    feasible: boolOrNull(r.feasible),
    confidencePct: numOrNull(r.confidence_pct),
    coveragePct: numOrNull(r.coverage_pct),
    estimatedDuration: str(r.estimated_duration),
    recommendedDrones: numOrNull(r.recommended_drones),
    summary: str(r.summary),
    operationalNotes: strList(r.operational_notes),
    optimizationSuggestions: strList(r.optimization_suggestions),
  };
}

export interface DroneResourceView {
  readonly droneId: number | null;
  readonly batteryConsumptionPct: number | null;
  readonly liquidNeededL: number | null;
  readonly liquidRefills: number | null;
  readonly flightTimeMin: number | null;
  readonly totalTimeMin: number | null;
}

export interface ResourcesView {
  readonly totalLiquidL: number | null;
  readonly totalRefills: number | null;
  readonly totalBatteryCycles: number | null;
  readonly durationMin: number | null;
  readonly durationFormatted: string | null;
  readonly bottleneck: string | null;
  readonly drones: readonly DroneResourceView[];
}

export function resourcesOf(pkg: MissionPackage): ResourcesView {
  const r = obj(pkg.resources);
  const rows = Array.isArray(r.drone_resources) ? r.drone_resources : [];
  return {
    totalLiquidL: numOrNull(r.total_liquid_l),
    totalRefills: numOrNull(r.total_refills),
    totalBatteryCycles: numOrNull(r.total_battery_cycles),
    durationMin: numOrNull(r.mission_duration_min),
    durationFormatted: str(r.mission_duration_formatted),
    bottleneck: str(r.bottleneck),
    drones: rows.map((row) => {
      const d = obj(row);
      return {
        droneId: numOrNull(d.drone_id),
        batteryConsumptionPct: numOrNull(d.battery_consumption_pct),
        liquidNeededL: numOrNull(d.liquid_needed_l),
        liquidRefills: numOrNull(d.liquid_refills),
        flightTimeMin: numOrNull(d.flight_time_min),
        totalTimeMin: numOrNull(d.total_time_min),
      };
    }),
  };
}

export interface RiskRowView {
  readonly category: string | null;
  readonly level: string | null;
  readonly description: string | null;
  readonly mitigation: string | null;
}

export interface RisksView {
  readonly overallRisk: string | null;
  readonly overallScore: number | null;
  readonly missionViable: boolean | null;
  readonly criticalRisks: readonly string[];
  readonly rows: readonly RiskRowView[];
}

export function risksOf(pkg: MissionPackage): RisksView {
  const r = obj(pkg.risks);
  const rows = Array.isArray(r.risks) ? r.risks : [];
  return {
    overallRisk: str(r.overall_risk),
    overallScore: numOrNull(r.overall_score),
    missionViable: boolOrNull(r.mission_viable),
    criticalRisks: strList(r.critical_risks),
    rows: rows.map((row) => {
      const d = obj(row);
      return {
        category: str(d.category),
        level: str(d.level),
        description: str(d.description),
        mitigation: str(d.mitigation),
      };
    }),
  };
}

export interface DroneTimelineView {
  readonly droneId: number | null;
  readonly durationFormatted: string | null;
  readonly sprayTimeMin: number | null;
  readonly transitTimeMin: number | null;
  readonly idleTimeMin: number | null;
}

export interface TimelineView {
  readonly durationMin: number | null;
  readonly durationFormatted: string | null;
  readonly totalEvents: number | null;
  readonly summary: string | null;
  readonly drones: readonly DroneTimelineView[];
}

export function timelineOf(pkg: MissionPackage): TimelineView {
  const t = obj(pkg.timeline);
  const rows = Array.isArray(t.drone_timelines) ? t.drone_timelines : [];
  return {
    durationMin: numOrNull(t.mission_duration_min),
    durationFormatted: str(t.mission_duration_formatted),
    totalEvents: numOrNull(t.total_events),
    summary: str(t.summary),
    drones: rows.map((row) => {
      const d = obj(row);
      return {
        droneId: numOrNull(d.drone_id),
        durationFormatted: str(d.total_duration_formatted),
        sprayTimeMin: numOrNull(d.spray_time_min),
        transitTimeMin: numOrNull(d.transit_time_min),
        idleTimeMin: numOrNull(d.idle_time_min),
      };
    }),
  };
}

export interface GeometryView {
  readonly areaHa: number | null;
  readonly areaM2: number | null;
  readonly perimeterM: number | null;
  readonly isSynthetic: boolean | null;
}

export function geometryOf(pkg: MissionPackage): GeometryView {
  const g = obj(pkg.field_geometry);
  return {
    areaHa: numOrNull(g.area_ha),
    areaM2: numOrNull(g.area_m2),
    perimeterM: numOrNull(g.perimeter_m),
    isSynthetic: boolOrNull(g.is_synthetic),
  };
}

export interface EnvironmentView {
  readonly areaCategory: string | null;
  readonly complexity: string | null;
  readonly weatherStatus: string | null;
  readonly flightConditions: string | null;
  readonly recommendedSpeedKmh: number | null;
  readonly effectiveSprayWidthM: number | null;
}

export function environmentOf(pkg: MissionPackage): EnvironmentView {
  const e = obj(pkg.environment_assessment);
  return {
    areaCategory: str(e.area_category),
    complexity: str(e.operational_complexity),
    weatherStatus: str(e.weather_status),
    flightConditions: str(e.flight_conditions),
    recommendedSpeedKmh: numOrNull(e.recommended_speed_kmh),
    effectiveSprayWidthM: numOrNull(e.effective_spray_width_m),
  };
}

export interface RouteSummaryView {
  readonly droneId: number | null;
  readonly sectorId: number | null;
  readonly numPasses: number | null;
  readonly totalDistanceM: number | null;
  readonly estimatedTimeMin: number | null;
}

export function routeSummariesOf(pkg: MissionPackage): RouteSummaryView[] {
  return pkg.routes.map((row) => {
    const d = obj(row);
    return {
      droneId: numOrNull(d.drone_id),
      sectorId: numOrNull(d.sector_id),
      numPasses: numOrNull(d.num_passes),
      totalDistanceM: numOrNull(d.total_distance_m),
      estimatedTimeMin: numOrNull(d.estimated_time_min),
    };
  });
}

export interface Waypoint {
  readonly x: number;
  readonly y: number;
  readonly sequence: number;
}

export interface ExecutionRouteView {
  readonly droneId: number;
  readonly waypoints: readonly Waypoint[];
}

/** Geometry the read-only preview draws — straight from the package. */
export interface ExecutionView {
  readonly operationType: string | null;
  readonly numDrones: number | null;
  readonly flightAltitudeM: number | null;
  readonly fieldPolygon: readonly (readonly [number, number])[];
  readonly routes: readonly ExecutionRouteView[];
}

export function executionOf(pkg: MissionPackage): ExecutionView {
  const e = obj(pkg.execution);
  const rawPolygon = Array.isArray(e.field_polygon_m) ? e.field_polygon_m : [];
  const polygon: [number, number][] = [];
  for (const point of rawPolygon) {
    if (Array.isArray(point) && point.length >= 2) {
      const x = numOrNull(point[0]);
      const y = numOrNull(point[1]);
      if (x !== null && y !== null) polygon.push([x, y]);
    }
  }
  const rawRoutes = Array.isArray(e.routes_m) ? e.routes_m : [];
  const routes: ExecutionRouteView[] = [];
  for (const row of rawRoutes) {
    const d = obj(row);
    const droneId = numOrNull(d.drone_id);
    if (droneId === null) continue;
    const rawWps = Array.isArray(d.waypoints) ? d.waypoints : [];
    const waypoints: Waypoint[] = [];
    for (const wp of rawWps) {
      const w = obj(wp);
      const x = numOrNull(w.x);
      const y = numOrNull(w.y);
      if (x === null || y === null) continue;
      waypoints.push({ x, y, sequence: numOrNull(w.sequence) ?? waypoints.length });
    }
    routes.push({ droneId, waypoints });
  }
  return {
    operationType: str(e.operation_type),
    numDrones: numOrNull(e.num_drones),
    flightAltitudeM: numOrNull(e.flight_altitude_m),
    fieldPolygon: polygon,
    routes,
  };
}
