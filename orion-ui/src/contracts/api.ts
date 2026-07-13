/**
 * API endpoint contracts.
 *
 * REST endpoints for on-demand queries to Digital Twin.
 * WebSocket endpoint for real-time state streaming.
 */

export const API_ENDPOINTS = {
  /** Full swarm state */
  SWARM_STATE: "/api/twin/state",
  /** Single drone state */
  DRONE_STATE: (droneId: number) => `/api/twin/drone/${droneId}`,
  /** List snapshot metadata */
  SNAPSHOTS: "/api/twin/snapshots",
  /** Retrieve a specific snapshot */
  SNAPSHOT: (snapshotId: string) => `/api/twin/snapshots/${snapshotId}`,
  /** Start/manage replay */
  REPLAY: "/api/twin/replay",
  /** Drone replay timeline */
  DRONE_REPLAY: (droneId: number) => `/api/twin/replay/drone/${droneId}`,
  /** Submit intent */
  INTENTS: "/api/intents",
  /** Health check */
  HEALTH: "/api/health",
  /** Aggregated analytics (backend-computed) */
  ANALYTICS: "/api/twin/analytics",
  /** Static mission geometry (field polygon + planned routes) */
  MISSION_GEOMETRY: "/api/mission/geometry",
  /** Mission lifecycle status + events */
  MISSION_STATUS: "/api/mission/status",
  /** Full alert log */
  ALERTS: "/api/alerts",
} as const;

export const WS_ENDPOINT = "/ws/twin";

/**
 * WebSocket message types (server → client).
 */
export type ServerMessageType =
  | "SWARM_STATE"
  | "DRONE_STATE_DELTA"
  | "MISSION_STATUS"
  | "ALERT"
  | "CONNECTION_STATUS";

/**
 * WebSocket message types (client → server).
 */
export type ClientMessageType =
  | "SUBSCRIBE"
  | "UNSUBSCRIBE"
  | "SET_UPDATE_RATE";

export interface ServerMessage {
  readonly type: ServerMessageType;
  readonly payload: unknown;
  readonly timestamp_ms: number;
}

export interface ClientMessage {
  readonly type: ClientMessageType;
  readonly payload: unknown;
}
