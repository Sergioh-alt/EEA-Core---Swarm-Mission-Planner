"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { PageShell } from "@/components/common/PageShell";
import { EmptyState } from "@/components/common/EmptyState";
import { getPipelineClient } from "@/lib/pipelineClient";
import { isLiveMode } from "@/lib/config";
import { formatAreaHa } from "@/lib/fieldGeometry";
import type { FieldDefinition } from "@/contracts/mission";
import { MapPinned, Plus, Trash2, Image as ImageIcon } from "lucide-react";

export default function FieldsPage() {
  const router = useRouter();
  const live = isLiveMode();
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const [name, setName] = useState("");
  const [cropType, setCropType] = useState("");
  const [location, setLocation] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPipelineClient().listFields();
      setFields(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fields");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleCreate = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!name.trim()) return;
      setCreating(true);
      setError(null);
      try {
        const created = await getPipelineClient().createField({
          name: name.trim(),
          crop_type: cropType.trim() || "generic",
          location: location.trim(),
          boundary_points: [],
          zones: [],
          obstacles: [],
          images: [],
          meters_per_pixel: 0.5,
          notes: "",
        });
        router.push(`/fields/${created.id}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create field");
        setCreating(false);
      }
    },
    [name, cropType, location, router]
  );

  const handleDelete = useCallback(
    async (fieldId: string) => {
      try {
        await getPipelineClient().deleteField(fieldId);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete field");
      }
    },
    [refresh]
  );

  return (
    <PageShell
      title="Fields"
      description="Create and prepare farm environments before mission generation"
    >
      {!live && (
        <div className="mb-4 rounded-md border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-400">
          Development mode — field acquisition requires the Digital Twin API.
          Set NEXT_PUBLIC_TWIN_API_URL to enable creating and saving fields.
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-3">
          {loading ? (
            <p className="text-xs text-neutral-500">Loading fields…</p>
          ) : fields.length === 0 ? (
            <EmptyState
              icon={<MapPinned className="h-8 w-8" />}
              title="No fields yet"
              description="Create a field to upload imagery and annotate boundaries, zones and obstacles."
            />
          ) : (
            fields.map((field) => (
              <div
                key={field.id}
                className="flex items-center justify-between rounded-lg border border-neutral-800 bg-neutral-900 p-4"
              >
                <Link href={`/fields/${field.id}`} className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-neutral-100">
                      {field.name}
                    </span>
                    <span className="rounded border border-neutral-700 bg-neutral-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-neutral-400">
                      {field.crop_type}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-neutral-500">
                    {field.location && <span>{field.location}</span>}
                    <span>{formatAreaHa(field.boundary_points)}</span>
                    <span>{field.zones.length} zones</span>
                    <span>{field.obstacles.length} obstacles</span>
                    <span className="flex items-center gap-1">
                      <ImageIcon className="h-3 w-3" />
                      {field.images.length}
                    </span>
                  </div>
                </Link>
                <button
                  type="button"
                  onClick={() => void handleDelete(field.id)}
                  className="ml-3 rounded-md border border-neutral-700 p-2 text-neutral-500 transition-colors hover:border-red-800 hover:text-red-400"
                  aria-label={`Delete ${field.name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))
          )}
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="mb-3 text-sm font-medium text-neutral-300">
            Create Field
          </h2>
          <form onSubmit={handleCreate} className="space-y-3">
            <Field label="Field name">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="North Vineyard"
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
              />
            </Field>
            <Field label="Crop type">
              <input
                value={cropType}
                onChange={(e) => setCropType(e.target.value)}
                placeholder="grapes"
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
              />
            </Field>
            <Field label="Location">
              <input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Sector 4, La Rioja"
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
              />
            </Field>
            <button
              type="submit"
              disabled={creating || !name.trim()}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              {creating ? "Creating…" : "Create Field"}
            </button>
          </form>
        </div>
      </div>
    </PageShell>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-neutral-500">{label}</label>
      {children}
    </div>
  );
}
