"use client";

/**
 * Saved mission detail (Phase 10D.7).
 *
 * Shows the stored Mission Definition and the Mission Package the Planning
 * Core produced for it, and offers the two execution paths the operator may
 * choose: execute now (hand the package to the Digital Twin) or schedule it.
 * Nothing on this screen plans, optimizes, allocates or recomputes a value.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CalendarClock, Copy, Play, RefreshCw } from "lucide-react";
import { PageShell } from "@/components/common/PageShell";
import { ScheduleForm } from "@/components/library/ScheduleForm";
import { getPipelineClient } from "@/lib/pipelineClient";
import type { LibraryEntry, ScheduleInput } from "@/contracts/mission";
import {
  environmentOf,
  geometryOf,
  recommendationOf,
  resourcesOf,
  risksOf,
  routeSummariesOf,
  timelineOf,
} from "@/lib/missionPackageView";

/** Delay before the automatic Mission Control handoff, so the operator sees it. */
const HANDOFF_DELAY_MS = 1500;

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1">
      <span className="text-[11px] text-neutral-500">{label}</span>
      <span className="text-xs text-neutral-200">{value}</span>
    </div>
  );
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
      <h2 className="mb-2 text-sm font-medium text-neutral-300">{title}</h2>
      {children}
    </section>
  );
}

