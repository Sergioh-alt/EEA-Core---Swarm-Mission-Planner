# Phase 10D.5 — Fleet Configuration: Implementation Report

## Objective

Complete the **Fleet Configuration** stage of the Mission Definition Pipeline:
enrich a Mission Definition with the full operational fleet configuration
(selection, equipment, tanks, product assignment) before deployment. The stage
collects and configures available assets only — it performs **no allocation,
resource balancing, optimization, scheduling, or routing**, and never contacts
the Digital Twin runtime. Feasibility remains the Planning Core's job.

This phase is **fully additive**. No architecture changes; no existing behavior
removed. Mission Control and the Mission Designer remain intact.

## Pipeline stage

```
Mission Definition → [Fleet Configuration] → Planning Core → Mission Package
```

## Precondition verification — "Definition valid = NO" semantics

During 10D.4 validation the Mission Package reported `Go/No-Go = GO`,
`Feasible = YES`, `Confidence = 96%` but `Definition valid = NO`. Investigation:

- The test field's crop was `grapes`, which is **not** a key in
  `config/settings.py::CROP_PROFILES`.
- `core/mission_intake.py::create_mission_profile` **gracefully falls back** to
  the `generic` crop profile for unknown crops (`CROP_PROFILES.get(crop,
  CROP_PROFILES["generic"])`) and produces a complete, plannable profile.
- Yet `utils/validators.py::validate_mission_inputs` classified an unknown crop
  as a hard **error**, forcing `ValidationResult.valid = False`.
- The decision engine (`core/decision_engine.py`) does **not** consume
  `validation.valid`; Go/No-Go is computed independently from weather, risk and
  coverage. So the "not valid" flag never blocked the mission — it only
  contradicted the GO recommendation on the same card.

**Determination:** inconsistent with intended semantics. The system treats an
unknown crop as non-blocking (generic fallback), so it must be a **warning**,
not an error. `valid` is defined to reflect only *blocking* conditions.

**Correction (inside the Planning Core, no architecture change):**

- `utils/validators.py`: unknown crop type now appends to `warnings` (with the
  generic-fallback explanation) instead of `errors`. `ValidationResult` gained a
  docstring stating `valid` reflects blocking conditions only.
- Regression test `tests/test_mission_designer.py::
  test_unknown_crop_is_non_blocking_warning_not_invalid` asserts
  `valid == True`, a `grapes` warning is present, and `feasible == True` — i.e.
  no contradiction.
- UI (`/missions/[missionId]`): the Mission Package card now lists the actual
  validation **warnings** (amber) and **errors** (red), instead of only a count,
  so the operator sees *why* rather than a bare "no".

Truly blocking inputs (non-positive field size, zero drones, impossible wind,
out-of-range temperature) remain errors and still drive `valid = False`.

## Contract extensions (additive, backward-compatible)

All new fields are optional with defaults, so 10D.2–10D.4 payloads deserialize
unchanged (covered by `test_legacy_fleet_without_config_still_parses`).

### `FleetItem` (`backend/mission_pipeline/models.py`)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `status` | `Optional[str]` | `None` | Catalog status echo (e.g. "available") |
| `payload_capacity_kg` | `Optional[float]` | `None` | Read-only spec |
| `estimated_flight_time_min` | `Optional[float]` | `None` | Read-only spec |
| `supported_operations` | `list[str]` | `[]` | Read-only spec |
| `sensors` | `list[str]` | `[]` | Installed sensor package |
| `equipment` | `list[str]` | `[]` | Installed equipment |
| `camera_package` | `Optional[str]` | `None` | Selected camera package |
| `sprayer_config` | `Optional[str]` | `None` | Selected sprayer configuration |
| `granular_spreader` | `Optional[str]` | `None` | Future-compatible spreader |
| `tanks` | `list[TankConfig]` | `[]` | Per-tank product assignment |

### `TankConfig` (new)

`tank_id`, `label`, `capacity_l?`, `product_id?`, `product_name?` — an operator
tank→product **assignment intent**. No consumption is computed here.

