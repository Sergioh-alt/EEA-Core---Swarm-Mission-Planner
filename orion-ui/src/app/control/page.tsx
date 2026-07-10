"use client";

import { MapView } from "@/components/mission-control/MapView";
import { FleetPanel } from "@/components/mission-control/FleetPanel";
import { TelemetryPanel } from "@/components/mission-control/TelemetryPanel";
import { MissionStatusPanel } from "@/components/mission-control/MissionStatusPanel";
import { AlertFeed } from "@/components/mission-control/AlertFeed";
import { IntentBar } from "@/components/mission-control/IntentBar";

/**
 * Phase 10C.3 — Mission Control Dashboard
 *
 * Primary operational view for the ORION GCS.
 * Layout: Fleet panel (left) | Map (center) | Telemetry (right)
 * Bottom: Mission Status + Alert Feed + Intent Bar
 *
 * Data flows:
 *   Digital Twin → WebSocket → Stores → Components (read-only)
 *   Operator → Intent Bar → POST /api/intents → Backend → Hive
 */
export default function MissionControlPage() {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Main content: 3-column layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Fleet Panel */}
        <div className="w-56 shrink-0">
          <FleetPanel />
        </div>

        {/* Center: Map + bottom panels */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Map */}
          <div className="flex-1 min-h-0 p-2">
            <MapView />
          </div>

          {/* Bottom panels row */}
          <div className="h-[200px] shrink-0 flex gap-2 px-2 pb-2">
            <div className="flex-1 min-w-0">
              <MissionStatusPanel />
            </div>
            <div className="flex-1 min-w-0">
              <AlertFeed />
            </div>
          </div>

          {/* Intent Bar */}
          <IntentBar />
        </div>

        {/* Right: Telemetry Panel */}
        <div className="w-64 shrink-0">
          <TelemetryPanel />
        </div>
      </div>
    </div>
  );
}
