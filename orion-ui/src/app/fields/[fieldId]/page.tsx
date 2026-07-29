"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { PageShell } from "@/components/common/PageShell";
import {
  FieldCanvas,
  LAYER_STYLES,
  type DrawTool,
} from "@/components/fields/FieldCanvas";
import { getPipelineClient } from "@/lib/pipelineClient";
import { isLiveMode } from "@/lib/config";
import {
  pixelToMetric,
  polygonAreaHa,
  formatAreaHa,
  type PixelPoint,
} from "@/lib/fieldGeometry";
import type {
  FieldDefinition,
  FieldImage,
  FieldImageSource,
  MetricPoint,
  Obstacle,
  Zone,
} from "@/contracts/mission";
import {
  ArrowLeft,
  Check,
  Save,
  RotateCcw,
  Trash2,
  Undo2,
  Upload,
  X,
} from "lucide-react";

const ZONE_TOOLS: DrawTool[] = ["crop", "management", "treatment", "exclusion"];
const OBSTACLE_KINDS: Obstacle["kind"][] = [
  "tree",
  "pole",
  "building",
  "irrigation",
  "road",
  "restricted",
];

let geometryCounter = 0;
function newId(prefix: string): string {
  geometryCounter += 1;
  return `${prefix}_${Date.now().toString(36)}_${geometryCounter}`;
}