The TypeScript contract (`orion-ui/src/contracts/mission.ts`) mirrors these
additively (`FleetItem` enrichment, new `TankConfig`, enriched `FleetModel` +
`FleetModelTank` for the read-only inventory catalog).

The Planning Core (`planning_core.py`) is **unchanged** and ignores the new
fields — it still derives conservative representative capacities from the
selected fleet. Verified by `test_configured_fleet_does_not_break_planning_core`.

## Read-only fleet inventory (`backend/mission_pipeline/fleet_inventory.py`)

Each drone model now advertises catalog specs: `status`, `payload_capacity_kg`,
`estimated_flight_time_min`, `tanks` (id/label/capacity), `supported_operations`,
`sensors`, `equipment`, `camera_packages`, `sprayer_configs`. A third-party
heterogeneous example **`XAG-P100`** was added alongside `ORION-Std`,
`ORION-Heavy`, and `DJI-Agras-T40`. This is inventory, not allocation.

## Frontend — `/missions/[missionId]/fleet` (new workspace)

- **Fleet Selection**: add any mix of available models (heterogeneous fleets
  supported); read-only specs shown per drone.
- **Equipment Configuration** (per drone): equipment multi-select, sensor
  package multi-select, camera package, sprayer configuration, granular spreader
  (future-compatible), all sourced from the model's advertised options.
- **Tank & Product Assignment** (per drone): assign a mission/catalog product to
  each advertised tank; tank capacity displayed (static catalog value).
- **Fleet Summary** (informational): drone count, total payload capacity, total
  liquid capacity, limiting (min) endurance, selected equipment, and a
  **configuration-completeness** readiness indicator — explicitly *not* a
  feasibility verdict.
- The Mission Designer's Fleet Selection section links to this workspace and its
  "add drone" now seeds catalog specs + tanks into the definition.

## Boundary preservation

- The workspace only reads mission + inventory and writes an enriched
  `MissionDefinition` via the design-time REST API (`updateMission`).
- It never imports or calls the Digital Twin runtime client.
- Fleet Summary values are simple sums/min of **static catalog specs** and a
  completeness check — no consumption/required-capacity is computed in the UI.
  Consumption, required capacity and feasibility are deliberately **deferred to
  the Planning Core** (surfaced in the Mission Package / Mission Review), to
  respect the "no resource balancing in the frontend" rule.
- `drone_id` values are sequential selection slots, not runtime allocations.
- Forbidden-import scan on `backend/mission_pipeline/`: **0**.

### Deviation note (intentional)

The 10D.5 scope lists "Required capacity" and "Estimated consumption" under the
Fleet Summary display. Computing those in the frontend would require
rate × area resource math, which the architecture rules forbid ("no resource
balancing / allocation / planning in the frontend; the Planning Core validates
feasibility"). We therefore surface only static catalog capacities and the
assigned product, and defer required-capacity/consumption to the Planning Core.
This honors the stronger, repeated architectural constraint.

## Files changed

- `utils/validators.py` — unknown crop reclassified error → warning; docstring.
- `backend/mission_pipeline/models.py` — `TankConfig` + `FleetItem` enrichment,
  (de)serialization, `_str_list`/`_tank_from_json` helpers.
- `backend/mission_pipeline/fleet_inventory.py` — enriched catalog + XAG-P100.
- `backend/mission_pipeline/__init__.py` — export `TankConfig`.
- `orion-ui/src/contracts/mission.ts` — `TankConfig`, enriched `FleetItem`,
  `FleetModel` + `FleetModelTank`.
- `orion-ui/src/app/missions/[missionId]/fleet/page.tsx` — Fleet Configuration
  workspace (new).
- `orion-ui/src/app/missions/[missionId]/page.tsx` — Fleet Configuration link;
  `addDrone` seeds catalog specs/tanks; Mission Package card lists warnings/errors.
- `tests/test_fleet_configuration.py` — 6 focused tests (new).
- `tests/test_mission_designer.py` — +1 validation-consistency test.
- `docs/guides/user_workflow.md` — Fleet Configuration workflow section.
