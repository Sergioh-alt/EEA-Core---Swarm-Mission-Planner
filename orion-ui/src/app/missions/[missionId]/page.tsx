"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { PageShell } from "@/components/common/PageShell";
import { FieldCanvas } from "@/components/fields/FieldCanvas";
import { getPipelineClient } from "@/lib/pipelineClient";
import { isLiveMode } from "@/lib/config";
import { formatAreaHa } from "@/lib/fieldGeometry";
import type {
  CoverageDirection,
  FleetInventory,
  FleetItem,
  FleetModel,
  MissionDefinition,
  MissionPackage,
  MissionPriority,
  OperationParams,
  PlanningMode,
  ProductSelection,
  RoutePreference,
  Zone,
} from "@/contracts/mission";
import {
  ArrowLeft,
  Check,
  Cpu,
  Plus,
  Send,
  Trash2,
  X,
} from "lucide-react";

const OPERATION_TYPES = [
  "spray",
  "fertilization",
  "seeding",
  "mapping",
  "inspection",
  "custom",
] as const;

const PRIORITIES: MissionPriority[] = ["low", "normal", "high", "urgent"];
const PLANNING_MODES: PlanningMode[] = ["manual", "assisted", "automatic"];
const COVERAGE_DIRECTIONS: CoverageDirection[] = [
  "auto",
  "north_south",
  "east_west",
];
const ROUTE_PREFERENCES: RoutePreference[] = ["balanced", "time", "battery"];
const PRODUCT_OPERATIONS = new Set(["spray", "fertilization", "seeding"]);

function num(value: string): number | null {
  const n = Number(value);
  return value.trim() === "" || Number.isNaN(n) ? null : n;
}

