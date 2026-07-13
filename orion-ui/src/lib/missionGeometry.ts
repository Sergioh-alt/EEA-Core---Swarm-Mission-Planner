/**
 * Mission geometry loader.
 *
 * In LIVE mode the field polygon + planned routes come from the Digital Twin
 * API (`/api/mission/geometry`). Without a backend the development-only mock
 * geometry is used so a fresh clone still renders a map. The UI never invents
 * or computes route/zone geometry.
 */

import type { MissionGeometry } from "@/contracts/types";
import { isLiveMode } from "@/lib/config";
import { getTwinRESTClient } from "@/lib/restClient";
import {
  getFieldPolygon,
  getPlannedRoutes,
  getFieldCenter,
} from "@/lib/mockDataProvider";

export function defaultGeometry(): MissionGeometry {
  const routes = getPlannedRoutes();
  const planned_routes: Record<string, { lat: number; lng: number }[]> = {};
  for (const [id, pts] of Object.entries(routes)) {
    planned_routes[id] = pts;
  }
  return {
    field_center: getFieldCenter(),
    field_polygon: getFieldPolygon(),
    planned_routes,
  };
}

export async function loadMissionGeometry(): Promise<MissionGeometry> {
  if (isLiveMode()) {
    try {
      return await getTwinRESTClient().getMissionGeometry();
    } catch {
      return defaultGeometry();
    }
  }
  return defaultGeometry();
}