export default function FieldPreparationPage() {
  const params = useParams();
  const fieldId = String(params.fieldId);
  const live = isLiveMode();
  const client = getPipelineClient();

  const [field, setField] = useState<FieldDefinition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);

  // Editable metadata.
  const [name, setName] = useState("");
  const [cropType, setCropType] = useState("");
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");
  const [metersPerPixel, setMetersPerPixel] = useState(0.5);

  // Editable geometry.
  const [boundary, setBoundary] = useState<MetricPoint[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [obstacles, setObstacles] = useState<Obstacle[]>([]);
  const [images, setImages] = useState<FieldImage[]>([]);

  // Drawing session.
  const [tool, setTool] = useState<DrawTool>("select");
  const [obstacleKind, setObstacleKind] = useState<Obstacle["kind"]>("tree");
  const [draft, setDraft] = useState<PixelPoint[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeImageId, setActiveImageId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const applyField = useCallback((f: FieldDefinition) => {
    setField(f);
    setName(f.name);
    setCropType(f.crop_type);
    setLocation(f.location);
    setNotes(f.notes);
    setMetersPerPixel(f.meters_per_pixel || 0.5);
    setBoundary([...f.boundary_points] as MetricPoint[]);
    setZones([...f.zones]);
    setObstacles([...f.obstacles]);
    setImages([...f.images]);
    setActiveImageId(f.images.length ? f.images[f.images.length - 1].image_id : null);
    setDraft([]);
    setSelectedId(null);
    setDirty(false);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      applyField(await client.getField(fieldId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load field");
    } finally {
      setLoading(false);
    }
  }, [client, fieldId, applyField]);

  useEffect(() => {
    void load();
  }, [load]);

  const markDirty = useCallback(() => setDirty(true), []);

  const activeImage = useMemo(
    () => images.find((i) => i.image_id === activeImageId) ?? null,
    [images, activeImageId]
  );
  const canvasW = activeImage?.width_px || 1200;
  const canvasH = activeImage?.height_px || 800;
  const imageUrl = activeImage ? client.resolveUrl(activeImage.url) : null;

  // -- drawing ---------------------------------------------------------------

  const handleCanvasClick = useCallback((point: PixelPoint) => {
    setDraft((prev) => [...prev, point]);
  }, []);

  const undoPoint = useCallback(() => {
    setDraft((prev) => prev.slice(0, -1));
  }, []);

  const cancelDraft = useCallback(() => {
    setDraft([]);
    setTool("select");
  }, []);

  const finishDraft = useCallback(() => {
    if (draft.length < 3) return;
    const metric = draft.map((p) => pixelToMetric(p, metersPerPixel));
    if (tool === "boundary") {
      setBoundary(metric);
    } else if (ZONE_TOOLS.includes(tool)) {
      const kind = tool as Zone["kind"];
      setZones((prev) => [
        ...prev,
        {
          zone_id: newId("zone"),
          kind,
          label: `${LAYER_STYLES[kind]?.label ?? "Zone"} ${prev.length + 1}`,
          boundary_points: metric,
          crop_type: kind === "crop" ? cropType || "generic" : null,
          enabled: true,
        },
      ]);
    } else if (tool === "obstacle") {
      setObstacles((prev) => [
        ...prev,
        {
          obstacle_id: newId("obs"),
          kind: obstacleKind,
          label: `${obstacleKind} ${prev.length + 1}`,
          points: metric,
        },
      ]);
    }
    setDraft([]);
    setTool("select");
    markDirty();
  }, [draft, metersPerPixel, tool, cropType, obstacleKind, markDirty]);

  // -- geometry editing ------------------------------------------------------

  const removeZone = useCallback(
    (id: string) => {
      setZones((prev) => prev.filter((z) => z.zone_id !== id));
      markDirty();
    },
    [markDirty]
  );
  const removeObstacle = useCallback(
    (id: string) => {
      setObstacles((prev) => prev.filter((o) => o.obstacle_id !== id));
      markDirty();
    },
    [markDirty]
  );
  const clearBoundary = useCallback(() => {
    setBoundary([]);
    markDirty();
  }, [markDirty]);

  const renameZone = useCallback(
    (id: string, label: string) => {
      setZones((prev) =>
        prev.map((z) => (z.zone_id === id ? { ...z, label } : z))
      );
      markDirty();
    },
    [markDirty]
  );
  const toggleZone = useCallback(
    (id: string) => {
      setZones((prev) =>
        prev.map((z) =>
          z.zone_id === id ? { ...z, enabled: z.enabled === false } : z
        )
      );
      markDirty();
    },
    [markDirty]
  );
  const renameObstacle = useCallback(
    (id: string, label: string) => {
      setObstacles((prev) =>
        prev.map((o) => (o.obstacle_id === id ? { ...o, label } : o))
      );
      markDirty();
    },
    [markDirty]
  );

  // -- images ----------------------------------------------------------------

  const handleUpload = useCallback(
    async (file: File, source: FieldImageSource) => {
      setUploading(true);
      setError(null);
      try {
        const image = await client.uploadFieldImage(fieldId, file, source);
        setImages((prev) => [...prev, image]);
        setActiveImageId(image.image_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [client, fieldId]
  );

  // -- persistence -----------------------------------------------------------

  const save = useCallback(async () => {
    if (!field) return;
    setSaving(true);
    setError(null);
    try {
      const payload: Partial<FieldDefinition> = {
        id: field.id,
        name: name.trim() || field.name,
        crop_type: cropType.trim() || "generic",
        location: location.trim(),
        notes,
        meters_per_pixel: metersPerPixel,
        boundary_points: boundary,
        area_ha: boundary.length >= 3 ? polygonAreaHa(boundary) : null,
        zones,
        obstacles,
        images,
      };
      applyField(await client.updateField(field.id, payload));
      setSavedAt(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [
    field,
    name,
    cropType,
    location,
    notes,
    metersPerPixel,
    boundary,
    zones,
    obstacles,
    images,
    client,
    applyField,
  ]);

  if (loading) {
    return (
      <PageShell title="Field Preparation" description={fieldId}>
        <p className="text-xs text-neutral-500">Loading field…</p>
      </PageShell>
    );
  }

  if (!field) {
    return (
      <PageShell title="Field Preparation" description={fieldId}>
        <div className="rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error ?? "Field not found."}
        </div>
        <Link
          href="/fields"
          className="mt-4 inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
        >
          <ArrowLeft className="h-3 w-3" /> Back to fields
        </Link>
      </PageShell>
    );
  }

  const drawing = tool !== "select";

  return (
    <PageShell
      title={`Prepare: ${field.name}`}
      description="Upload imagery and annotate boundaries, zones and obstacles"
      actions={
        <div className="flex items-center gap-2">
          {dirty && (
            <span className="text-[10px] uppercase tracking-wider text-amber-400">
              Unsaved
            </span>
          )}
          {savedAt && !dirty && (
            <span className="text-[10px] uppercase tracking-wider text-green-500">
              Saved
            </span>
          )}
          <button
            type="button"
            onClick={() => void load()}
            className="flex items-center gap-1 rounded-md border border-neutral-700 px-2.5 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Reload
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={saving || !live}
            className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            {saving ? "Saving…" : "Save Field"}
          </button>
        </div>
      }
    >
      {!live && (
        <div className="mb-4 rounded-md border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-400">
          Development mode — saving and image upload require the Digital Twin
          API (set NEXT_PUBLIC_TWIN_API_URL).
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        {/* Canvas + toolbar */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-neutral-800 bg-neutral-900 p-2">
            <ToolButton label="Select" active={tool === "select"} onClick={() => { setTool("select"); setDraft([]); }} />
            <ToolButton label="Boundary" active={tool === "boundary"} color={LAYER_STYLES.boundary.stroke} onClick={() => { setTool("boundary"); setDraft([]); }} />
            {ZONE_TOOLS.map((t) => (
              <ToolButton
                key={t}
                label={LAYER_STYLES[t]?.label ?? t}
                active={tool === t}
                color={LAYER_STYLES[t]?.stroke}
                onClick={() => { setTool(t); setDraft([]); }}
              />
            ))}
            <ToolButton label="Obstacle" active={tool === "obstacle"} color={LAYER_STYLES.obstacle.stroke} onClick={() => { setTool("obstacle"); setDraft([]); }} />
            {tool === "obstacle" && (
              <select
                value={obstacleKind}
                onChange={(e) => setObstacleKind(e.target.value as Obstacle["kind"])}
                className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] text-neutral-200"
              >
                {OBSTACLE_KINDS.map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            )}
          </div>

          {drawing && (
            <div className="flex items-center gap-2 rounded-md border border-blue-900/40 bg-blue-950/20 px-3 py-2 text-[11px] text-blue-300">
              <span>
                Click to add points ({draft.length}). Double-click or Finish to
                close the polygon (min 3 points).
              </span>
              <div className="ml-auto flex gap-1.5">
                <button type="button" onClick={undoPoint} disabled={!draft.length} className="flex items-center gap-1 rounded border border-neutral-700 px-2 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40">
                  <Undo2 className="h-3 w-3" /> Undo
                </button>
                <button type="button" onClick={finishDraft} disabled={draft.length < 3} className="flex items-center gap-1 rounded border border-green-800 px-2 py-1 text-green-400 hover:bg-green-950/40 disabled:opacity-40">
                  <Check className="h-3 w-3" /> Finish
                </button>
                <button type="button" onClick={cancelDraft} className="flex items-center gap-1 rounded border border-neutral-700 px-2 py-1 text-neutral-300 hover:bg-neutral-800">
                  <X className="h-3 w-3" /> Cancel
                </button>
              </div>
            </div>
          )}

          <div className="h-[560px]">
            <FieldCanvas
              imageUrl={imageUrl}
              width={canvasW}
              height={canvasH}
              metersPerPixel={metersPerPixel}
              boundary={boundary}
              zones={zones}
              obstacles={obstacles}
              tool={tool}
              draft={draft}
              selectedId={selectedId}
              onCanvasClick={handleCanvasClick}
              onFinish={finishDraft}
              onSelect={setSelectedId}
            />
          </div>

          {/* Image strip */}
          <div className="flex flex-wrap items-center gap-2">
            {images.map((img) => (
              <button
                key={img.image_id}
                type="button"
                onClick={() => setActiveImageId(img.image_id)}
                className={`rounded-md border px-2 py-1 text-[11px] ${
                  img.image_id === activeImageId
                    ? "border-blue-600 text-blue-300"
                    : "border-neutral-700 text-neutral-400 hover:bg-neutral-800"
                }`}
                title={`${img.filename} · ${img.source} · ${img.width_px}×${img.height_px}`}
              >
                {img.source}: {img.filename}
              </button>
            ))}
            <UploadControl uploading={uploading} disabled={!live} onUpload={handleUpload} />
          </div>
        </div>

        {/* Sidebar: metadata + geometry list */}
        <div className="space-y-4">
          <Panel title="Field Metadata">
            <LabeledInput label="Name" value={name} onChange={(v) => { setName(v); markDirty(); }} />
            <LabeledInput label="Crop type" value={cropType} onChange={(v) => { setCropType(v); markDirty(); }} />
            <LabeledInput label="Location" value={location} onChange={(v) => { setLocation(v); markDirty(); }} />
            <div>
              <label className="mb-1 block text-xs text-neutral-500">
                Scale (meters / pixel)
              </label>
              <input
                type="number"
                step="0.05"
                min="0.01"
                value={metersPerPixel}
                onChange={(e) => { setMetersPerPixel(Number(e.target.value) || 0.5); markDirty(); }}
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-neutral-500">Notes</label>
              <textarea
                value={notes}
                onChange={(e) => { setNotes(e.target.value); markDirty(); }}
                rows={2}
                className="w-full resize-none rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
              />
            </div>
          </Panel>

          <Panel title="Geometry">
            <div className="space-y-2 text-xs">
              <GeometryRow
                color={LAYER_STYLES.boundary.stroke}
                label="Boundary"
                detail={boundary.length >= 3 ? formatAreaHa(boundary) : `${boundary.length} pts`}
                onRemove={boundary.length ? clearBoundary : undefined}
              />
              {zones.length === 0 && obstacles.length === 0 && (
                <p className="text-[11px] text-neutral-600">
                  No zones or obstacles yet. Pick a tool and draw on the canvas.
                </p>
              )}
              {zones.map((z) => (
                <EditableGeometryRow
                  key={z.zone_id}
                  color={LAYER_STYLES[z.kind]?.stroke ?? "#888"}
                  value={z.label}
                  detail={formatAreaHa(z.boundary_points)}
                  disabled={z.enabled === false}
                  selected={z.zone_id === selectedId}
                  onSelect={() => setSelectedId(z.zone_id)}
                  onRename={(v) => renameZone(z.zone_id, v)}
                  onToggle={() => toggleZone(z.zone_id)}
                  onRemove={() => removeZone(z.zone_id)}
                />
              ))}
              {obstacles.map((o) => (
                <EditableGeometryRow
                  key={o.obstacle_id}
                  color={LAYER_STYLES.obstacle.stroke}
                  value={o.label}
                  detail={o.kind}
                  selected={o.obstacle_id === selectedId}
                  onSelect={() => setSelectedId(o.obstacle_id)}
                  onRename={(v) => renameObstacle(o.obstacle_id, v)}
                  onRemove={() => removeObstacle(o.obstacle_id)}
                />
              ))}
            </div>
          </Panel>
        </div>
      </div>

      <Link
        href="/fields"
        className="mt-4 inline-flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-300"
      >
        <ArrowLeft className="h-3 w-3" /> Back to fields
      </Link>
    </PageShell>
  );
}

function ToolButton({
  label,
  active,
  color,
  onClick,
}: {
  label: string;
  active: boolean;
  color?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] transition-colors ${
        active
          ? "border-blue-600 bg-blue-600/20 text-blue-300"
          : "border-neutral-700 text-neutral-400 hover:bg-neutral-800"
      }`}
    >
      {color && (
        <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
      )}
      {label}
    </button>
  );
}

function UploadControl({
  uploading,
  disabled,
  onUpload,
}: {
  uploading: boolean;
  disabled: boolean;
  onUpload: (file: File, source: FieldImageSource) => void;
}) {
  const [source, setSource] = useState<FieldImageSource>("satellite");
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="flex items-center gap-1.5">
      <select
        value={source}
        onChange={(e) => setSource(e.target.value as FieldImageSource)}
        className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] text-neutral-200"
      >
        <option value="satellite">satellite</option>
        <option value="drone">drone</option>
        <option value="manual">manual</option>
      </select>
      <button
        type="button"
        disabled={disabled || uploading}
        onClick={() => inputRef.current?.click()}
        className="flex items-center gap-1 rounded-md border border-neutral-700 px-2.5 py-1 text-[11px] text-neutral-300 hover:bg-neutral-800 disabled:opacity-50"
      >
        <Upload className="h-3 w-3" />
        {uploading ? "Uploading…" : "Upload image"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file, source);
          e.target.value = "";
        }}
      />
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
      <h2 className="mb-3 text-sm font-medium text-neutral-300">{title}</h2>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function LabeledInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-neutral-500">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
      />
    </div>
  );
}

function GeometryRow({
  color,
  label,
  detail,
  onRemove,
}: {
  color: string;
  label: string;
  detail: string;
  onRemove?: () => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1.5">
      <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
      <span className="text-neutral-300">{label}</span>
      <span className="ml-auto font-mono text-[10px] text-neutral-500">{detail}</span>
      {onRemove && (
        <button type="button" onClick={onRemove} className="text-neutral-500 hover:text-red-400" aria-label={`Remove ${label}`}>
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

function EditableGeometryRow({
  color,
  value,
  detail,
  disabled,
  selected,
  onSelect,
  onRename,
  onToggle,
  onRemove,
}: {
  color: string;
  value: string;
  detail: string;
  disabled?: boolean;
  selected?: boolean;
  onSelect: () => void;
  onRename: (v: string) => void;
  onToggle?: () => void;
  onRemove: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`flex items-center gap-2 rounded-md border px-2 py-1.5 ${
        selected ? "border-blue-600 bg-blue-950/20" : "border-neutral-800 bg-neutral-950"
      }`}
    >
      <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: color }} />
      <input
        value={value}
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => onRename(e.target.value)}
        className={`min-w-0 flex-1 bg-transparent text-neutral-300 outline-none ${disabled ? "line-through opacity-60" : ""}`}
      />
      <span className="font-mono text-[10px] text-neutral-500">{detail}</span>
      {onToggle && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onToggle(); }}
          className="text-[10px] text-neutral-500 hover:text-neutral-300"
          title={disabled ? "Enable" : "Disable"}
        >
          {disabled ? "off" : "on"}
        </button>
      )}
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onRemove(); }}
        className="text-neutral-500 hover:text-red-400"
        aria-label={`Remove ${value}`}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
