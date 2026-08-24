"use client";

/**
 * Deployed Mission Package strip for Mission Control (Phase 10D.6 handoff).
 *
 * Mission Control receives *only* the deployed Mission Package: this reads it
 * from the Digital Twin and shows what was handed over. It renders nothing
 * when no package has been deployed, so the existing Mission Control layout
 * and behavior are unchanged for the standing demo.
 */

import { useEffect, useState } from "react";
import { Lock } from "lucide-react";
import { getPipelineClient } from "@/lib/pipelineClient";
import type { TwinDeployment } from "@/contracts/mission";
import { executionOf, recommendationOf, resourcesOf } from "@/lib/missionPackageView";
import { useMissionStore } from "@/stores/missionStore";
import { useLiveStale } from "@/hooks/useLiveStale";

/** Runtime-state wording for the strip. The Digital Twin owns the state. */
const RUNTIME_NOTE: Record<string, string> = {
  IDLE: "Awaiting operator start — execution is controlled here.",
  RUNNING: "Executing — execution is controlled here.",
  PAUSED: "Paused by operator — execution is controlled here.",
  COMPLETED: "Execution completed.",
  ABORTED: "Execution aborted.",
};

export function DeployedMissionBar() {
  const [deployment, setDeployment] = useState<TwinDeployment | null>(null);
  const missionStatus = useMissionStore((s) => s.status);
  const stale = useLiveStale();

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getPipelineClient().getTwinDeployment();
        if (active) setDeployment(data);
      } catch {
        /* Mission Control keeps working without a deployment. */
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const pkg = deployment?.deployed ? deployment.package : null;
  if (!pkg) return null;

  const execution = executionOf(pkg);
  const resources = resourcesOf(pkg);
  const recommendation = recommendationOf(pkg);

  return (
    <div
      data-testid="deployed-mission-bar"
      className="mx-2 mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-blue-900/50 bg-blue-950/20 px-3 py-1.5 text-[11px] text-blue-200"
    >
      <span className="inline-flex items-center gap-1.5 font-medium">
        <Lock className="h-3 w-3" /> Deployed Mission Package
      </span>
      <span className="text-blue-300/70">{pkg.definition_id}</span>
      <span>{execution.operationType ?? "—"}</span>
      <span>{execution.numDrones ?? pkg.routes.length} drones</span>
      <span>{pkg.routes.length} routes</span>
      {resources.durationFormatted && <span>{resources.durationFormatted}</span>}
      {recommendation.goNoGo && <span>{recommendation.goNoGo}</span>}
      <span className={stale ? "ml-auto text-amber-400" : "ml-auto text-blue-300/60"}>
        {stale
          ? "Digital Twin unreachable — last reported state only."
          : RUNTIME_NOTE[missionStatus] ?? RUNTIME_NOTE.IDLE}
      </span>
    </div>
  );
}
