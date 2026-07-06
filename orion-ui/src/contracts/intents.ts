/**
 * UI Intent contracts.
 *
 * Intents are the ONLY write path from UI.
 * They are submitted to the backend intent handler which routes to Hive.
 * The UI never decides — Hive accepts or rejects.
 */

export type IntentType =
  | "START_MISSION"
  | "PAUSE_MISSION"
  | "RESUME_MISSION"
  | "STOP_MISSION"
  | "START_REPLAY"
  | "STOP_REPLAY"
  | "REQUEST_SNAPSHOT";

export interface UIIntent {
  readonly intent_type: IntentType;
  readonly payload: Record<string, unknown>;
  readonly user_id: string;
  readonly timestamp_ms: number;
}

export interface IntentResponse {
  readonly accepted: boolean;
  readonly intent_type: IntentType;
  readonly message: string;
  readonly timestamp_ms: number;
}
