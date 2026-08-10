"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Library, Plus } from "lucide-react";
import { PageShell } from "@/components/common/PageShell";
import { EmptyState } from "@/components/common/EmptyState";
import { LibraryEntryCard } from "@/components/library/LibraryEntryCard";
import { getPipelineClient } from "@/lib/pipelineClient";
import { isLiveMode } from "@/lib/config";
import type { LibraryEntry, MissionDefinition } from "@/contracts/mission";

/**
 * Mission Library — saved, reusable missions.
 *
 * Every value shown here comes from the stored Mission Definition and the
 * Mission Package the Planning Core produced for it. Execution history lives
 * on its own page and is never mixed into this list.
 */
export default function LibraryPage() {
  const router = useRouter();
  const live = isLiveMode();
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [missions, setMissions] = useState<MissionDefinition[]>([]);
  const [missionId, setMissionId] = useState("");
  const [search, setSearch] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const client = getPipelineClient();
      const [saved, defs] = await Promise.all([
        client.listLibrary(),
        client.listMissions(),
      ]);
      setEntries(saved);
      setMissions(defs);
      setMissionId((current) =>
        current || (defs.length ? defs[defs.length - 1].id : "")
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the library");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return entries.filter((entry) => {
      if (!showArchived && entry.status === "archived") return false;
      if (!needle) return true;
      return [
        entry.name,
        entry.description,
        entry.summary.field_name,
        entry.summary.operation_type,
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [entries, search, showArchived]);

  const handleSave = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!missionId) return;
      setBusy(true);
      setError(null);
      try {
        const entry = await getPipelineClient().saveToLibrary(missionId);
        setNotice(`Saved "${entry.name}" to the Mission Library`);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save mission");
      } finally {
        setBusy(false);
      }
    },
    [missionId, refresh]
  );

  const handleDuplicate = useCallback(
    async (entry: LibraryEntry) => {
      setBusy(true);
      setError(null);
      try {
        const result = await getPipelineClient().duplicateLibraryEntry(
          entry.entry_id,
          `${entry.name} (copy)`
        );
        router.push(`/missions/${result.mission.id}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to duplicate mission");
        setBusy(false);
      }
    },
    [router]
  );

  const handleArchive = useCallback(
    async (entry: LibraryEntry) => {
      setBusy(true);
      setError(null);
      try {
        await getPipelineClient().updateLibraryEntry(entry.entry_id, {
          status: entry.status === "archived" ? "ready" : "archived",
        });
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update mission");
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  const handleDelete = useCallback(
    async (entry: LibraryEntry) => {
      setBusy(true);
      setError(null);
      try {
        await getPipelineClient().deleteLibraryEntry(entry.entry_id);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to remove mission");
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  return (
    <PageShell
      title="Mission Library"
      description="Saved, reusable missions — definition and Planning Core package kept together"
      actions={
        <Link
          href="/history"
          className="rounded-md border border-neutral-700 px-2.5 py-1.5 text-[11px] text-neutral-300 transition-colors hover:bg-neutral-800"
        >
          Execution history
        </Link>
      }
    >
      {!live && (
        <div className="mb-4 rounded-md border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-400">
          Development mode — the Mission Library requires the Digital Twin API.
          Set NEXT_PUBLIC_TWIN_API_URL to enable saved missions.
        </div>
      )}
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
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          <div className="flex items-center gap-3">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search saved missions"
              aria-label="Search saved missions"
              className="flex-1 rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
            />
            <label className="flex items-center gap-1.5 text-[11px] text-neutral-400">
              <input
                type="checkbox"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
              />
              Show archived
            </label>
          </div>

          {loading ? (
            <p className="text-xs text-neutral-500">Loading saved missions…</p>
          ) : visible.length === 0 ? (
            <EmptyState
              icon={<Library className="h-8 w-8" />}
              title="No saved missions"
              description="Save a mission with a generated Mission Package to reuse, schedule and execute it later."
            />
          ) : (
            visible.map((entry) => (
              <LibraryEntryCard
                key={entry.entry_id}
                entry={entry}
                busy={busy}
                onDuplicate={handleDuplicate}
                onArchive={handleArchive}
                onDelete={handleDelete}
              />
            ))
          )}
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="mb-1 text-sm font-medium text-neutral-300">
            Save a mission
          </h2>
          <p className="mb-3 text-[11px] text-neutral-500">
            The Planning Core package generated for the mission is stored with
            it, so a saved mission always runs what was reviewed.
          </p>
          {missions.length === 0 && !loading ? (
            <p className="text-[11px] text-neutral-500">
              No mission definitions yet.{" "}
              <Link href="/missions" className="text-blue-400 hover:text-blue-300">
                Design a mission
              </Link>{" "}
              first.
            </p>
          ) : (
            <form onSubmit={handleSave} className="space-y-3">
              <label className="block text-xs text-neutral-500" htmlFor="mission">
                Mission Definition
              </label>
              <select
                id="mission"
                value={missionId}
                onChange={(e) => setMissionId(e.target.value)}
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
              >
                {missions.map((mission) => (
                  <option key={mission.id} value={mission.id}>
                    {mission.name} — {mission.field.name}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                disabled={busy || !missionId}
                className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                {busy ? "Saving…" : "Save to Library"}
              </button>
            </form>
          )}
        </div>
      </div>
    </PageShell>
  );
}