export default function LibraryEntryPage() {
  const params = useParams();
  const router = useRouter();
  const entryId = String(params.entryId);
  const client = getPipelineClient();

  const [entry, setEntry] = useState<LibraryEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [handoff, setHandoff] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEntry(await client.getLibraryEntry(entryId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the mission");
    } finally {
      setLoading(false);
    }
  }, [client, entryId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleExecute = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await client.executeLibraryEntry(entryId, true);
      setNotice(
        `Mission Package handed to the Digital Twin — execution ${result.execution.execution_id}`
      );
      setHandoff(true);
      setTimeout(() => router.push("/control"), HANDOFF_DELAY_MS);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution failed");
      setBusy(false);
    }
  }, [client, entryId, router]);

  const handleDuplicate = useCallback(async () => {
    if (!entry) return;
    setBusy(true);
    setError(null);
    try {
      const result = await client.duplicateLibraryEntry(
        entryId,
        `${entry.name} (copy)`
      );
      router.push(`/missions/${result.mission.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to duplicate mission");
      setBusy(false);
    }
  }, [client, entry, entryId, router]);

  const handleResync = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await client.resyncLibraryEntry(entryId);
      setEntry(updated);
      setNotice("Planning Core re-run — the saved package now matches the definition");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to re-run the Planning Core");
    } finally {
      setBusy(false);
    }
  }, [client, entryId]);

  const handleSchedule = useCallback(
    async (input: ScheduleInput) => {
      setBusy(true);
      setError(null);
      try {
        await client.createSchedule(input);
        setScheduling(false);
        setNotice("Schedule created — the operator's times are stored as entered");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create the schedule");
      } finally {
        setBusy(false);
      }
    },
    [client]
  );

  if (loading) {
    return (
      <PageShell title="Saved mission" description="Loading…">
        <p className="text-xs text-neutral-500">Loading saved mission…</p>
      </PageShell>
    );
  }

  if (!entry) {
    return (
      <PageShell title="Saved mission" description="Not found">
        <p className="text-xs text-red-400">{error ?? "Saved mission not found"}</p>
        <Link href="/library" className="mt-3 inline-block text-xs text-blue-400">
          Back to the Mission Library
        </Link>
      </PageShell>
    );
  }

  const pkg = entry.package;
  const definition = entry.definition;
  const recommendation = pkg ? recommendationOf(pkg) : null;
  const resources = pkg ? resourcesOf(pkg) : null;
  const risks = pkg ? risksOf(pkg) : null;
  const timeline = pkg ? timelineOf(pkg) : null;
  const geometry = pkg ? geometryOf(pkg) : null;
  const environment = pkg ? environmentOf(pkg) : null;
  const routes = pkg ? routeSummariesOf(pkg) : [];
  // Non-blocking Planning Core advisories, shown here as they already are on
  // the execution-history record — same source, same wording.
  const packageWarnings = (
    (pkg?.validation as { warnings?: readonly unknown[] } | undefined)
      ?.warnings ?? []
  ).filter((w): w is string => typeof w === "string");

  return (
    <PageShell
      title={entry.name}
      description={entry.description || "Saved reusable mission"}
      actions={
        <div className="flex items-center gap-2">
          <Link
            href="/library"
            className="flex items-center gap-1 rounded-md border border-neutral-700 px-2.5 py-1.5 text-[11px] text-neutral-300 transition-colors hover:bg-neutral-800"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Library
          </Link>
          <button
            type="button"
            onClick={() => void handleDuplicate()}
            disabled={busy}
            className="flex items-center gap-1 rounded-md border border-neutral-700 px-2.5 py-1.5 text-[11px] text-neutral-300 transition-colors hover:bg-neutral-800 disabled:opacity-50"
          >
            <Copy className="h-3.5 w-3.5" /> Use as template
          </button>
          <button
            type="button"
            onClick={() => setScheduling((v) => !v)}
            disabled={busy}
            className="flex items-center gap-1 rounded-md border border-neutral-700 px-2.5 py-1.5 text-[11px] text-neutral-300 transition-colors hover:bg-neutral-800 disabled:opacity-50"
          >
            <CalendarClock className="h-3.5 w-3.5" /> Schedule
          </button>
          <button
            type="button"
            onClick={() => void handleExecute()}
            disabled={busy || !pkg}
            className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5" /> Execute now
          </button>
        </div>
      }
    >
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-400"
        >
          {error}
        </div>
      )}
      {notice && !error && (
        <div className="mb-4 rounded-md border border-emerald-900/50 bg-emerald-950/30 px-3 py-2 text-xs text-emerald-400">
          {notice}
          {handoff && " — opening Mission Control…"}
        </div>
      )}
      {entry.package_stale && (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-md border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-400">
          <span>
            The source Mission Definition changed after this package was
            generated. Executions keep running the reviewed package until the
            Planning Core is re-run explicitly.
          </span>
          <button
            type="button"
            onClick={() => void handleResync()}
            disabled={busy}
            className="flex shrink-0 items-center gap-1 rounded-md border border-amber-800 px-2 py-1 text-[11px] text-amber-300 hover:bg-amber-950/50 disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Re-run Planning Core
          </button>
        </div>
      )}

      {scheduling && (
        <div className="mb-6">
          <ScheduleForm
            entryId={entry.entry_id}
            busy={busy}
            onSubmit={handleSchedule}
            onCancel={() => setScheduling(false)}
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel title="Mission Definition">
          <Row label="Field" value={entry.summary.field_name || "—"} />
          <Row label="Crop" value={entry.summary.crop_type || "—"} />
          <Row label="Location" value={entry.summary.location || "—"} />
          <Row label="Operation" value={entry.summary.operation_type || "—"} />
          <Row label="Priority" value={entry.summary.priority} />
          <Row label="Zones selected" value={String(entry.summary.zone_count)} />
          <Row
            label="Products"
            value={entry.summary.products.join(", ") || "—"}
          />
          <Row label="Fleet" value={`${entry.summary.fleet_count} drones`} />
          <Row label="Definition version" value={`v${entry.definition_version}`} />
        </Panel>

        <Panel title="Operational parameters">
          <Row
            label="Altitude"
            value={
              definition.operation.flight_altitude_m != null
                ? `${definition.operation.flight_altitude_m} m`
                : "—"
            }
          />
          <Row
            label="Speed"
            value={
              definition.operation.nominal_speed_ms != null
                ? `${definition.operation.nominal_speed_ms} m/s`
                : "—"
            }
          />
          <Row
            label="Overlap"
            value={
              definition.operation.overlap_pct != null
                ? `${definition.operation.overlap_pct} %`
                : "—"
            }
          />
          <Row
            label="Safety margin"
            value={
              definition.operation.safety_margin_m != null
                ? `${definition.operation.safety_margin_m} m`
                : "—"
            }
          />
          <Row
            label="Coverage direction"
            value={definition.operation.coverage_direction ?? "—"}
          />
          <Row
            label="Route preference"
            value={definition.operation.route_preference ?? "—"}
          />
        </Panel>

        <Panel title="Execution readiness">
          <Row label="Package" value={pkg ? "Stored" : "Not generated"} />
          <Row
            label="Package version"
            value={
              entry.package_definition_version !== null
                ? `definition v${entry.package_definition_version}`
                : "—"
            }
          />
          <Row label="Go / No-Go" value={recommendation?.goNoGo ?? "—"} />
          <Row
            label="Mission feasible"
            value={
              recommendation?.feasible === null ||
              recommendation?.feasible === undefined
                ? "—"
                : recommendation.feasible
                  ? "yes"
                  : "no"
            }
          />
          <Row
            label="Confidence"
            value={
              recommendation?.confidencePct != null
                ? `${recommendation.confidencePct.toFixed(0)} %`
                : "—"
            }
          />
          <Row
            label="Definition valid"
            value={
              pkg
                ? (pkg.validation as { valid?: boolean })?.valid === false
                  ? "no"
                  : "yes"
                : "—"
            }
          />
          {packageWarnings.map((warning) => (
            <p key={warning} className="mt-1 text-[11px] text-amber-400">
              {warning}
            </p>
          ))}
        </Panel>

        <Panel title="Planning Core result">
          <Row
            label="Area"
            value={
              geometry?.areaHa != null ? `${geometry.areaHa.toFixed(3)} ha` : "—"
            }
          />
          <Row label="Routes" value={String(routes.length)} />
          <Row
            label="Coverage"
            value={
              recommendation?.coveragePct != null
                ? `${recommendation.coveragePct.toFixed(1)} %`
                : "—"
            }
          />
          <Row
            label="Estimated duration"
            value={resources?.durationFormatted ?? "—"}
          />
          <Row
            label="Timeline"
            value={timeline?.durationFormatted ?? "—"}
          />
          <Row
            label="Flight conditions"
            value={environment?.flightConditions ?? "—"}
          />
        </Panel>

        <Panel title="Resources">
          <Row
            label="Total liquid"
            value={
              resources?.totalLiquidL != null
                ? `${resources.totalLiquidL.toFixed(1)} L`
                : "—"
            }
          />
          <Row
            label="Refills"
            value={resources?.totalRefills != null ? String(resources.totalRefills) : "—"}
          />
          <Row
            label="Battery cycles"
            value={
              resources?.totalBatteryCycles != null
                ? String(resources.totalBatteryCycles)
                : "—"
            }
          />
          <Row label="Bottleneck" value={resources?.bottleneck ?? "—"} />
        </Panel>

        <Panel title="Risk assessment">
          <Row label="Overall risk" value={risks?.overallRisk ?? "—"} />
          <Row
            label="Risk score"
            value={risks?.overallScore != null ? risks.overallScore.toFixed(2) : "—"}
          />
          <Row
            label="Mission viable"
            value={
              risks?.missionViable === null || risks?.missionViable === undefined
                ? "—"
                : risks.missionViable
                  ? "yes"
                  : "no"
            }
          />
          {risks?.criticalRisks.length ? (
            <ul className="mt-2 space-y-1">
              {risks.criticalRisks.map((risk) => (
                <li key={risk} className="text-[11px] text-amber-400">
                  {risk}
                </li>
              ))}
            </ul>
          ) : null}
        </Panel>
      </div>

      {routes.length > 0 && (
        <div className="mt-4 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="mb-2 text-sm font-medium text-neutral-300">Routes</h2>
          <table className="w-full text-left text-[11px]">
            <thead className="text-neutral-500">
              <tr>
                <th className="py-1 font-normal">Drone</th>
                <th className="py-1 font-normal">Passes</th>
                <th className="py-1 font-normal">Distance</th>
                <th className="py-1 font-normal">Estimated time</th>
              </tr>
            </thead>
            <tbody className="text-neutral-300">
              {routes.map((route) => (
                <tr
                  key={`${route.droneId}-${route.sectorId}`}
                  className="border-t border-neutral-800"
                >
                  <td className="py-1">{route.droneId ?? "—"}</td>
                  <td className="py-1">{route.numPasses ?? "—"}</td>
                  <td className="py-1">
                    {route.totalDistanceM != null
                      ? `${route.totalDistanceM.toFixed(0)} m`
                      : "—"}
                  </td>
                  <td className="py-1">
                    {route.estimatedTimeMin != null
                      ? `${route.estimatedTimeMin.toFixed(1)} min`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
