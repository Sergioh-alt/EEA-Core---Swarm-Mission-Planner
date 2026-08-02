"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { PageShell } from "@/components/common/PageShell";
import { EmptyState } from "@/components/common/EmptyState";
import { getPipelineClient } from "@/lib/pipelineClient";
import { isLiveMode } from "@/lib/config";
import type { FieldDefinition, MissionDefinition } from "@/contracts/mission";
import { ClipboardList, Plus, Trash2 } from "lucide-react";

const PRIORITY_STYLES: Record<string, string> = {
  low: "border-neutral-700 text-neutral-400",
  normal: "border-blue-800 text-blue-300",
  high: "border-amber-800 text-amber-300",
  urgent: "border-red-800 text-red-300",
};

export default function MissionsPage() {
  const router = useRouter();
  const live = isLiveMode();
  const [missions, setMissions] = useState<MissionDefinition[]>([]);
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const [name, setName] = useState("");
  const [fieldId, setFieldId] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const client = getPipelineClient();
      const [m, f] = await Promise.all([
        client.listMissions(),
        client.listFields(),
      ]);
      setMissions(m);
      setFields(f);
      if (!fieldId && f.length) setFieldId(f[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load missions");
    } finally {
      setLoading(false);
    }
  }, [fieldId]);

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreate = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!name.trim() || !fieldId) return;
      setCreating(true);
      setError(null);
      try {
        const field = fields.find((f) => f.id === fieldId);
        if (!field) throw new Error("Select a prepared field");
        const created = await getPipelineClient().createMission({
          name: name.trim(),
          description: "",
          field_id: field.id,
          priority: "normal",
          field: {
            name: field.name,
            crop_type: field.crop_type,
            boundary_points: field.boundary_points,
            area_ha: field.area_ha ?? null,
            zones: field.zones,
            obstacles: field.obstacles,
            images: field.images,
            meters_per_pixel: field.meters_per_pixel,
            location: field.location,
            notes: field.notes,
          },
          operation: {
            operation_type: "spray",
            num_drones: 3,
            planning_mode: "automatic",
            coverage_direction: "auto",
            route_preference: "balanced",
          },
          fleet: [],
          products: [],
        });
        router.push(`/missions/${created.id}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create mission");
        setCreating(false);
      }
    },
    [name, fieldId, fields, router]
  );

  const handleDelete = useCallback(
    async (missionId: string) => {
      try {
        await getPipelineClient().deleteMission(missionId);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete mission");
      }
    },
    [refresh]
  );

  return (
    <PageShell
      title="Mission Designer"
      description="Turn a prepared field into a complete Mission Definition"
    >
      {!live && (
        <div className="mb-4 rounded-md border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-400">
          Development mode — the Mission Designer requires the Digital Twin API.
          Set NEXT_PUBLIC_TWIN_API_URL to enable creating missions.
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          {loading ? (
            <p className="text-xs text-neutral-500">Loading missions…</p>
          ) : missions.length === 0 ? (
            <EmptyState
              icon={<ClipboardList className="h-8 w-8" />}
              title="No missions yet"
              description="Create a mission from a prepared field to configure operation, products, parameters and fleet."
            />
          ) : (
            missions.map((mission) => (
              <div
                key={mission.id}
                className="flex items-center justify-between rounded-lg border border-neutral-800 bg-neutral-900 p-4"
              >
                <Link
                  href={`/missions/${mission.id}`}
                  className="min-w-0 flex-1"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-neutral-100">
                      {mission.name}
                    </span>
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${
                        PRIORITY_STYLES[mission.priority ?? "normal"] ??
                        PRIORITY_STYLES.normal
                      }`}
                    >
                      {mission.priority ?? "normal"}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-neutral-500">
                    <span>{mission.field.name}</span>
                    <span>{mission.operation.operation_type}</span>
                    <span>{mission.fleet.length} drones</span>
                    <span>{mission.products.length} products</span>
                  </div>
                </Link>
                <button
                  type="button"
                  onClick={() => void handleDelete(mission.id)}
                  className="ml-3 rounded-md border border-neutral-700 p-2 text-neutral-500 transition-colors hover:border-red-800 hover:text-red-400"
                  aria-label={`Delete ${mission.name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))
          )}
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="mb-3 text-sm font-medium text-neutral-300">
            New Mission
          </h2>
          {fields.length === 0 && !loading ? (
            <p className="text-[11px] text-neutral-500">
              No prepared fields yet.{" "}
              <Link href="/fields" className="text-blue-400 hover:text-blue-300">
                Create a field
              </Link>{" "}
              before designing a mission.
            </p>
          ) : (
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-neutral-500">
                  Mission name
                </label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Spring spray pass"
                  className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-neutral-500">
                  Prepared field
                </label>
                <select
                  value={fieldId}
                  onChange={(e) => setFieldId(e.target.value)}
                  className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
                >
                  {fields.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name} ({f.crop_type})
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="submit"
                disabled={creating || !name.trim() || !fieldId}
                className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                {creating ? "Creating…" : "Create Mission"}
              </button>
            </form>
          )}
        </div>
      </div>
    </PageShell>
  );
}
