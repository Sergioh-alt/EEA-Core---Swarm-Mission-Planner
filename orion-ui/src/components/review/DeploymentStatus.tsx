"use client";

/**
 * Deployment status visualization (Phase 10D.6).
 *
 * Shows the whole mission lifecycle. Mission Review only drives the states up
 * to `Deployed`; later states belong to Mission Control and the Digital Twin
 * and are rendered as context, never advanced from here.
 */

import {
  DEPLOYMENT_STATES,
  DEPLOYMENT_STATE_LABELS,
  RUNTIME_OWNED_STATES,
  type DeploymentState,
} from "@/contracts/mission";

export function DeploymentStatus({ state }: { state: DeploymentState }) {
  const currentIndex = DEPLOYMENT_STATES.indexOf(state);

  return (
    <div className="space-y-2">
      <ol className="space-y-1">
        {DEPLOYMENT_STATES.map((s, i) => {
          const done = i < currentIndex;
          const current = i === currentIndex;
          const runtimeOwned = RUNTIME_OWNED_STATES.includes(s);
          return (
            <li
              key={s}
              data-state={s}
              data-current={current ? "true" : "false"}
              className={`flex items-center gap-2 rounded-md px-2 py-1 text-[11px] ${
                current
                  ? "bg-blue-950/40 text-blue-300"
                  : done
                    ? "text-neutral-400"
                    : "text-neutral-600"
              }`}
            >
              <span
                className={`inline-block h-2 w-2 shrink-0 rounded-full ${
                  current
                    ? "bg-blue-400"
                    : done
                      ? "bg-neutral-500"
                      : "bg-neutral-700"
                }`}
              />
              <span>{DEPLOYMENT_STATE_LABELS[s]}</span>
              {runtimeOwned && (
                <span className="ml-auto text-[10px] text-neutral-600">
                  Mission Control
                </span>
              )}
            </li>
          );
        })}
      </ol>
      <p className="text-[10px] text-neutral-600">
        Mission Review is responsible only for the transitions up to Deployed.
        Execution stays with Mission Control and the Digital Twin.
      </p>
    </div>
  );
}
