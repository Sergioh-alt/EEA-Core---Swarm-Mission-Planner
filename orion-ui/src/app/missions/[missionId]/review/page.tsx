"use client";

/**
 * Mission Review & Deployment workspace (Phase 10D.6).
 *
 * The operational gateway between planning and execution. It summarizes the
 * completed Mission Package, collects operator confirmations, offers a
 * read-only execution preview and authorizes deployment.
 *
 * Boundaries: every operational value shown is read from the Mission Package
 * produced by the Planning Core — this screen plans, optimizes, allocates and
 * schedules nothing. Deployment has exactly one effect: submitting the
 * approved, immutable package to the Digital Twin deployment endpoint.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Check, Lock, Rocket } from "lucide-react";
import { PageShell } from "@/components/common/PageShell";
import { DeploymentStatus } from "@/components/review/DeploymentStatus";
import { MissionPreview } from "@/components/review/MissionPreview";
import { getPipelineClient } from "@/lib/pipelineClient";
import { isLiveMode } from "@/lib/config";
import {
  DEPLOYMENT_STATE_LABELS,
  type DeploymentRecord,
  type MissionReview,
} from "@/contracts/mission";
import {
  environmentOf,
  executionOf,
  geometryOf,
  recommendationOf,
  resourcesOf,
  risksOf,
  timelineOf,
} from "@/lib/missionPackageView";

/** Delay before the automatic Mission Control handoff, so the operator sees it. */
const HANDOFF_DELAY_MS = 1500;

