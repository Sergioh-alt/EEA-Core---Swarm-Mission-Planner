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

/**
 * Mission Review & Deployment (Phase 10D.6).
 *
 * Mission Review only visualizes the Mission Package, records operator
 * confirmations and authorizes deployment. States after `deployed` belong to
 * Mission Control and the Digital Twin and are shown for context only.
 */
export type DeploymentState =
  | "draft"
  | "ready_for_review"
  | "approved"
  | "deploying"
  | "deployed"
  | "executing"
  | "completed"
  | "archived";

/** Ordered lifecycle used by the deployment status visualization. */
export const DEPLOYMENT_STATES: readonly DeploymentState[] = [
  "draft",
  "ready_for_review",
  "approved",
  "deploying",
  "deployed",
  "executing",
  "completed",
  "archived",
] as const;

export const DEPLOYMENT_STATE_LABELS: Record<DeploymentState, string> = {
  draft: "Draft",
  ready_for_review: "Ready for Review",
  approved: "Approved",
  deploying: "Deploying",
  deployed: "Deployed",
  executing: "Executing",
  completed: "Completed",
  archived: "Archived",
};

/** States owned by Mission Control / the Digital Twin, not Mission Review. */
export const RUNTIME_OWNED_STATES: readonly DeploymentState[] = [
  "executing",
  "completed",
  "archived",
];

/** A single operator confirmation. Never alters Planning Core output. */
export interface ChecklistItem {
  readonly item_id: string;
  readonly label: string;
  readonly confirmed: boolean;
  readonly required: boolean;
}

/** Review/deployment state of one Mission Definition (backend-owned). */
export interface DeploymentRecord {
  readonly mission_id: string;
  readonly state: DeploymentState;
  readonly checklist: readonly ChecklistItem[];
  readonly checklist_complete: boolean;
  /** Deployed definitions are immutable — create a new one to change anything. */
  readonly locked: boolean;
  /** The immutable package handed to the Digital Twin (present once deployed). */
  readonly package: MissionPackage | null;
  readonly definition_version: number | null;
  readonly deployment_id: string | null;
  readonly deployed_ms: number | null;
  readonly updated_ms: number;
}

/** Everything the Mission Review workspace renders. */
export interface MissionReview {
  readonly mission: MissionDefinition;
  readonly package: MissionPackage;
  readonly deployment: DeploymentRecord;
  /** False when no Digital Twin deployment interface is attached. */
  readonly deployment_available: boolean;
}

/** Digital Twin acknowledgement of a deployed Mission Package. */
export interface DeploymentReceipt {
  readonly accepted: boolean;
  readonly deployment_id: string;
  readonly definition_id: string;
  readonly deployed_ms: number;
  readonly route_count: number;
  readonly mission_status: string;
}

export interface DeploymentResult {
  readonly deployment: DeploymentRecord;
  readonly receipt: DeploymentReceipt;
}

