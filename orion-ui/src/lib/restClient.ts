/**
 * REST client for Digital Twin on-demand queries.
 *
 * All endpoints are read-only except for intent submission.
 * Only communicates with the Digital Twin API.
 */

import { API_ENDPOINTS } from "@/contracts/api";
import type {
  SwarmState,
  DroneState,
  Snapshot,
  SnapshotMetadata,
  ReplayTimeline,
  DroneReplayTimeline,
  MissionGeometry,
  MissionInfo,
  AnalyticsData,
  Alert,
} from "@/contracts/types";
import type { UIIntent, IntentResponse } from "@/contracts/intents";
import { restBaseUrl } from "@/lib/config";

class TwinRESTClientError extends Error {
  constructor(
    message: string,
    public status: number,
    public endpoint: string
  ) {
    super(message);
    this.name = "TwinRESTClientError";
  }
}

const REQUEST_TIMEOUT_MS = 10000;
const MAX_GET_RETRIES = 2;

export class TwinRESTClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl ?? restBaseUrl() ?? this.inferBaseUrl();
  }

  private inferBaseUrl(): string {
    if (typeof window === "undefined") return "http://localhost:8000";
    return window.location.origin;
  }

  private backoff(attempt: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, 250 * 2 ** attempt));
  }

  private async fetchWithTimeout(
    url: string,
    options?: RequestInit
  ): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      return await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          ...options?.headers,
        },
      });
    } finally {
      clearTimeout(timer);
    }
  }

  private async parseJson<T>(response: Response, endpoint: string): Promise<T> {
    const text = await response.text();
    if (!text) {
      return undefined as T;
    }
    try {
      return JSON.parse(text) as T;
    } catch {
      throw new TwinRESTClientError(
        "Malformed JSON response",
        response.status,
        endpoint
      );
    }
  }

  /**
   * Perform a request with a hard timeout. Idempotent GETs are retried a
   * few times on transient failures (network error, timeout, 5xx). Non-GET
   * requests (intents, replay) are never retried automatically.
   */
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const method = (options?.method ?? "GET").toUpperCase();
    const isIdempotent = method === "GET";
    const maxAttempts = isIdempotent ? MAX_GET_RETRIES + 1 : 1;

    let lastError: unknown;
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const response = await this.fetchWithTimeout(url, options);
        if (!response.ok) {
          const err = new TwinRESTClientError(
            `Request failed: ${response.statusText}`,
            response.status,
            endpoint
          );
          if (
            isIdempotent &&
            response.status >= 500 &&
            attempt < maxAttempts - 1
          ) {
            lastError = err;
            await this.backoff(attempt);
            continue;
          }
          throw err;
        }
        return await this.parseJson<T>(response, endpoint);
      } catch (err) {
        // Deterministic client errors and malformed responses are not retried.
        if (err instanceof TwinRESTClientError && err.status < 500) {
          throw err;
        }
        lastError = err;
        if (!isIdempotent || attempt >= maxAttempts - 1) {
          if (err instanceof TwinRESTClientError) throw err;
          throw new TwinRESTClientError(
            err instanceof Error ? err.message : "Network request failed",
            0,
            endpoint
          );
        }
        await this.backoff(attempt);
      }
    }
    throw lastError instanceof Error
      ? lastError
      : new TwinRESTClientError("Network request failed", 0, endpoint);
  }

  async getSwarmState(): Promise<SwarmState> {
    return this.request<SwarmState>(API_ENDPOINTS.SWARM_STATE);
  }

  async getDroneState(droneId: number): Promise<DroneState> {
    return this.request<DroneState>(API_ENDPOINTS.DRONE_STATE(droneId));
  }

  async listSnapshots(): Promise<SnapshotMetadata[]> {
    return this.request<SnapshotMetadata[]>(API_ENDPOINTS.SNAPSHOTS);
  }

  async getSnapshot(snapshotId: string): Promise<Snapshot> {
    return this.request<Snapshot>(API_ENDPOINTS.SNAPSHOT(snapshotId));
  }

  /**
   * Request a replay timeline reconstructed from stored snapshots.
   * The Digital Twin replay engine is version-range based; passing no range
   * replays the full recorded history. Read-only.
   */
  async startReplay(range?: {
    start_version?: number;
    end_version?: number;
  }): Promise<ReplayTimeline> {
    return this.request<ReplayTimeline>(API_ENDPOINTS.REPLAY, {
      method: "POST",
      body: JSON.stringify(range ?? {}),
    });
  }

  async getDroneReplay(droneId: number): Promise<DroneReplayTimeline> {
    return this.request<DroneReplayTimeline>(
      API_ENDPOINTS.DRONE_REPLAY(droneId)
    );
  }

  async submitIntent(intent: UIIntent): Promise<IntentResponse> {
    return this.request<IntentResponse>(API_ENDPOINTS.INTENTS, {
      method: "POST",
      body: JSON.stringify(intent),
    });
  }

  async healthCheck(): Promise<{ status: string }> {
    return this.request<{ status: string }>(API_ENDPOINTS.HEALTH);
  }

  async getMissionGeometry(): Promise<MissionGeometry> {
    return this.request<MissionGeometry>(API_ENDPOINTS.MISSION_GEOMETRY);
  }

  async getMissionStatus(): Promise<MissionInfo> {
    return this.request<MissionInfo>(API_ENDPOINTS.MISSION_STATUS);
  }

  async getAnalytics(): Promise<AnalyticsData> {
    return this.request<AnalyticsData>(API_ENDPOINTS.ANALYTICS);
  }

  async listAlerts(): Promise<Alert[]> {
    return this.request<Alert[]>(API_ENDPOINTS.ALERTS);
  }
}

let restInstance: TwinRESTClient | null = null;

export function getTwinRESTClient(baseUrl?: string): TwinRESTClient {
  if (!restInstance) {
    restInstance = new TwinRESTClient(baseUrl);
  }
  return restInstance;
}
