"use client";

/**
 * Scheduler (Phase 10D.7).
 *
 * Lists the operator's scheduled missions and the occurrences their own rules
 * produce. The scheduler stores intent and reports it — it never selects a
 * better time, reallocates fleet, alters a mission or resolves a conflict.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CalendarClock, Trash2 } from "lucide-react";
import { PageShell } from "@/components/common/PageShell";
import { EmptyState } from "@/components/common/EmptyState";
import { ScheduleForm } from "@/components/library/ScheduleForm";
import { getPipelineClient } from "@/lib/pipelineClient";
import {
  RECURRENCE_LABELS,
  type LibraryEntry,
  type MissionSchedule,
  type ScheduleInput,
} from "@/contracts/mission";

function formatMoment(ms: number | null): string {
  return ms === null ? "—" : new Date(ms).toLocaleString();
}

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<MissionSchedule[]>([]);
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const client = getPipelineClient();
      const [list, saved] = await Promise.all([
        client.listSchedules(),
        client.listLibrary(),
      ]);
      setSchedules(list);
      setEntries(saved.filter((entry) => entry.status === "ready"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load schedules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const nameOf = useMemo(() => {
    const names = new Map(entries.map((e) => [e.entry_id, e.name]));
    return (entryId: string) => names.get(entryId) ?? entryId;
  }, [entries]);

  const handleCreate = useCallback(
    async (input: ScheduleInput) => {
      setBusy(true);
      setError(null);
      try {
        await getPipelineClient().createSchedule(input);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create schedule");
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  const handleToggle = useCallback(
    async (schedule: MissionSchedule) => {
      setBusy(true);
      setError(null);
      try {
        await getPipelineClient().setScheduleEnabled(
          schedule.schedule_id,
          !schedule.enabled
        );
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update schedule");
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  const handleDelete = useCallback(
    async (schedule: MissionSchedule) => {
      setBusy(true);
      setError(null);
      try {
        await getPipelineClient().deleteSchedule(schedule.schedule_id);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to remove schedule");
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  return (
    <PageShell
      title="Scheduler"
      description="Scheduled executions of saved missions — chosen entirely by the operator"
      actions={
        <Link
          href="/library"
          className="rounded-md border border-neutral-700 px-2.5 py-1.5 text-[11px] text-neutral-300 transition-colors hover:bg-neutral-800"
        >
          Mission Library
        </Link>
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

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          {loading ? (
            <p className="text-xs text-neutral-500">Loading schedules…</p>
          ) : schedules.length === 0 ? (
            <EmptyState
              icon={<CalendarClock className="h-8 w-8" />}
              title="No scheduled missions"
              description="Schedule a saved mission to run it at the dates and times you choose."
            />
          ) : (
            schedules.map((schedule) => (
              <div
                key={schedule.schedule_id}
                className="rounded-lg border border-neutral-800 bg-neutral-900 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/library/${schedule.entry_id}`}
                        className="text-sm font-medium text-neutral-100 hover:text-blue-300"
                      >
                        {nameOf(schedule.entry_id)}
                      </Link>
                      <span className="rounded border border-neutral-700 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-neutral-400">
                        {RECURRENCE_LABELS[schedule.recurrence]}
                      </span>
                      <span
                        className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${
                          schedule.enabled
                            ? "border-emerald-800 text-emerald-300"
                            : "border-neutral-700 text-neutral-500"
                        }`}
                      >
                        {schedule.enabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                    {schedule.label && (
                      <p className="mt-1 text-[11px] text-neutral-400">
                        {schedule.label}
                      </p>
                    )}
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-neutral-500">
                      <span>from {schedule.start_date}</span>
                      <span>{schedule.times.join(" · ")}</span>
                      {schedule.recurrence === "custom" && (
                        <span>every {schedule.interval_days} days</span>
                      )}
                    </div>
                    <p className="mt-1 text-[11px] text-neutral-400">
                      Next occurrence: {formatMoment(schedule.next_occurrence_ms)}
                    </p>
                    {schedule.upcoming_ms.length > 1 && (
                      <p className="mt-0.5 text-[10px] text-neutral-600">
                        Then{" "}
                        {schedule.upcoming_ms
                          .slice(1)
                          .map((ms) => formatMoment(ms))
                          .join(" · ")}
                      </p>
                    )}
                    {schedule.last_result && (
                      <p className="mt-1 text-[11px] text-amber-400">
                        Last run: {schedule.last_result}
                      </p>
                    )}
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleToggle(schedule)}
                      className="rounded-md border border-neutral-700 px-2 py-1 text-[11px] text-neutral-300 transition-colors hover:bg-neutral-800 disabled:opacity-50"
                    >
                      {schedule.enabled ? "Disable" : "Enable"}
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleDelete(schedule)}
                      aria-label="Remove schedule"
                      className="rounded-md border border-neutral-700 p-2 text-neutral-500 transition-colors hover:border-red-800 hover:text-red-400 disabled:opacity-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div>
          {entries.length === 0 && !loading ? (
            <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
              <p className="text-[11px] text-neutral-500">
                No saved missions yet.{" "}
                <Link href="/library" className="text-blue-400 hover:text-blue-300">
                  Save a mission
                </Link>{" "}
                before scheduling it.
              </p>
            </div>
          ) : (
            <ScheduleForm entries={entries} busy={busy} onSubmit={handleCreate} />
          )}
        </div>
      </div>
    </PageShell>
  );
}