/** The Mission Package currently deployed to the Digital Twin. */
export interface TwinDeployment {
  readonly deployed: boolean;
  readonly deployment_id: string | null;
  readonly deployed_ms: number | null;
  readonly package: MissionPackage | null;
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

// ---------------------------------------------------------------------------
// Mission Library & Scheduler (Phase 10D.7)
// ---------------------------------------------------------------------------

export type LibraryEntryStatus = "ready" | "archived";

/** Projection of stored definition/package values, computed by the backend. */
export interface LibraryEntrySummary {
  readonly field_name: string;
  readonly crop_type: string;
  readonly location: string;
  readonly operation_type: string;
  readonly zone_count: number;
  readonly products: readonly string[];
  readonly fleet_count: number;
  readonly priority: string;
  readonly area_ha: number | null;
  readonly route_count: number | null;
  readonly go_no_go: string | null;
  readonly estimated_duration: string | null;
}

/** A saved, reusable mission: a Mission Definition + its Mission Package. */
export interface LibraryEntry {
  readonly entry_id: string;
  readonly name: string;
  readonly description: string;
  readonly template: boolean;
  readonly status: LibraryEntryStatus;
  readonly source_mission_id: string;
  readonly definition: MissionDefinition;
  readonly definition_version: number;
  readonly package: MissionPackage | null;
  readonly package_definition_version: number | null;
  readonly package_stale: boolean;
  readonly version: number;
  readonly created_ms: number;
  readonly updated_ms: number;
  readonly summary: LibraryEntrySummary;
}

export type Recurrence = "one_time" | "daily" | "weekly" | "custom";

export const RECURRENCE_LABELS: Record<Recurrence, string> = {
  one_time: "One-time",
  daily: "Daily",
  weekly: "Weekly",
  custom: "Custom repeat",
};

/** The operator's explicit scheduling intent, plus its own occurrences. */
export interface MissionSchedule {
  readonly schedule_id: string;
  readonly entry_id: string;
  readonly label: string;
  readonly notes: string;
  readonly start_date: string;
  readonly times: readonly string[];
  readonly recurrence: Recurrence;
  readonly weekdays: readonly number[];
  readonly interval_days: number;
  readonly enabled: boolean;
  readonly last_triggered_ms: number | null;
  readonly last_result: string;
  readonly created_ms: number;
  readonly updated_ms: number;
  readonly next_occurrence_ms: number | null;
  readonly upcoming_ms: readonly number[];
}

export type ExecutionStatus = "running" | "completed" | "interrupted";
export type ExecutionTrigger = "manual" | "scheduled";

/** Planning Core figures the execution was started with (never recomputed). */
export interface ExecutionPlanned {
  readonly coverage_pct: number | null;
  readonly confidence_pct: number | null;
  readonly go_no_go: string | null;
  readonly duration_formatted: string | null;
  readonly duration_min: number | null;
  readonly total_liquid_l: number | null;
  readonly total_battery_cycles: number | null;
  readonly area_ha: number | null;
}

/** Digital Twin state mirrored into history; the runtime stays authoritative. */
export interface ExecutionRuntime {
  readonly status?: string;
  readonly progress?: number | null;
  readonly event_count?: number;
  readonly last_event?: string;
}

/** One past or ongoing execution — history, never a template. */
export interface ExecutionRecord {
  readonly execution_id: string;
  readonly entry_id: string;
  readonly definition_id: string;
  readonly mission_name: string;
  readonly field_name: string;
  readonly operation_type: string;
  readonly products: readonly string[];
  readonly drone_count: number;
  readonly route_count: number;
  readonly trigger: ExecutionTrigger;
  readonly schedule_id: string | null;
  readonly status: ExecutionStatus;
  readonly planned: ExecutionPlanned;
  readonly runtime: ExecutionRuntime;
  readonly warnings: readonly string[];
  readonly deployment_id: string | null;
  readonly started_ms: number;
  readonly ended_ms: number | null;
  readonly duration_ms: number | null;
}

export interface ExecutionResult {
  readonly execution: ExecutionRecord;
  readonly receipt: DeploymentReceipt;
}

export interface DuplicateResult {
  readonly mission: MissionDefinition;
  readonly source_entry_id: string;
}

/** Fields an operator may edit on a schedule; recurrence is never inferred. */
export interface ScheduleInput {
  readonly entry_id: string;
  readonly label?: string;
  readonly notes?: string;
  readonly start_date: string;
  readonly times: readonly string[];
  readonly recurrence: Recurrence;
  readonly weekdays?: readonly number[];
  readonly interval_days?: number;
  readonly enabled?: boolean;
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
  /** Mission Review payload: package + deployment record (10D.6). */
  MISSION_REVIEW: (missionId: string) => `/api/missions/${missionId}/review`,
  /** Operator checklist confirmations (10D.6). */
  MISSION_CHECKLIST: (missionId: string) => `/api/missions/${missionId}/checklist`,
  /** Submit the approved Mission Package to the Digital Twin (10D.6). */
  MISSION_DEPLOY: (missionId: string) => `/api/missions/${missionId}/deploy`,
  /** The Mission Package currently deployed to the Twin (Mission Control). */
  TWIN_DEPLOYMENT: "/api/twin/deployment",
  /** Saved reusable missions (list / save). */
  LIBRARY: "/api/library",
  /** A single saved mission. */
  LIBRARY_ENTRY: (entryId: string) => `/api/library/${entryId}`,
  /** Re-run the Planning Core for a saved mission's source definition. */
  LIBRARY_RESYNC: (entryId: string) => `/api/library/${entryId}/resync`,
  /** Copy a saved mission into a new Mission Definition. */
  LIBRARY_DUPLICATE: (entryId: string) => `/api/library/${entryId}/duplicate`,
  /** Hand a saved Mission Package to the Digital Twin. */
  LIBRARY_EXECUTE: (entryId: string) => `/api/library/${entryId}/execute`,
  /** Operator schedules (list / create). */
  SCHEDULES: "/api/schedules",
  /** A single schedule. */
  SCHEDULE: (scheduleId: string) => `/api/schedules/${scheduleId}`,
  /** Enable or disable a schedule. */
  SCHEDULE_ENABLED: (scheduleId: string) => `/api/schedules/${scheduleId}/enabled`,
  /** Execution history (separate from saved missions). */
  EXECUTIONS: "/api/executions",
  /** A single execution history record. */
  EXECUTION: (executionId: string) => `/api/executions/${executionId}`,
} as const;
