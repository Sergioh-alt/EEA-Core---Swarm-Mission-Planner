/**
 * REST client for the Mission Definition Pipeline (Phase 10D.2+).
 *
 * Design-time only: field acquisition/preparation, mission definitions and
 * planning requests. These endpoints are served by the same backend as the
 * Digital Twin API but represent the *definition* side of the contract, never
 * runtime state. The UI collects and submits structured data — it never plans.
 */

import {
  PIPELINE_ENDPOINTS,
  type FieldDefinition,
  type FieldImage,
  type FieldImageSource,
  type FleetInventory,
  type MissionDefinition,
  type MissionPackage,
} from "@/contracts/mission";
import { restBaseUrl } from "@/lib/config";

class PipelineClientError extends Error {
  constructor(
    message: string,
    public status: number,
    public endpoint: string
  ) {
    super(message);
    this.name = "PipelineClientError";
  }
}

const REQUEST_TIMEOUT_MS = 15000;

export class PipelineClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl ?? restBaseUrl() ?? this.inferBaseUrl();
  }

  private inferBaseUrl(): string {
    if (typeof window === "undefined") return "http://localhost:8000";
    return window.location.origin;
  }

  /** Resolve a backend-relative image url to an absolute, loadable url. */
  resolveUrl(path: string): string {
    if (!path) return path;
    if (/^https?:\/\//.test(path)) return path;
    return `${this.baseUrl}${path}`;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          ...options?.headers,
        },
      });
      const text = await response.text();
      if (!response.ok) {
        let detail = response.statusText;
        try {
          const parsed = JSON.parse(text) as { detail?: string };
          if (parsed.detail) detail = parsed.detail;
        } catch {
          /* keep statusText */
        }
        throw new PipelineClientError(detail, response.status, endpoint);
      }
      return (text ? JSON.parse(text) : undefined) as T;
    } catch (err) {
      if (err instanceof PipelineClientError) throw err;
      throw new PipelineClientError(
        err instanceof Error ? err.message : "Network request failed",
        0,
        endpoint
      );
    } finally {
      clearTimeout(timer);
    }
  }

  // -- fleet inventory -------------------------------------------------------

  async getFleetInventory(): Promise<FleetInventory> {
    return this.request<FleetInventory>(PIPELINE_ENDPOINTS.FLEET_INVENTORY);
  }

  // -- fields ----------------------------------------------------------------

  async listFields(): Promise<FieldDefinition[]> {
    const data = await this.request<{ fields: FieldDefinition[] }>(
      PIPELINE_ENDPOINTS.FIELDS
    );
    return data.fields ?? [];
  }

  async getField(fieldId: string): Promise<FieldDefinition> {
    return this.request<FieldDefinition>(PIPELINE_ENDPOINTS.FIELD(fieldId));
  }

  async createField(field: Partial<FieldDefinition>): Promise<FieldDefinition> {
    return this.request<FieldDefinition>(PIPELINE_ENDPOINTS.FIELDS, {
      method: "POST",
      body: JSON.stringify(field),
    });
  }

  async updateField(
    fieldId: string,
    field: Partial<FieldDefinition>
  ): Promise<FieldDefinition> {
    return this.request<FieldDefinition>(PIPELINE_ENDPOINTS.FIELD(fieldId), {
      method: "PUT",
      body: JSON.stringify(field),
    });
  }

  async deleteField(fieldId: string): Promise<void> {
    await this.request<{ deleted: string }>(PIPELINE_ENDPOINTS.FIELD(fieldId), {
      method: "DELETE",
    });
  }

  // -- field images ----------------------------------------------------------

  /** Upload image bytes as the raw request body (no multipart dependency). */
  async uploadFieldImage(
    fieldId: string,
    file: File,
    source: FieldImageSource
  ): Promise<FieldImage> {
    const params = new URLSearchParams({
      filename: file.name,
      source,
    });
    const endpoint = `${PIPELINE_ENDPOINTS.FIELD_IMAGES(fieldId)}?${params}`;
    const buffer = await file.arrayBuffer();
    return this.request<FieldImage>(endpoint, {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: buffer,
    });
  }

  // -- mission definitions ---------------------------------------------------

  async listMissions(): Promise<MissionDefinition[]> {
    const data = await this.request<{ missions: MissionDefinition[] }>(
      PIPELINE_ENDPOINTS.MISSIONS
    );
    return data.missions ?? [];
  }

  async getMission(missionId: string): Promise<MissionDefinition> {
    return this.request<MissionDefinition>(
      PIPELINE_ENDPOINTS.MISSION(missionId)
    );
  }

  async createMission(
    mission: Partial<MissionDefinition>
  ): Promise<MissionDefinition> {
    return this.request<MissionDefinition>(PIPELINE_ENDPOINTS.MISSIONS, {
      method: "POST",
      body: JSON.stringify(mission),
    });
  }

  async updateMission(
    missionId: string,
    mission: Partial<MissionDefinition>
  ): Promise<MissionDefinition> {
    return this.request<MissionDefinition>(
      PIPELINE_ENDPOINTS.MISSION(missionId),
      {
        method: "PUT",
        body: JSON.stringify(mission),
      }
    );
  }

  async deleteMission(missionId: string): Promise<void> {
    await this.request<{ deleted: string }>(
      PIPELINE_ENDPOINTS.MISSION(missionId),
      { method: "DELETE" }
    );
  }

  // -- planning core (design-time; never mutates runtime state) --------------

  /**
   * Submit a stored mission to the Planning Core and receive a Mission Package.
   * The Planning Core (core/) performs all environment analysis, swarm
   * planning, routing, resource planning, risk analysis and timeline work.
   */
  async computePlanning(missionId: string): Promise<MissionPackage> {
    return this.request<MissionPackage>(PIPELINE_ENDPOINTS.PLANNING_COMPUTE, {
      method: "POST",
      body: JSON.stringify({ mission_id: missionId }),
    });
  }
}

let pipelineInstance: PipelineClient | null = null;

export function getPipelineClient(baseUrl?: string): PipelineClient {
  if (!pipelineInstance) {
    pipelineInstance = new PipelineClient(baseUrl);
  }
  return pipelineInstance;
}
