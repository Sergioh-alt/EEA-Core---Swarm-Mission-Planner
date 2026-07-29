/**
 * Mission Definition Pipeline contracts (Phase 10D.2).
 *
 * Design-time contract mirroring backend/mission_pipeline (Python). The UI
 * creates and edits a MissionDefinition; the backend Planning Core turns it
 * into a MissionPackage consumed by the Digital Twin. The UI never plans.
 *
 * These types are the frontend half of the API contract. They are consumed by
 * the planning screens introduced in sub-phases 10D.3+ (Field Acquisition,
 * Mission Designer, Fleet Configuration, Mission Review, Mission Library).
 */

/** Local metric coordinate (meters). */
export type MetricPoint = readonly [number, number];

export interface Zone {
  readonly zone_id: string;
  readonly kind: "crop" | "management" | "exclusion" | "treatment";
  readonly label: string;
  readonly boundary_points: readonly MetricPoint[];
  readonly crop_type?: string | null;
  readonly enabled?: boolean;
}

export interface Obstacle {
  readonly obstacle_id: string;
  readonly kind: "tree" | "pole" | "building" | "irrigation" | "road" | "restricted";
  readonly label: string;
  readonly points: readonly MetricPoint[];
}

export interface FieldSpec {
  readonly name: string;
  readonly crop_type: string;
  readonly boundary_points: readonly MetricPoint[];
  readonly area_ha?: number | null;
  readonly zones: readonly Zone[];
  readonly obstacles: readonly Obstacle[];
}

export interface EnvironmentParams {
  readonly temperature_c: number;
  readonly wind_speed_kmh: number;
}

export type PlanningMode = "manual" | "assisted" | "automatic";

export interface OperationParams {
  readonly operation_type: string;
  readonly num_drones: number;
  readonly flight_altitude_m?: number | null;
  readonly planning_mode: PlanningMode;
}

export interface ProductSelection {
  readonly product_id: string;
  readonly name: string;
  readonly rate_l_per_ha?: number | null;
}

export interface FleetItem {
  readonly drone_id: number;
  readonly model: string;
  readonly vendor: string;
  readonly battery_capacity_mah: number;
  readonly liquid_capacity_l: number;
  readonly working_width_m?: number | null;
}

/** The central editable contract every planning screen writes to. */
export interface MissionDefinition {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly version: number;
  readonly created_ms: number;
  readonly updated_ms: number;
  readonly field: FieldSpec;
  readonly operation: OperationParams;
  readonly environment: EnvironmentParams;
  readonly fleet: readonly FleetItem[];
  readonly products: readonly ProductSelection[];
}

/**
 * Planning-Core output. Fields are backend-generated and read-only; the UI
 * only visualizes them (Mission Review, deployment). Detailed sub-objects are
 * left as records because they mirror the existing core/ result shapes 1:1.
 */
export interface MissionPackage {
  readonly definition_id: string;
  readonly generated_ms: number;
  readonly field_geometry: Record<string, unknown>;
  readonly routes: readonly Record<string, unknown>[];
  readonly resources: Record<string, unknown>;
  readonly timeline: Record<string, unknown>;
  readonly risks: Record<string, unknown>;
  readonly recommendation: Record<string, unknown>;
  readonly environment_assessment: Record<string, unknown>;
  readonly validation: {
    readonly valid: boolean;
    readonly errors: readonly string[];
    readonly warnings: readonly string[];
  };
  readonly execution: Record<string, unknown>;
}

export interface FleetInventory {
  readonly drone_models: readonly Record<string, unknown>[];
  readonly products: readonly ProductSelection[];
  readonly crop_types: readonly string[];
}

/** Mission Definition Pipeline REST endpoints (backend-owned, design-time). */
export const PIPELINE_ENDPOINTS = {
  /** Available assets (drones, products, supported crops). */
  FLEET_INVENTORY: "/api/fleet/inventory",
  /** Field records (list / create). */
  FIELDS: "/api/fields",
  /** A single field record. */
  FIELD: (fieldId: string) => `/api/fields/${fieldId}`,
  /** Mission definitions (list / create). */
  MISSIONS: "/api/missions",
  /** A single mission definition. */
  MISSION: (missionId: string) => `/api/missions/${missionId}`,
  /** Generate a Mission Package for a stored definition. */
  MISSION_PACKAGE: (missionId: string) => `/api/missions/${missionId}/package`,
  /** Compute a Mission Package (inline definition or {mission_id}). */
  PLANNING_COMPUTE: "/api/planning/compute",
} as const;