export default function MissionDesignerPage() {
  const params = useParams();
  const missionId = String(params.missionId);
  const live = isLiveMode();
  const client = getPipelineClient();

  const [mission, setMission] = useState<MissionDefinition | null>(null);
  const [inventory, setInventory] = useState<FleetInventory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Mission information.
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<MissionPriority>("normal");
  const [scheduledDate, setScheduledDate] = useState("");
  const [notes, setNotes] = useState("");

  // Operation + preferences.
  const [operationType, setOperationType] = useState("spray");
  const [customOperation, setCustomOperation] = useState("");
  const [planningMode, setPlanningMode] = useState<PlanningMode>("automatic");
  const [numDrones, setNumDrones] = useState("3");
  const [flightAltitude, setFlightAltitude] = useState("");
  const [nominalSpeed, setNominalSpeed] = useState("");
  const [overlap, setOverlap] = useState("");
  const [safetyMargin, setSafetyMargin] = useState("");
  const [coverageDirection, setCoverageDirection] =
    useState<CoverageDirection>("auto");
  const [routePreference, setRoutePreference] =
    useState<RoutePreference>("balanced");

  // Zones / products / fleet.
  const [zones, setZones] = useState<Zone[]>([]);
  const [products, setProducts] = useState<ProductSelection[]>([]);
  const [fleet, setFleet] = useState<FleetItem[]>([]);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);

  // Planning Core result (read-only).
  const [pkg, setPkg] = useState<MissionPackage | null>(null);
  const [computing, setComputing] = useState(false);

  const applyMission = useCallback((m: MissionDefinition) => {
    setMission(m);
    setName(m.name);
    setDescription(m.description);
    setPriority(m.priority ?? "normal");
    setScheduledDate(m.scheduled_date ?? "");
    setNotes(m.notes ?? "");
    const knownOp = (OPERATION_TYPES as readonly string[]).includes(
      m.operation.operation_type
    );
    setOperationType(knownOp ? m.operation.operation_type : "custom");
    setCustomOperation(knownOp ? "" : m.operation.operation_type);
    setPlanningMode(m.operation.planning_mode);
    setNumDrones(String(m.operation.num_drones ?? 3));
    setFlightAltitude(
      m.operation.flight_altitude_m != null
        ? String(m.operation.flight_altitude_m)
        : ""
    );
    setNominalSpeed(
      m.operation.nominal_speed_ms != null
        ? String(m.operation.nominal_speed_ms)
        : ""
    );
    setOverlap(
      m.operation.overlap_pct != null ? String(m.operation.overlap_pct) : ""
    );
    setSafetyMargin(
      m.operation.safety_margin_m != null
        ? String(m.operation.safety_margin_m)
        : ""
    );
    setCoverageDirection(m.operation.coverage_direction ?? "auto");
    setRoutePreference(m.operation.route_preference ?? "balanced");
    setZones([...m.field.zones]);
    setProducts([...m.products]);
    setFleet([...m.fleet]);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, inv] = await Promise.all([
        client.getMission(missionId),
        client.getFleetInventory(),
      ]);
      applyMission(m);
      setInventory(inv);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load mission");
    } finally {
      setLoading(false);
    }
  }, [client, missionId, applyMission]);

  useEffect(() => {
    void load();
  }, [load]);

  const activeImage = useMemo(() => {
    const imgs = mission?.field.images ?? [];
    return imgs.length ? imgs[imgs.length - 1] : null;
  }, [mission]);
  const canvasW = activeImage?.width_px || 1200;
  const canvasH = activeImage?.height_px || 800;
  const imageUrl = activeImage ? client.resolveUrl(activeImage.url) : null;

  const resolvedOperation = useMemo(
    () =>
      operationType === "custom"
        ? customOperation.trim() || "custom"
        : operationType,
    [operationType, customOperation]
  );

  const buildDefinition = useCallback((): Partial<MissionDefinition> => {
    if (!mission) return {};
    const operation: OperationParams = {
      operation_type: resolvedOperation,
      num_drones: num(numDrones) ?? 1,
      flight_altitude_m: num(flightAltitude),
      planning_mode: planningMode,
      nominal_speed_ms: num(nominalSpeed),
      overlap_pct: num(overlap),
      safety_margin_m: num(safetyMargin),
      coverage_direction: coverageDirection,
      route_preference: routePreference,
    };
    return {
      id: mission.id,
      name: name.trim(),
      description: description.trim(),
      field_id: mission.field_id,
      priority,
      scheduled_date: scheduledDate,
      notes: notes.trim(),
      field: { ...mission.field, zones },
      operation,
      environment: mission.environment,
      fleet,
      products,
    };
  }, [
    mission,
    resolvedOperation,
    numDrones,
    flightAltitude,
    planningMode,
    nominalSpeed,
    overlap,
    safetyMargin,
    coverageDirection,
    routePreference,
    name,
    description,
    priority,
    scheduledDate,
    notes,
    zones,
    fleet,
    products,
  ]);

  // -- completeness validation (interface level only) ------------------------

  const checks = useMemo(() => {
    const hasField = (mission?.field.boundary_points.length ?? 0) >= 3;
    const hasZoneSelection =
      zones.length === 0 || zones.some((z) => z.enabled !== false);
    const productNeeded = PRODUCT_OPERATIONS.has(resolvedOperation);
    return [
      { key: "name", label: "Mission name provided", ok: name.trim().length > 0 },
      { key: "field", label: "Prepared field with boundary", ok: hasField },
      {
        key: "zones",
        label: "At least one area participates",
        ok: hasZoneSelection,
      },
      {
        key: "operation",
        label: "Operation type selected",
        ok: resolvedOperation.trim().length > 0,
      },
      {
        key: "product",
        label: productNeeded
          ? "At least one product configured"
          : "Products optional for this operation",
        ok: !productNeeded || products.length > 0,
      },
      {
        key: "params",
        label: "Flight altitude set",
        ok: (num(flightAltitude) ?? 0) > 0,
      },
      { key: "fleet", label: "At least one drone selected", ok: fleet.length > 0 },
    ];
  }, [
    mission,
    zones,
    resolvedOperation,
    name,
    products,
    flightAltitude,
    fleet,
  ]);

  const complete = checks.every((c) => c.ok);

  // -- persistence + planning ------------------------------------------------

  const handleSave = useCallback(async (): Promise<MissionDefinition | null> => {
    if (!mission) return null;
    setSaving(true);
    setError(null);
    try {
      const updated = await client.updateMission(mission.id, buildDefinition());
      setMission(updated);
      setSavedAt(Date.now());
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save mission");
      return null;
    } finally {
      setSaving(false);
    }
  }, [client, mission, buildDefinition]);

  const handleCompute = useCallback(async () => {
    if (!mission) return;
    setComputing(true);
    setError(null);
    setPkg(null);
    try {
      const saved = await handleSave();
      if (!saved) return;
      const result = await client.computePlanning(saved.id);
      setPkg(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Planning Core request failed"
      );
    } finally {
      setComputing(false);
    }
  }, [client, mission, handleSave]);

  // -- zone / product / fleet mutations --------------------------------------

  const toggleZone = useCallback((zoneId: string) => {
    setZones((prev) =>
      prev.map((z) =>
        z.zone_id === zoneId ? { ...z, enabled: z.enabled === false } : z
      )
    );
  }, []);

  const selectEntireField = useCallback(() => {
    setZones((prev) => prev.map((z) => ({ ...z, enabled: true })));
  }, []);

  const addProduct = useCallback(
    (model: ProductSelection) => {
      setProducts((prev) => [
        ...prev,
        {
          product_id: model.product_id,
          name: model.name,
          rate_l_per_ha: model.rate_l_per_ha ?? null,
          tank: null,
          concentration_pct: null,
          dilution: null,
          safety_notes: "",
        },
      ]);
    },
    []
  );

  const updateProduct = useCallback(
    (index: number, patch: Partial<ProductSelection>) => {
      setProducts((prev) =>
        prev.map((p, i) => (i === index ? { ...p, ...patch } : p))
      );
    },
    []
  );

  const removeProduct = useCallback((index: number) => {
    setProducts((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const addDrone = useCallback((model: FleetModel) => {
    setFleet((prev) => [
      ...prev,
      {
        drone_id: prev.length + 1,
        model: model.model,
        vendor: model.vendor,
        battery_capacity_mah: model.battery_capacity_mah,
        liquid_capacity_l: model.liquid_capacity_l,
        working_width_m: model.working_width_m ?? null,
      },
    ]);
  }, []);

  const removeDrone = useCallback((index: number) => {
    setFleet((prev) =>
      prev
        .filter((_, i) => i !== index)
        .map((item, i) => ({ ...item, drone_id: i + 1 }))
    );
  }, []);

  if (loading) {
    return (
      <PageShell title="Mission Designer" description="Loading mission…">
        <p className="text-xs text-neutral-500">Loading…</p>
      </PageShell>
    );
  }

  if (!mission) {
    return (
      <PageShell title="Mission Designer" description="Mission not found">
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

  return (
    <PageShell
      title={`Mission Designer — ${mission.name}`}
      description="Collect every parameter for a Mission Definition (no planning here)"
      actions={
        <div className="flex items-center gap-2">
          {savedAt && (
            <span className="text-[11px] text-neutral-500">Saved</span>
          )}
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || !live}
            className="rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save draft"}
          </button>
          <Link
            href="/missions"
            className="inline-flex items-center gap-1 rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800"
          >
            <ArrowLeft className="h-3 w-3" /> Missions
          </Link>
        </div>
      }
    >
      {error && (
        <div className="mb-4 rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Left column: forms */}
        <div className="space-y-6 xl:col-span-2">
          {/* 1. Mission information */}
          <Section title="Mission Information">
            <Field label="Mission name">
              <TextInput value={name} onChange={setName} />
            </Field>
            <Field label="Description">
              <TextInput value={description} onChange={setDescription} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Priority">
                <Select
                  value={priority}
                  options={PRIORITIES}
                  onChange={(v) => setPriority(v as MissionPriority)}
                />
              </Field>
              <Field label="Estimated execution date">
                <input
                  type="date"
                  value={scheduledDate}
                  onChange={(e) => setScheduledDate(e.target.value)}
                  className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
                />
              </Field>
            </div>
            <Field label="Notes (optional)">
              <TextInput value={notes} onChange={setNotes} />
            </Field>
          </Section>

          {/* 2. Zone selection */}
          <Section
            title="Zone Selection"
            action={
              zones.length > 0 ? (
                <button
                  type="button"
                  onClick={selectEntireField}
                  className="rounded-md border border-neutral-700 px-2 py-1 text-[11px] text-neutral-300 hover:bg-neutral-800"
                >
                  Select entire field
                </button>
              ) : undefined
            }
          >
            <div className="h-[360px]">
              <FieldCanvas
                imageUrl={imageUrl}
                width={canvasW}
                height={canvasH}
                metersPerPixel={mission.field.meters_per_pixel || 0.5}
                boundary={mission.field.boundary_points}
                zones={zones}
                obstacles={mission.field.obstacles}
                tool="select"
                draft={[]}
                selectedId={selectedZoneId}
                onCanvasClick={() => {}}
                onFinish={() => {}}
                onSelect={setSelectedZoneId}
              />
            </div>
            {zones.length === 0 ? (
              <p className="text-[11px] text-neutral-500">
                This field has no internal zones — the entire field boundary
                participates in the mission.
              </p>
            ) : (
              <div className="space-y-1.5">
                {zones.map((z) => (
                  <div
                    key={z.zone_id}
                    className="flex items-center gap-2 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1.5 text-xs"
                  >
                    <span className="text-neutral-300">{z.label}</span>
                    <span className="text-[10px] uppercase tracking-wider text-neutral-600">
                      {z.kind}
                    </span>
                    <button
                      type="button"
                      onClick={() => toggleZone(z.zone_id)}
                      className={`ml-auto rounded px-2 py-0.5 text-[10px] ${
                        z.enabled === false
                          ? "border border-neutral-700 text-neutral-500"
                          : "border border-blue-700 bg-blue-950/40 text-blue-300"
                      }`}
                    >
                      {z.enabled === false ? "excluded" : "included"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Section>

          {/* 3. Agricultural operation */}
          <Section title="Agricultural Operation">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Operation type">
                <Select
                  value={operationType}
                  options={OPERATION_TYPES}
                  onChange={setOperationType}
                />
              </Field>
              {operationType === "custom" && (
                <Field label="Custom operation">
                  <TextInput
                    value={customOperation}
                    onChange={setCustomOperation}
                  />
                </Field>
              )}
            </div>
          </Section>

          {/* 4. Product configuration */}
          <Section title="Product Configuration">
            {inventory && inventory.products.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {inventory.products.map((p) => (
                  <button
                    key={p.product_id}
                    type="button"
                    onClick={() => addProduct(p)}
                    className="inline-flex items-center gap-1 rounded-md border border-neutral-700 px-2 py-1 text-[11px] text-neutral-300 hover:bg-neutral-800"
                  >
                    <Plus className="h-3 w-3" /> {p.name}
                  </button>
                ))}
              </div>
            )}
            {products.length === 0 ? (
              <p className="text-[11px] text-neutral-500">
                No products added. Add one or more from the catalog above.
              </p>
            ) : (
              <div className="space-y-3">
                {products.map((p, i) => (
                  <div
                    key={`${p.product_id}-${i}`}
                    className="rounded-md border border-neutral-800 bg-neutral-950 p-3"
                  >
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-xs font-medium text-neutral-200">
                        {p.name}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeProduct(i)}
                        className="ml-auto text-neutral-500 hover:text-red-400"
                        aria-label={`Remove ${p.name}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <Field label="Rate (L/ha)">
                        <NumberInput
                          value={p.rate_l_per_ha}
                          onChange={(v) =>
                            updateProduct(i, { rate_l_per_ha: v })
                          }
                        />
                      </Field>
                      <Field label="Tank">
                        <input
                          value={p.tank ?? ""}
                          onChange={(e) =>
                            updateProduct(i, { tank: e.target.value || null })
                          }
                          className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs text-neutral-200 outline-none focus:border-blue-600"
                        />
                      </Field>
                      <Field label="Concentration (%)">
                        <NumberInput
                          value={p.concentration_pct}
                          onChange={(v) =>
                            updateProduct(i, { concentration_pct: v })
                          }
                        />
                      </Field>
                      <Field label="Dilution">
                        <input
                          value={p.dilution ?? ""}
                          onChange={(e) =>
                            updateProduct(i, {
                              dilution: e.target.value || null,
                            })
                          }
                          placeholder="e.g. 1:100"
                          className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs text-neutral-200 outline-none focus:border-blue-600"
                        />
                      </Field>
                    </div>
                    <div className="mt-2">
                      <Field label="Safety parameters / notes">
                        <input
                          value={p.safety_notes ?? ""}
                          onChange={(e) =>
                            updateProduct(i, { safety_notes: e.target.value })
                          }
                          className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs text-neutral-200 outline-none focus:border-blue-600"
                        />
                      </Field>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Section>

          {/* 5. Operational parameters */}
          <Section title="Operational Parameters (preferences)">
            <p className="text-[11px] text-neutral-500">
              Preferences only — the Planning Core decides how to use them.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Flight altitude (m)">
                <NumberInput
                  value={num(flightAltitude)}
                  onChange={(v) => setFlightAltitude(v == null ? "" : String(v))}
                />
              </Field>
              <Field label="Nominal speed (m/s)">
                <NumberInput
                  value={num(nominalSpeed)}
                  onChange={(v) => setNominalSpeed(v == null ? "" : String(v))}
                />
              </Field>
              <Field label="Overlap (%)">
                <NumberInput
                  value={num(overlap)}
                  onChange={(v) => setOverlap(v == null ? "" : String(v))}
                />
              </Field>
              <Field label="Safety margin (m)">
                <NumberInput
                  value={num(safetyMargin)}
                  onChange={(v) => setSafetyMargin(v == null ? "" : String(v))}
                />
              </Field>
              <Field label="Coverage direction">
                <Select
                  value={coverageDirection}
                  options={COVERAGE_DIRECTIONS}
                  onChange={(v) =>
                    setCoverageDirection(v as CoverageDirection)
                  }
                />
              </Field>
              <Field label="Route preference">
                <Select
                  value={routePreference}
                  options={ROUTE_PREFERENCES}
                  onChange={(v) => setRoutePreference(v as RoutePreference)}
                />
              </Field>
              <Field label="Planning mode">
                <Select
                  value={planningMode}
                  options={PLANNING_MODES}
                  onChange={(v) => setPlanningMode(v as PlanningMode)}
                />
              </Field>
              <Field label="Drones requested">
                <NumberInput
                  value={num(numDrones)}
                  onChange={(v) => setNumDrones(v == null ? "" : String(v))}
                />
              </Field>
            </div>
          </Section>

          {/* 6. Fleet selection */}
          <Section title="Fleet Selection">
            {inventory && inventory.drone_models.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {inventory.drone_models.map((m) => (
                  <button
                    key={m.model}
                    type="button"
                    onClick={() => addDrone(m)}
                    className="inline-flex items-center gap-1 rounded-md border border-neutral-700 px-2 py-1 text-[11px] text-neutral-300 hover:bg-neutral-800"
                    title={`${m.vendor} · ${m.liquid_capacity_l} L · ${m.battery_capacity_mah} mAh`}
                  >
                    <Plus className="h-3 w-3" /> {m.model}
                  </button>
                ))}
              </div>
            )}
            {fleet.length === 0 ? (
              <p className="text-[11px] text-neutral-500">
                No drones selected. Add available assets from the inventory
                above (specifications are read-only; no allocation happens here).
              </p>
            ) : (
              <div className="space-y-1.5">
                {fleet.map((f, i) => (
                  <div
                    key={`${f.model}-${i}`}
                    className="flex items-center gap-2 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1.5 text-xs"
                  >
                    <span className="text-neutral-300">{f.model}</span>
                    <span className="text-[10px] text-neutral-600">
                      {f.vendor}
                    </span>
                    <span className="ml-auto font-mono text-[10px] text-neutral-500">
                      {f.liquid_capacity_l} L · {f.battery_capacity_mah} mAh
                      {f.working_width_m ? ` · ${f.working_width_m} m` : ""}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeDrone(i)}
                      className="text-neutral-500 hover:text-red-400"
                      aria-label={`Remove ${f.model}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Section>
        </div>

        {/* Right column: validation + preview + planning */}
        <div className="space-y-6">
          <Section title="Completeness">
            <div className="space-y-1.5">
              {checks.map((c) => (
                <div
                  key={c.key}
                  className="flex items-center gap-2 text-xs text-neutral-300"
                >
                  {c.ok ? (
                    <Check className="h-3.5 w-3.5 text-green-500" />
                  ) : (
                    <X className="h-3.5 w-3.5 text-red-500" />
                  )}
                  <span className={c.ok ? "" : "text-neutral-500"}>
                    {c.label}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-neutral-600">
              Interface completeness only — never operational feasibility.
            </p>
          </Section>

          <Section title="Mission Definition Preview">
            <PreviewRow label="Field" value={mission.field.name} />
            <PreviewRow
              label="Coverage"
              value={
                zones.length === 0
                  ? "Entire field"
                  : `${
                      zones.filter((z) => z.enabled !== false).length
                    } / ${zones.length} zones`
              }
            />
            <PreviewRow
              label="Area"
              value={
                mission.field.boundary_points.length >= 3
                  ? formatAreaHa(mission.field.boundary_points)
                  : mission.field.area_ha != null
                    ? `${mission.field.area_ha.toFixed(2)} ha`
                    : "—"
              }
            />
            <PreviewRow label="Operation" value={resolvedOperation} />
            <PreviewRow label="Priority" value={priority} />
            <PreviewRow
              label="Products"
              value={
                products.length
                  ? products.map((p) => p.name).join(", ")
                  : "None"
              }
            />
            <PreviewRow
              label="Altitude"
              value={flightAltitude ? `${flightAltitude} m` : "—"}
            />
            <PreviewRow
              label="Fleet"
              value={
                fleet.length
                  ? `${fleet.length} drone(s): ${fleet
                      .map((f) => f.model)
                      .join(", ")}`
                  : "None"
              }
            />
            <p className="mt-2 text-[10px] text-neutral-600">
              This is a Mission Definition preview — not yet a Mission Package.
            </p>
          </Section>

          <Section title="Planning Core">
            <button
              type="button"
              onClick={() => void handleCompute()}
              disabled={!complete || computing || !live}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              {computing ? "Submitting…" : "Submit to Planning Core"}
            </button>
            <p className="text-[10px] text-neutral-600">
              Saves the definition and submits it to the existing Planning Core
              (10D.2). All planning, routing, resourcing and risk analysis run
              there — never in this interface.
            </p>
            {pkg && <PackageResult pkg={pkg} />}
          </Section>
        </div>
      </div>
    </PageShell>
  );
}

// ---------------------------------------------------------------------------
// Presentational helpers
// ---------------------------------------------------------------------------

function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium text-neutral-300">{title}</h2>
        {action}
      </div>
      <div className="space-y-3">{children}</div>
    </div>
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

function TextInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
    />
  );
}

function NumberInput({
  value,
  onChange,
}: {
  value: number | null | undefined;
  onChange: (v: number | null) => void;
}) {
  return (
    <input
      type="number"
      value={value == null ? "" : value}
      onChange={(e) => {
        const raw = e.target.value;
        const n = Number(raw);
        onChange(raw.trim() === "" || Number.isNaN(n) ? null : n);
      }}
      className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs text-neutral-200 outline-none focus:border-blue-600"
    />
  );
}

function Select({
  value,
  options,
  onChange,
}: {
  value: string;
  options: readonly string[];
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

function PreviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 text-xs">
      <span className="text-neutral-500">{label}</span>
      <span className="text-right text-neutral-200">{value}</span>
    </div>
  );
}

function PackageResult({ pkg }: { pkg: MissionPackage }) {
  const rec = pkg.recommendation as {
    go_no_go?: string;
    feasible?: boolean;
    coverage_pct?: number;
    estimated_duration?: string;
    recommended_drones?: number;
    summary?: string;
  };
  const resources = pkg.resources as {
    total_liquid_l?: number;
    total_refills?: number;
    mission_duration_formatted?: string;
  };
  const risks = pkg.risks as { overall_risk?: string; mission_viable?: boolean };
  return (
    <div className="mt-3 space-y-2 rounded-md border border-neutral-800 bg-neutral-950 p-3">
      <div className="flex items-center gap-2 text-xs font-medium text-neutral-200">
        <Cpu className="h-3.5 w-3.5 text-blue-400" />
        Mission Package (Planning Core output — read-only)
      </div>
      <PreviewRow label="Go / No-Go" value={rec.go_no_go ?? "—"} />
      <PreviewRow
        label="Coverage"
        value={rec.coverage_pct != null ? `${rec.coverage_pct}%` : "—"}
      />
      <PreviewRow
        label="Est. duration"
        value={
          rec.estimated_duration ??
          resources.mission_duration_formatted ??
          "—"
        }
      />
      <PreviewRow label="Routes" value={String(pkg.routes.length)} />
      <PreviewRow
        label="Liquid"
        value={
          resources.total_liquid_l != null
            ? `${resources.total_liquid_l} L`
            : "—"
        }
      />
      <PreviewRow label="Overall risk" value={risks.overall_risk ?? "—"} />
      <PreviewRow
        label="Definition valid"
        value={pkg.validation.valid ? "yes" : "no"}
      />
      {pkg.validation.warnings.length > 0 && (
        <p className="text-[10px] text-amber-500">
          {pkg.validation.warnings.length} planning warning(s)
        </p>
      )}
      {rec.summary && (
        <p className="text-[11px] text-neutral-400">{rec.summary}</p>
      )}
    </div>
  );
}
