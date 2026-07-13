/**
 * Phase 10C.2 — TypeScript Type Contracts.
 *
 * Mirror of Digital Twin Python models (1:1).
 * All types are read-only from the UI perspective.
 *
 * Source of truth: digital_twin/state_models.py
 */

// =========================================================================
// Enumerations
// =========================================================================

export enum MissionStatus {
  IDLE = "IDLE",
  RUNNING = "RUNNING",
  PAUSED = "PAUSED",
  FAILED = "FAILED",
  COMPLETED = "COMPLETED",
}

export enum DroneMode {
  STANDBY = "STANDBY",
  MANUAL = "MANUAL",
  GUIDED = "GUIDED",
  AUTO = "AUTO",
  RTL = "RTL",
  LAND = "LAND",
}

export enum HealthLevel {
  OK = "OK",
  WARNING = "WARNING",
  CRITICAL = "CRITICAL",
}

export enum TaskState {
  NONE = "NONE",
  IN_PROGRESS = "IN_PROGRESS",
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
}

export enum FailureCategory {
  BATTERY_DEGRADATION = "battery_degradation",
  GPS_LOSS = "gps_loss",
  LINK_LOSS = "link_loss",
  WIND_DISTURBANCE = "wind_disturbance",
}

export enum EnvironmentCondition {
  NOMINAL = "NOMINAL",
  DEGRADED = "DEGRADED",
  SEVERE = "SEVERE",
}

// =========================================================================
// Core Data Models (immutable from UI perspective)
// =========================================================================

export interface Position {
  readonly latitude: number;
  readonly longitude: number;
  readonly altitude_m: number;
}

export interface Velocity {
  readonly vx: number;
  readonly vy: number;
  readonly vz: number;
}

export interface DroneState {
  readonly drone_id: number;
  readonly armed: boolean;
  readonly mode: DroneMode;
  readonly position: Position;
  readonly velocity: Velocity;
  readonly heading_deg: number;
  readonly battery_pct: number;
  readonly battery_voltage: number;
  readonly gps_available: boolean;
  readonly gps_accuracy_m: number;
  readonly communication_active: boolean;
  readonly health: HealthLevel;
  readonly current_task: TaskState;
  readonly last_update_ms: number;
}

export interface EnvironmentState {
  readonly wind_speed_m_s: number;
  readonly wind_direction_deg: number;
  readonly condition: EnvironmentCondition;
  readonly timestamp_ms: number;
}

export interface SwarmState {
  readonly swarm_id: string;
  readonly timestamp_ms: number;
  readonly mission_status: MissionStatus;
  readonly mission_id: string | null;
  readonly simulation_time_ms: number;
  readonly drone_states: readonly DroneState[];
  readonly global_health: HealthLevel;
  readonly active_failures: readonly FailureCategory[];
  readonly environment_state: EnvironmentState;
  readonly total_drones: number;
  readonly active_drones: number;
  readonly failed_drones: number;
  readonly version: number;
}

// =========================================================================
// Snapshot & Replay Models
// =========================================================================

export interface Snapshot {
  readonly snapshot_id: string;
  readonly version: number;
  readonly timestamp_ms: number;
  readonly swarm_state: SwarmState;
  readonly description: string;
}

export interface SnapshotMetadata {
  readonly snapshot_id: string;
  readonly version: number;
  readonly timestamp_ms: number;
  readonly description: string;
}

export interface ReplayFrame {
  readonly frame_index: number;
  readonly timestamp_ms: number;
  readonly swarm_state: SwarmState;
}

export interface DroneReplayFrame {
  readonly frame_index: number;
  readonly timestamp_ms: number;
  readonly drone_state: DroneState;
}

export interface ReplayTimeline {
  readonly timeline_id: string;
  readonly start_ms: number;
  readonly end_ms: number;
  readonly frames: readonly ReplayFrame[];
  readonly total_frames: number;
  readonly description: string;
}

export interface DroneReplayTimeline {
  readonly drone_id: number;
  readonly timeline_id: string;
  readonly start_ms: number;
  readonly end_ms: number;
  readonly frames: readonly DroneReplayFrame[];
  readonly total_frames: number;
}

// =========================================================================
// Alert Model
// =========================================================================

export type AlertSeverity = "INFO" | "WARNING" | "CRITICAL";

export interface Alert {
  readonly id: string;
  readonly severity: AlertSeverity;
  readonly source: string;
  readonly message: string;
  readonly category: FailureCategory | "SYSTEM" | "ENVIRONMENT";
  readonly timestamp_ms: number;
  readonly active: boolean;
  readonly resolved_ms: number | null;
}

// =========================================================================
// Transport DTOs (Phase 10C.4) — served by the Digital Twin API layer.
// These carry backend-provided geometry/analytics/mission lifecycle. The UI
// only visualizes them; it never computes or invents these values.
// =========================================================================

export interface LatLng {
  readonly lat: number;
  readonly lng: number;
}

export interface MissionGeometry {
  readonly field_center: LatLng;
  readonly field_polygon: readonly LatLng[];
  readonly planned_routes: Readonly<Record<string, readonly LatLng[]>>;
}

export interface MissionEventDTO {
  readonly id: string;
  readonly timestamp_ms: number;
  readonly type:
    | "START"
    | "PAUSE"
    | "RESUME"
    | "STOP"
    | "FAILURE"
    | "RECOVERY"
    | "MILESTONE";
  readonly message: string;
}

export interface MissionInfo {
  readonly mission_id: string | null;
  readonly status: MissionStatus;
  readonly progress: number;
  readonly start_ms: number | null;
  readonly end_ms: number | null;
  readonly events: readonly MissionEventDTO[];
}

export interface BatteryTrendPoint {
  readonly version: number;
  readonly timestamp_ms: number;
  readonly battery_pct: number;
}

export interface FleetUtilizationPoint {
  readonly version: number;
  readonly timestamp_ms: number;
  readonly active_drones: number;
  readonly failed_drones: number;
  readonly total_drones: number;
}

export interface AnalyticsData {
  readonly snapshot_count: number;
  readonly battery_trends: Readonly<Record<string, readonly BatteryTrendPoint[]>>;
  readonly fleet_utilization: readonly FleetUtilizationPoint[];
  readonly alert_frequency: Readonly<Record<string, number>>;
  readonly mission: {
    readonly mission_id: string | null;
    readonly status: MissionStatus;
    readonly progress: number;
    readonly duration_ms: number;
  };
}
