"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { PageShell } from "@/components/common/PageShell";
import { getPipelineClient } from "@/lib/pipelineClient";
import { isLiveMode } from "@/lib/config";
import type {
  FleetInventory,
  FleetItem,
  FleetModel,
  MissionDefinition,
  ProductSelection,
  TankConfig,
} from "@/contracts/mission";
import { ArrowLeft, Check, Plus, Trash2, X } from "lucide-react";

/** A product option an operator can assign to a tank. */
interface ProductOption {
  readonly product_id: string;
  readonly name: string;
}

function modelFor(
  inventory: FleetInventory | null,
  model: string
): FleetModel | undefined {
  return inventory?.drone_models.find((m) => m.model === model);
}

export default function FleetConfigurationPage() {
  const params = useParams();
  const missionId = String(params.missionId);
  const live = isLiveMode();
  const client = getPipelineClient();

  const [mission, setMission] = useState<MissionDefinition | null>(null);
  const [inventory, setInventory] = useState<FleetInventory | null>(null);
  const [fleet, setFleet] = useState<FleetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [m, inv] = await Promise.all([
          client.getMission(missionId),
          client.getFleetInventory(),
        ]);
        if (!active) return;
        setMission(m);
        setInventory(inv);
        setFleet([...m.fleet]);
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

  // Products the operator may assign to tanks: those configured in the mission
  // (Mission Designer), else the read-only catalog. No consumption is computed.
  const productOptions: ProductOption[] = useMemo(() => {
    const source: readonly ProductSelection[] =
      mission && mission.products.length > 0
        ? mission.products
        : inventory?.products ?? [];
    return source.map((p) => ({ product_id: p.product_id, name: p.name }));
  }, [mission, inventory]);

  const operationType = mission?.operation.operation_type ?? "";

  // -- fleet mutations (selection + configuration; never allocation) ---------

  const patchDrone = useCallback(
    (index: number, patch: Partial<FleetItem>) => {
      setFleet((prev) =>
        prev.map((item, i) => (i === index ? { ...item, ...patch } : item))
      );
    },
    []
  );

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
        status: model.status ?? "available",
        payload_capacity_kg: model.payload_capacity_kg ?? null,
        estimated_flight_time_min: model.estimated_flight_time_min ?? null,
        supported_operations: model.supported_operations
          ? [...model.supported_operations]
          : [],
        sensors: model.sensors ? [...model.sensors] : [],
        equipment: [],
        camera_package: null,
        sprayer_config: null,
        granular_spreader: null,
        tanks: (model.tanks ?? []).map((t) => ({
          tank_id: t.tank_id,
          label: t.label,
          capacity_l: t.capacity_l,
          product_id: null,
          product_name: null,
        })),
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

  const toggleInList = useCallback(
    (index: number, key: "equipment" | "sensors", value: string) => {
      setFleet((prev) =>
        prev.map((item, i) => {
          if (i !== index) return item;
          const current = item[key] ?? [];
          const next = current.includes(value)
            ? current.filter((v) => v !== value)
            : [...current, value];
          return { ...item, [key]: next };
        })
      );
    },
    []
  );

  const assignTankProduct = useCallback(
    (index: number, tankId: string, productId: string) => {
      const opt = productOptions.find((p) => p.product_id === productId);
      setFleet((prev) =>
        prev.map((item, i) => {
          if (i !== index) return item;
          const tanks: TankConfig[] = (item.tanks ?? []).map((t) =>
            t.tank_id === tankId
              ? {
                  ...t,
                  product_id: opt ? opt.product_id : null,
                  product_name: opt ? opt.name : null,
                }
              : t
          );
          return { ...item, tanks };
        })
      );
    },
    [productOptions]
  );

  const handleSave = useCallback(async (): Promise<boolean> => {
    if (!mission) return false;
    setSaving(true);
    setError(null);
    try {
      const updated = await client.updateMission(mission.id, {
        ...mission,
        fleet,
      });
      setMission(updated);
      setFleet([...updated.fleet]);
      setSavedAt(Date.now());
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
      return false;
    } finally {
      setSaving(false);
    }
  }, [client, mission, fleet]);

  // -- informational fleet summary (static catalog sums; no planning) --------

  const summary = useMemo(() => {
    const drones = fleet.length;
    const totalPayloadKg = fleet.reduce(
      (acc, f) => acc + (f.payload_capacity_kg ?? 0),
      0
    );
    const totalLiquidL = fleet.reduce((acc, f) => acc + f.liquid_capacity_l, 0);
    const enduranceValues = fleet
      .map((f) => f.estimated_flight_time_min)
      .filter((v): v is number => typeof v === "number");
    const minEnduranceMin =
      enduranceValues.length > 0 ? Math.min(...enduranceValues) : null;
    const equipment = Array.from(
      new Set(fleet.flatMap((f) => f.equipment ?? []))
    );
    // Configuration completeness (interface-level only — NOT feasibility).
    const productNeeded = ["spray", "fertilization", "seeding"].includes(
      operationType
    );
    const allSupportOp =
      drones > 0 &&
      fleet.every((f) =>
        (f.supported_operations ?? []).length === 0
          ? true
          : (f.supported_operations ?? []).includes(operationType)
      );
    const anyProductAssigned = fleet.some((f) =>
      (f.tanks ?? []).some((t) => !!t.product_id)
    );
    const ready =
      drones > 0 && allSupportOp && (!productNeeded || anyProductAssigned);
    return {
      drones,
      totalPayloadKg,
      totalLiquidL,
      minEnduranceMin,
      equipment,
      allSupportOp,
      anyProductAssigned,
      productNeeded,
      ready,
    };
  }, [fleet, operationType]);

  if (loading) {
    return (
      <PageShell title="Fleet Configuration" description="Loading…">
        <p className="text-xs text-neutral-500">Loading…</p>
      </PageShell>
    );
  }

  if (!mission) {
    return (
      <PageShell title="Fleet Configuration" description="Mission not found">
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
      title={`Fleet Configuration — ${mission.name}`}
      description="Select and configure the operational fleet for this Mission Definition (no allocation or planning here)"
      actions={
        <div className="flex items-center gap-2">
          {savedAt && <span className="text-[11px] text-neutral-500">Saved</span>}
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || !live}
            className="rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save fleet"}
          </button>
          <Link
            href={`/missions/${missionId}`}
            className="inline-flex items-center gap-1 rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800"
          >
            <ArrowLeft className="h-3 w-3" /> Designer
          </Link>
        </div>
      }
    >
      {!live && (
        <div className="mb-4 rounded-md border border-amber-900/50 bg-amber-950/20 px-3 py-2 text-xs text-amber-400">
          Live API mode is disabled — changes cannot be saved. Set
          NEXT_PUBLIC_TWIN_API_URL to enable persistence.
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          {/* 1. Fleet selection */}
          <Section title="Fleet Selection">
            <p className="text-[11px] text-neutral-500">
              Add available assets from the inventory. Specifications are
              read-only; this screen never allocates drones or optimizes fleet
              composition.
            </p>
            {inventory && inventory.drone_models.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {inventory.drone_models.map((m) => (
                  <button
                    key={m.model}
                    type="button"
                    onClick={() => addDrone(m)}
                    className="inline-flex items-center gap-1 rounded-md border border-neutral-700 px-2 py-1 text-[11px] text-neutral-300 hover:bg-neutral-800"
                    title={`${m.vendor} · ${m.liquid_capacity_l} L · ${m.payload_capacity_kg ?? "?"} kg`}
                  >
                    <Plus className="h-3 w-3" /> {m.model}
                  </button>
                ))}
              </div>
            )}
            {fleet.length === 0 ? (
              <p className="text-[11px] text-neutral-500">
                No drones selected yet.
              </p>
            ) : (
              <div className="space-y-4">
                {fleet.map((f, i) => (
                  <DroneCard
                    key={`${f.model}-${i}`}
                    item={f}
                    model={modelFor(inventory, f.model)}
                    operationType={operationType}
                    productOptions={productOptions}
                    onRemove={() => removeDrone(i)}
                    onPatch={(patch) => patchDrone(i, patch)}
                    onToggle={(key, value) => toggleInList(i, key, value)}
                    onAssignTank={(tankId, productId) =>
                      assignTankProduct(i, tankId, productId)
                    }
                  />
                ))}
              </div>
            )}
          </Section>
        </div>

        {/* Right column: live fleet summary */}
        <div className="space-y-6">
          <Section title="Fleet Summary">
            <p className="text-[11px] text-neutral-500">
              Informational totals from read-only catalog specs. Feasibility,
              consumption and allocation are computed by the Planning Core.
            </p>
            <SummaryRow label="Selected drones" value={String(summary.drones)} />
            <SummaryRow
              label="Total payload capacity"
              value={`${summary.totalPayloadKg.toFixed(1)} kg`}
            />
            <SummaryRow
              label="Total liquid capacity"
              value={`${summary.totalLiquidL.toFixed(1)} L`}
            />
            <SummaryRow
              label="Min endurance (limiting)"
              value={
                summary.minEnduranceMin != null
                  ? `${summary.minEnduranceMin} min`
                  : "—"
              }
            />
            <SummaryRow
              label="Selected equipment"
              value={summary.equipment.length ? summary.equipment.join(", ") : "—"}
            />
            <div className="mt-3 border-t border-neutral-800 pt-3">
              <div className="mb-2 text-[11px] uppercase tracking-wide text-neutral-500">
                Configuration completeness
              </div>
              <CheckRow
                ok={summary.drones > 0}
                label="At least one drone selected"
              />
              <CheckRow
                ok={summary.allSupportOp}
                label={`All drones support "${operationType || "operation"}"`}
              />
              {summary.productNeeded && (
                <CheckRow
                  ok={summary.anyProductAssigned}
                  label="At least one tank has a product assigned"
                />
              )}
              <div className="mt-2 flex items-center gap-2 text-xs">
                <span className="text-neutral-500">Fleet readiness</span>
                <span
                  className={`ml-auto rounded px-2 py-0.5 text-[10px] font-medium ${
                    summary.ready
                      ? "bg-emerald-950 text-emerald-400"
                      : "bg-neutral-800 text-neutral-400"
                  }`}
                >
                  {summary.ready ? "Ready" : "Incomplete"}
                </span>
              </div>
              <p className="mt-2 text-[10px] text-neutral-600">
                Completeness only — operational feasibility is decided by the
                Planning Core in Mission Review.
              </p>
            </div>
          </Section>
        </div>
      </div>
    </PageShell>
  );
}

