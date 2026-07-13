/**
 * Runtime integration configuration.
 *
 * When NEXT_PUBLIC_TWIN_API_URL is set (e.g. http://localhost:8000), the UI
 * runs in LIVE mode and consumes the real Digital Twin API server over REST +
 * WebSocket. When unset, the UI falls back to the development-only mock data
 * provider (see lib/mockDataProvider.ts) so a fresh clone still renders.
 *
 * The UI only ever talks to the Digital Twin API — never PX4/ROS2/MAVLink/Hive.
 */

const RAW_API_URL = (process.env.NEXT_PUBLIC_TWIN_API_URL ?? "").trim().replace(/\/$/, "");

/** True when a real Digital Twin API server is configured. */
export function isLiveMode(): boolean {
  return RAW_API_URL.length > 0;
}

/** REST base URL. Empty string means "same origin" (handled by the client). */
export function restBaseUrl(): string | undefined {
  return RAW_API_URL || undefined;
}

/** WebSocket base URL derived from the API URL (http→ws, https→wss). */
export function wsBaseUrl(): string | undefined {
  if (!RAW_API_URL) return undefined;
  return RAW_API_URL.replace(/^http/, "ws");
}
