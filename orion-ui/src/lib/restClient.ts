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

export class TwinRESTClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl ?? restBaseUrl() ?? this.inferBaseUrl();
  }

  private inferBaseUrl(): string {
    if (typeof window === "undefined") return "http://localhost:8000";
    return window.location.origin;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new TwinRESTClientError(
        `Request failed: ${response.statusText}`,
        response.status,
        endpoint
      );
    }

    return response.json() as Promise<T>;
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