// ---------------------------------------------------------------------------
// Per-drone configuration card
// ---------------------------------------------------------------------------

function DroneCard({
  item,
  model,
  operationType,
  productOptions,
  onRemove,
  onPatch,
  onToggle,
  onAssignTank,
}: {
  item: FleetItem;
  model: FleetModel | undefined;
  operationType: string;
  productOptions: readonly ProductOption[];
  onRemove: () => void;
  onPatch: (patch: Partial<FleetItem>) => void;
  onToggle: (key: "equipment" | "sensors", value: string) => void;
  onAssignTank: (tankId: string, productId: string) => void;
}) {
  const supportsOp =
    (item.supported_operations ?? []).length === 0 ||
    (item.supported_operations ?? []).includes(operationType);
  const cameraOptions = ["", ...(model?.camera_packages ?? [])];
  const sprayerOptions = ["", ...(model?.sprayer_configs ?? [])];
  const spreaderOptions = [
    "",
    ...(model?.equipment ?? []).filter((e) =>
      /spread|cast|granular/i.test(e)
    ),
  ];

  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950 p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-sm text-neutral-200">{item.model}</span>
        <span className="text-[10px] text-neutral-600">{item.vendor}</span>
        {item.status && (
          <span className="rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] text-emerald-400">
            {item.status}
          </span>
        )}
        {!supportsOp && (
          <span
            className="rounded bg-amber-950 px-1.5 py-0.5 text-[10px] text-amber-400"
            title={`Model does not list "${operationType}"`}
          >
            operation unsupported
          </span>
        )}
        <button
          type="button"
          onClick={onRemove}
          className="ml-auto text-neutral-500 hover:text-red-400"
          aria-label={`Remove ${item.model}`}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Read-only catalog specs */}
      <div className="mb-3 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[10px] text-neutral-500 sm:grid-cols-3">
        <span>{item.liquid_capacity_l} L tank</span>
        <span>{item.battery_capacity_mah} mAh</span>
        {item.payload_capacity_kg != null && (
          <span>{item.payload_capacity_kg} kg payload</span>
        )}
        {item.estimated_flight_time_min != null && (
          <span>~{item.estimated_flight_time_min} min</span>
        )}
        {item.working_width_m != null && <span>{item.working_width_m} m width</span>}
        {(item.supported_operations ?? []).length > 0 && (
          <span className="col-span-2 sm:col-span-3">
            ops: {(item.supported_operations ?? []).join(", ")}
          </span>
        )}
      </div>

      {/* Equipment configuration */}
      <div className="space-y-2">
        <ConfigLabel>Equipment</ConfigLabel>
        {(model?.equipment ?? []).length === 0 ? (
          <p className="text-[10px] text-neutral-600">
            No equipment options for this model.
          </p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {(model?.equipment ?? []).map((e) => {
              const on = (item.equipment ?? []).includes(e);
              return (
                <Chip key={e} on={on} onClick={() => onToggle("equipment", e)}>
                  {e}
                </Chip>
              );
            })}
          </div>
        )}

        <ConfigLabel>Sensor package</ConfigLabel>
        <div className="flex flex-wrap gap-1.5">
          {(model?.sensors ?? item.sensors ?? []).map((s) => {
            const on = (item.sensors ?? []).includes(s);
            return (
              <Chip key={s} on={on} onClick={() => onToggle("sensors", s)}>
                {s}
              </Chip>
            );
          })}
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <div>
            <ConfigLabel>Camera package</ConfigLabel>
            <SmallSelect
              value={item.camera_package ?? ""}
              options={cameraOptions}
              onChange={(v) => onPatch({ camera_package: v || null })}
            />
          </div>
          <div>
            <ConfigLabel>Sprayer configuration</ConfigLabel>
            <SmallSelect
              value={item.sprayer_config ?? ""}
              options={sprayerOptions}
              onChange={(v) => onPatch({ sprayer_config: v || null })}
            />
          </div>
          <div>
            <ConfigLabel>Granular spreader</ConfigLabel>
            <SmallSelect
              value={item.granular_spreader ?? ""}
              options={spreaderOptions}
              onChange={(v) => onPatch({ granular_spreader: v || null })}
            />
          </div>
        </div>

        {/* Tank / product assignment */}
        <ConfigLabel>Tank &amp; product assignment</ConfigLabel>
        {(item.tanks ?? []).length === 0 ? (
          <p className="text-[10px] text-neutral-600">
            This model advertises no tanks.
          </p>
        ) : (
          <div className="space-y-1.5">
            {(item.tanks ?? []).map((t) => (
              <div
                key={t.tank_id}
                className="flex items-center gap-2 rounded border border-neutral-800 px-2 py-1"
              >
                <span className="text-[11px] text-neutral-300">
                  {t.label || t.tank_id}
                </span>
                <span className="font-mono text-[10px] text-neutral-600">
                  {t.capacity_l != null ? `${t.capacity_l} L` : "—"}
                </span>
                <div className="ml-auto w-40">
                  <SmallSelect
                    value={t.product_id ?? ""}
                    options={["", ...productOptions.map((p) => p.product_id)]}
                    labels={{
                      "": "— empty —",
                      ...Object.fromEntries(
                        productOptions.map((p) => [p.product_id, p.name])
                      ),
                    }}
                    onChange={(v) => onAssignTank(t.tank_id, v)}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
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

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 text-xs">
      <span className="text-neutral-500">{label}</span>
      <span className="text-right text-neutral-200">{value}</span>
    </div>
  );
}

function CheckRow({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-neutral-300">
      {ok ? (
        <Check className="h-3.5 w-3.5 text-emerald-500" />
      ) : (
        <X className="h-3.5 w-3.5 text-red-500" />
      )}
      <span>{label}</span>
    </div>
  );
}

function ConfigLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] uppercase tracking-wide text-neutral-500">
      {children}
    </div>
  );
}

function Chip({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-2 py-0.5 text-[10px] ${
        on
          ? "border-blue-700 bg-blue-950 text-blue-300"
          : "border-neutral-700 text-neutral-400 hover:bg-neutral-800"
      }`}
    >
      {children}
    </button>
  );
}

function SmallSelect({
  value,
  options,
  labels,
  onChange,
}: {
  value: string;
  options: readonly string[];
  labels?: Record<string, string>;
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] text-neutral-200 outline-none focus:border-blue-600"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {labels?.[o] ?? (o === "" ? "—" : o)}
        </option>
      ))}
    </select>
  );
}