export default function MissionReviewPage() {
  const params = useParams();
  const router = useRouter();
  const missionId = String(params.missionId);
  const live = isLiveMode();
  const client = getPipelineClient();

  const [review, setReview] = useState<MissionReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [handoff, setHandoff] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await client.getReview(missionId);
        if (active) setReview(data);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Load failed");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [client, missionId]);

  const patchDeployment = useCallback((deployment: DeploymentRecord) => {
    setReview((prev) => (prev ? { ...prev, deployment } : prev));
  }, []);

  const toggleItem = useCallback(
    async (itemId: string, confirmed: boolean) => {
      setBusy(true);
      setError(null);
      try {
        patchDeployment(
          await client.updateChecklist(missionId, { [itemId]: confirmed })
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : "Checklist update failed");
      } finally {
        setBusy(false);
      }
    },
    [client, missionId, patchDeployment]
  );

  const handleDeploy = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await client.deployMission(missionId);
      patchDeployment(result.deployment);
      setHandoff(true);
      // Mission Control handoff: the Twin already holds the deployed package.
      setTimeout(() => router.push("/control"), HANDOFF_DELAY_MS);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Deployment failed");
    } finally {
      setBusy(false);
    }
  }, [client, missionId, patchDeployment, router]);

  const pkg = review?.package ?? null;
  const view = useMemo(() => {
    if (!pkg) return null;
    return {
      recommendation: recommendationOf(pkg),
      resources: resourcesOf(pkg),
      risks: risksOf(pkg),
      timeline: timelineOf(pkg),
      geometry: geometryOf(pkg),
      environment: environmentOf(pkg),
      execution: executionOf(pkg),
    };
  }, [pkg]);

  if (loading) {
    return (
      <PageShell title="Mission Review" description="Loading…">
        <p className="text-xs text-neutral-500">Loading…</p>
      </PageShell>
    );
  }

  if (!review || !pkg || !view) {
    return (
      <PageShell title="Mission Review" description="Mission not found">
        <div className="rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error ?? "Mission not found"}
        </div>
        <Link
          href="/missions"
          className="mt-4 inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
        >
          <ArrowLeft className="h-3 w-3" /> Back to missions
        </Link>
      </PageShell>
    );
  }

  const { mission, deployment } = review;
  const zones = mission.field.zones ?? [];
  const selectedZones = zones.filter((z) => z.kind !== "exclusion" && z.enabled !== false);
  const excludedZones = zones.filter((z) => z.kind === "exclusion" || z.enabled === false);
  const deployable =
    live &&
    review.deployment_available &&
    deployment.checklist_complete &&
    !deployment.locked;

  return (
    <PageShell
      title={`Mission Review — ${mission.name}`}
      description="Verify the Mission Package, confirm operational readiness and authorize deployment to the Digital Twin"
      actions={
        <div className="flex items-center gap-2">
          <Link
            href={`/missions/${missionId}`}
            className="inline-flex items-center gap-1 rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800"
          >
            <ArrowLeft className="h-3 w-3" /> Designer
          </Link>
          <button
            type="button"
            onClick={() => void handleDeploy()}
            disabled={!deployable || busy}
            data-testid="deploy-button"
            className="inline-flex items-center gap-1.5 rounded-md border border-blue-700 bg-blue-950 px-3 py-1.5 text-xs text-blue-200 hover:bg-blue-900 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Rocket className="h-3 w-3" />
            {deployment.locked ? "Deployed" : busy ? "Deploying…" : "Deploy mission"}
          </button>
        </div>
      }
    >
      {!live && (
        <Banner tone="amber">
          Live API mode is disabled — deployment is unavailable. Set
          NEXT_PUBLIC_TWIN_API_URL to enable it.
        </Banner>
      )}
      {live && !review.deployment_available && (
        <Banner tone="amber">
          No Digital Twin deployment interface is attached to this backend.
        </Banner>
      )}
      {error && <Banner tone="red">{error}</Banner>}
      {handoff && (
        <Banner tone="blue">
          Mission Package deployed to the Digital Twin — opening Mission
          Control…
        </Banner>
      )}
      {deployment.locked && !handoff && (
        <Banner tone="blue">
          <span className="inline-flex items-center gap-1.5">
            <Lock className="h-3 w-3" />
            This Mission Package is deployed and locked. To change anything,
            create a new Mission Definition.
          </span>
        </Banner>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Section title="Mission Summary">
            <p className="text-[11px] text-neutral-500">
              Every value below is read from the Mission Package produced by the
              Planning Core. This screen computes nothing.
            </p>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1 md:grid-cols-3">
              <Row label="Mission" value={mission.name} />
              <Row label="Field" value={mission.field.name} />
              <Row
                label="Area"
                value={
                  view.geometry.areaHa != null
                    ? `${view.geometry.areaHa.toFixed(2)} ha`
                    : "—"
                }
              />
              <Row
                label="Operation type"
                value={view.execution.operationType ?? mission.operation.operation_type}
              />
              <Row label="Drone count" value={String(view.execution.numDrones ?? mission.fleet.length)} />
              <Row label="Route count" value={String(pkg.routes.length)} />
              <Row
                label="Estimated duration"
                value={
                  view.resources.durationFormatted ??
                  view.recommendation.estimatedDuration ??
                  "—"
                }
              />
              <Row
                label="Estimated coverage"
                value={
                  view.recommendation.coveragePct != null
                    ? `${view.recommendation.coveragePct.toFixed(1)} %`
                    : "—"
                }
              />
              <Row
                label="Estimated liquid usage"
                value={
                  view.resources.totalLiquidL != null
                    ? `${view.resources.totalLiquidL.toFixed(1)} L`
                    : "—"
                }
              />
              <Row
                label="Battery cycles"
                value={String(view.resources.totalBatteryCycles ?? "—")}
              />
              <Row label="Refills" value={String(view.resources.totalRefills ?? "—")} />
              <Row label="Bottleneck" value={view.resources.bottleneck ?? "—"} />
              <Row
                label="Confidence"
                value={
                  view.recommendation.confidencePct != null
                    ? `${view.recommendation.confidencePct.toFixed(0)} %`
                    : "—"
                }
              />
              <Row label="Go / No-Go" value={view.recommendation.goNoGo ?? "—"} />
              <Row
                label="Risk assessment"
                value={
                  view.risks.overallRisk
                    ? `${view.risks.overallRisk}${
                        view.risks.overallScore != null
                          ? ` (${view.risks.overallScore.toFixed(0)})`
                          : ""
                      }`
                    : "—"
                }
              />
              <Row label="Flight conditions" value={view.environment.flightConditions ?? "—"} />
              <Row label="Weather status" value={view.environment.weatherStatus ?? "—"} />
              <Row
                label="Flight altitude"
                value={
                  view.execution.flightAltitudeM != null
                    ? `${view.execution.flightAltitudeM} m`
                    : "—"
                }
              />
            </dl>
          </Section>

          <Section title="Zones">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <ListLabel>Selected zones ({selectedZones.length})</ListLabel>
                <ZoneList
                  zones={selectedZones.map((z) => `${z.label} · ${z.kind}`)}
                  empty="Entire field"
                />
              </div>
              <div>
                <ListLabel>Excluded zones ({excludedZones.length})</ListLabel>
                <ZoneList
                  zones={excludedZones.map((z) => `${z.label} · ${z.kind}`)}
                  empty="None"
                />
              </div>
            </div>
          </Section>

          <Section title="Products">
            {mission.products.length === 0 ? (
              <p className="text-[11px] text-neutral-500">No products configured.</p>
            ) : (
              <ul className="space-y-1 text-[11px] text-neutral-300">
                {mission.products.map((p) => (
                  <li key={p.product_id}>
                    {p.name}
                    {p.rate_l_per_ha != null && ` · ${p.rate_l_per_ha} L/ha`}
                    {p.tank && ` · ${p.tank}`}
                    {p.concentration_pct != null && ` · ${p.concentration_pct}%`}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Fleet & estimated resource consumption">
            <div className="overflow-x-auto rounded-md border border-neutral-800">
              <table className="w-full text-left text-[11px]">
                <thead className="bg-neutral-900 text-neutral-400">
                  <tr>
                    <th className="px-2 py-1 font-normal">Drone</th>
                    <th className="px-2 py-1 font-normal">Model</th>
                    <th className="px-2 py-1 font-normal">Battery use</th>
                    <th className="px-2 py-1 font-normal">Liquid</th>
                    <th className="px-2 py-1 font-normal">Refills</th>
                    <th className="px-2 py-1 font-normal">Flight time</th>
                    <th className="px-2 py-1 font-normal">Total time</th>
                  </tr>
                </thead>
                <tbody className="text-neutral-300">
                  {view.resources.drones.map((d, i) => {
                    const item = mission.fleet.find((f) => f.drone_id === d.droneId);
                    return (
                      <tr key={`${d.droneId}-${i}`} className="border-t border-neutral-800">
                        <td className="px-2 py-1">D{d.droneId ?? "—"}</td>
                        <td className="px-2 py-1">{item?.model ?? "—"}</td>
                        <td className="px-2 py-1">
                          {d.batteryConsumptionPct != null
                            ? `${d.batteryConsumptionPct.toFixed(1)} %`
                            : "—"}
                        </td>
                        <td className="px-2 py-1">
                          {d.liquidNeededL != null ? `${d.liquidNeededL.toFixed(1)} L` : "—"}
                        </td>
                        <td className="px-2 py-1">{d.liquidRefills ?? "—"}</td>
                        <td className="px-2 py-1">
                          {d.flightTimeMin != null ? `${d.flightTimeMin.toFixed(1)} min` : "—"}
                        </td>
                        <td className="px-2 py-1">
                          {d.totalTimeMin != null ? `${d.totalTimeMin.toFixed(1)} min` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Section>

          <Section title="Timeline summary">
            <Row label="Duration" value={view.timeline.durationFormatted ?? "—"} />
            <Row label="Events" value={String(view.timeline.totalEvents ?? "—")} />
            {view.timeline.summary && (
              <p className="mt-1 text-[11px] text-neutral-400">{view.timeline.summary}</p>
            )}
          </Section>

          <Section title="Planning recommendations">
            {view.recommendation.summary && (
              <p className="text-[11px] text-neutral-300">{view.recommendation.summary}</p>
            )}
            <Notes title="Operational notes" items={view.recommendation.operationalNotes} />
            <Notes
              title="Optimization suggestions"
              items={view.recommendation.optimizationSuggestions}
            />
            {view.risks.rows.length > 0 && (
              <div className="space-y-1">
                <ListLabel>Risks</ListLabel>
                <ul className="space-y-1 text-[11px] text-neutral-400">
                  {view.risks.rows.map((r, i) => (
                    <li key={i}>
                      <span className="text-neutral-300">{r.category}</span> ·{" "}
                      {r.level} — {r.description}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Section>

          <Section title="Validation">
            <Row label="Definition valid" value={pkg.validation.valid ? "yes" : "no"} />
            {pkg.validation.warnings.length > 0 && (
              <ul className="space-y-1 text-[10px] text-amber-500">
                {pkg.validation.warnings.map((w, i) => (
                  <li key={i}>• {w}</li>
                ))}
              </ul>
            )}
            {pkg.validation.errors.length > 0 && (
              <ul className="space-y-1 text-[10px] text-red-500">
                {pkg.validation.errors.map((e, i) => (
                  <li key={i}>• {e}</li>
                ))}
              </ul>
            )}
            {pkg.validation.warnings.length === 0 &&
              pkg.validation.errors.length === 0 && (
                <p className="text-[11px] text-neutral-500">No warnings.</p>
              )}
          </Section>

          <Section title="Execution preview (optional)">
            <button
              type="button"
              onClick={() => setShowPreview((v) => !v)}
              data-testid="preview-toggle"
              className="rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800"
            >
              {showPreview ? "Hide preview" : "Show preview"}
            </button>
            {showPreview && (
              <div className="mt-3">
                <MissionPreview pkg={pkg} />
              </div>
            )}
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="Operational Checklist">
            <p className="text-[11px] text-neutral-500">
              Operator confirmation only. Deployment stays disabled until every
              item is confirmed; nothing here changes the Mission Package.
            </p>
            <ul className="space-y-1">
              {deployment.checklist.map((item) => (
                <li key={item.item_id}>
                  <label
                    className={`flex items-center gap-2 rounded-md px-2 py-1 text-[11px] ${
                      deployment.locked
                        ? "text-neutral-500"
                        : "cursor-pointer text-neutral-300 hover:bg-neutral-900"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={item.confirmed}
                      disabled={deployment.locked || busy || !live}
                      onChange={(e) =>
                        void toggleItem(item.item_id, e.target.checked)
                      }
                      data-testid={`checklist-${item.item_id}`}
                      className="h-3 w-3 accent-blue-600"
                    />
                    {item.label}
                    {item.confirmed && (
                      <Check className="ml-auto h-3 w-3 text-emerald-500" />
                    )}
                  </label>
                </li>
              ))}
            </ul>
            <p
              data-testid="checklist-state"
              className={`text-[11px] ${
                deployment.checklist_complete
                  ? "text-emerald-500"
                  : "text-amber-500"
              }`}
            >
              {deployment.checklist_complete
                ? "Checklist complete — deployment authorized"
                : "Checklist incomplete — deployment disabled"}
            </p>
          </Section>

          <Section title="Deployment Status">
            <Row
              label="Current state"
              value={DEPLOYMENT_STATE_LABELS[deployment.state]}
            />
            {deployment.deployment_id && (
              <Row label="Deployment id" value={deployment.deployment_id} />
            )}
            {deployment.deployed_ms && (
              <Row
                label="Deployed at"
                value={new Date(deployment.deployed_ms).toLocaleString()}
              />
            )}
            <div className="pt-2">
              <DeploymentStatus state={deployment.state} />
            </div>
          </Section>

          {deployment.locked && (
            <Section title="Mission Control">
              <p className="text-[11px] text-neutral-500">
                The Digital Twin holds the deployed Mission Package. Execution
                is started by the operator from Mission Control.
              </p>
              <Link
                href="/control"
                className="inline-flex items-center gap-1 rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-blue-400 hover:bg-neutral-800"
              >
                Open Mission Control →
              </Link>
            </Section>
          )}
        </div>
      </div>
    </PageShell>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2 rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
      <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-400">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-neutral-800/60 py-0.5">
      <dt className="text-[11px] text-neutral-500">{label}</dt>
      <dd className="text-[11px] text-neutral-200">{value}</dd>
    </div>
  );
}

function ListLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] uppercase tracking-wide text-neutral-500">
      {children}
    </div>
  );
}

function ZoneList({
  zones,
  empty,
}: {
  zones: readonly string[];
  empty: string;
}) {
  if (zones.length === 0) {
    return <p className="text-[11px] text-neutral-500">{empty}</p>;
  }
  return (
    <ul className="space-y-0.5 text-[11px] text-neutral-300">
      {zones.map((z, i) => (
        <li key={i}>{z}</li>
      ))}
    </ul>
  );
}

function Notes({
  title,
  items,
}: {
  title: string;
  items: readonly string[];
}) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-1">
      <ListLabel>{title}</ListLabel>
      <ul className="space-y-0.5 text-[11px] text-neutral-400">
        {items.map((n, i) => (
          <li key={i}>• {n}</li>
        ))}
      </ul>
    </div>
  );
}

function Banner({
  tone,
  children,
}: {
  tone: "amber" | "red" | "blue";
  children: React.ReactNode;
}) {
  const styles = {
    amber: "border-amber-900/50 bg-amber-950/20 text-amber-400",
    red: "border-red-900/50 bg-red-950/30 text-red-400",
    blue: "border-blue-900/50 bg-blue-950/30 text-blue-300",
  } as const;
  return (
    <div className={`mb-4 rounded-md border px-3 py-2 text-xs ${styles[tone]}`}>
      {children}
    </div>
  );
}
