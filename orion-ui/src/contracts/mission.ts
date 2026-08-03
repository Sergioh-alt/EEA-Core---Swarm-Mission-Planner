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

/** Origin of an uploaded field image. */
export type FieldImageSource = "satellite" | "drone" | "manual";

/** Reference to an uploaded field annotation image (metadata only). */
export interface FieldImage {
  readonly image_id: string;
  readonly filename: string;
  readonly source: FieldImageSource;
  /** Backend path to fetch the image bytes (read-only). */
  readonly url: string;
  readonly width_px: number;
  readonly height_px: number;
  readonly uploaded_ms: number;
}

export interface FieldSpec {
  readonly name: string;
  readonly crop_type: string;
  readonly boundary_points: readonly MetricPoint[];
  readonly area_ha?: number | null;
  readonly zones: readonly Zone[];
  readonly obstacles: readonly Obstacle[];
  readonly images: readonly FieldImage[];
  /**
   * Scale relating the annotation image to metric space. Operator drawings on
   * the uploaded image are stored as metric geometry (meters) using this scale.
   */
  readonly meters_per_pixel: number;
  readonly location: string;
  readonly notes: string;
}

/** A persisted, reusable field: its FieldSpec plus identity + timestamps. */
export interface FieldDefinition extends FieldSpec {
  readonly id: string;
  readonly version: number;
  readonly created_ms: number;
  readonly updated_ms: number;
}

export interface EnvironmentParams {
  readonly temperature_c: number;
  readonly wind_speed_kmh: number;
}

export type PlanningMode = "manual" | "assisted" | "automatic";

export type CoverageDirection = "auto" | "north_south" | "east_west";
export type RoutePreference = "balanced" | "time" | "battery";

export interface OperationParams {
  readonly operation_type: string;
  readonly num_drones: number;
  readonly flight_altitude_m?: number | null;
  readonly planning_mode: PlanningMode;
  /** Mission Designer preferences (10D.4) — hints only, Planning Core decides. */
  readonly nominal_speed_ms?: number | null;
  readonly overlap_pct?: number | null;
  readonly safety_margin_m?: number | null;
  readonly coverage_direction?: CoverageDirection;
  readonly route_preference?: RoutePreference;
}

export interface ProductSelection {
  readonly product_id: string;
  readonly name: string;
  readonly rate_l_per_ha?: number | null;
  /** Mission Designer application details (10D.4) — captured, not allocated. */
  readonly tank?: string | null;
  readonly concentration_pct?: number | null;
  readonly dilution?: string | null;
  readonly safety_notes?: string;
}

/**
 * An operator-assigned tank on a selected drone (Fleet Configuration, 10D.5).
 * Assignment intent only — consumption/feasibility stay with the Planning Core.
 */
export interface TankConfig {
  readonly tank_id: string;
  readonly label?: string;
  readonly capacity_l?: number | null;
  readonly product_id?: string | null;
  readonly product_name?: string | null;
}

export interface FleetItem {
  readonly drone_id: number;
  readonly model: string;
  readonly vendor: string;
  readonly battery_capacity_mah: number;
  readonly liquid_capacity_l: number;
  readonly working_width_m?: number | null;
  /** Fleet Configuration enrichment (10D.5) — catalog specs + operator config. */
  readonly status?: string | null;
  readonly payload_capacity_kg?: number | null;
  readonly estimated_flight_time_min?: number | null;
  readonly supported_operations?: readonly string[];
  readonly sensors?: readonly string[];
  readonly equipment?: readonly string[];
  readonly camera_package?: string | null;
  readonly sprayer_config?: string | null;
  readonly granular_spreader?: string | null;
  readonly tanks?: readonly TankConfig[];
}

export type MissionPriority = "low" | "normal" | "high" | "urgent";

/** The central editable contract every planning screen writes to. */
export interface MissionDefinition {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly version: number;
  readonly created_ms: number;
  readonly updated_ms: number;
  readonly field: FieldSpec;
  /** Source prepared field this definition was built from (10D.4). */
  readonly field_id?: string;
  readonly priority?: MissionPriority;
  /** Operator estimate (ISO date). Captured only — not a schedule. */
  readonly scheduled_date?: string;
  readonly notes?: string;
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

/** A tank slot advertised by a drone model in the inventory (read-only). */
export interface FleetModelTank {
  readonly tank_id: string;
  readonly label: string;
  readonly capacity_l: number;
}

/** A selectable drone model from the read-only Fleet Inventory. */
export interface FleetModel {
  readonly model: string;
  readonly vendor: string;
  readonly battery_capacity_mah: number;
  readonly liquid_capacity_l: number;
  readonly working_width_m?: number | null;
  readonly max_speed_kmh?: number | null;
  /** Read-only catalog specifications surfaced by Fleet Configuration (10D.5). */
  readonly status?: string;
  readonly payload_capacity_kg?: number | null;
  readonly estimated_flight_time_min?: number | null;
  readonly tanks?: readonly FleetModelTank[];
  readonly supported_operations?: readonly string[];
  readonly sensors?: readonly string[];
  readonly equipment?: readonly string[];
  readonly camera_packages?: readonly string[];
  readonly sprayer_configs?: readonly string[];
}

export interface FleetInventory {
  readonly drone_models: readonly FleetModel[];
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
  /** Upload an image to a field (raw body). */
  FIELD_IMAGES: (fieldId: string) => `/api/fields/${fieldId}/images`,
  /** Fetch an uploaded field image (read-only). */
  FIELD_IMAGE: (fieldId: string, imageId: string) =>
    `/api/fields/${fieldId}/images/${imageId}`,
  /** Mission definitions (list / create). */
  MISSIONS: "/api/missions",
  /** A single mission definition. */
  MISSION: (missionId: string) => `/api/missions/${missionId}`,
  /** Generate a Mission Package for a stored definition. */
  MISSION_PACKAGE: (missionId: string) => `/api/missions/${missionId}/package`,
  /** Compute a Mission Package (inline definition or {mission_id}). */
  PLANNING_COMPUTE: "/api/planning/compute",
} as const;
