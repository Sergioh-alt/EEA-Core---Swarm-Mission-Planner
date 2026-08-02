# Phase 10D.4 — Mission Designer: Implementation Report

## Objective

Build the complete Mission Designer interface that transforms a prepared field
into a complete **Mission Definition**, then submits it to the existing Planning
Core (10D.2). The Designer collects parameters and constructs the definition
only — it performs no planning, routing, optimization, allocation, scheduling,
or decision-making, and never contacts the Digital Twin.

This phase is **fully additive**. No architecture changes, no removal of
existing behavior. Mission Control is untouched.

## Pipeline stage

```
Field → Preparation → [Mission Designer] → Mission Definition → Planning Core
      → Mission Package → Mission Library → Digital Twin → Mission Control
```

The Mission Designer owns exactly the highlighted stage and never bypasses the
Mission Definition contract.

## Contract extensions (additive, backward-compatible)

All new fields are optional with defaults, so 10D.2/10D.3 payloads deserialize
unchanged (covered by `test_mission_definition_backward_compatible_defaults`).

### `MissionDefinition` (`backend/mission_pipeline/models.py`)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `field_id` | `str` | `""` | Source prepared field (traceability) |
| `priority` | `str` | `"normal"` | Execution priority (captured only) |
| `scheduled_date` | `str` | `""` | Operator estimate (ISO date) — not a schedule |
| `notes` | `str` | `""` | Optional mission notes |

### `OperationParams` — operator preferences (hints only)

| Field | Type | Default |
|-------|------|---------|
| `nominal_speed_ms` | `Optional[float]` | `None` |
| `overlap_pct` | `Optional[float]` | `None` |
| `safety_margin_m` | `Optional[float]` | `None` |
| `coverage_direction` | `str` | `"auto"` |
| `route_preference` | `str` | `"balanced"` |

### `ProductSelection` — application details (captured, not allocated)

| Field | Type | Default |
|-------|------|---------|
| `tank` | `Optional[str]` | `None` |
| `concentration_pct` | `Optional[float]` | `None` |
| `dilution` | `Optional[str]` | `None` |
| `safety_notes` | `str` | `""` |

The TypeScript contract (`orion-ui/src/contracts/mission.ts`) mirrors these
additively (all optional), plus a typed `FleetModel` for the read-only Fleet
Inventory `drone_models`.

The Planning Core (`planning_core.py`) is **unchanged** and simply ignores the
new preference fields — verified by
`test_designer_fields_do_not_break_planning_core`.

## Frontend

- **Pipeline client** (`pipelineClient.ts`): added `listMissions`, `getMission`,
  `createMission`, `updateMission`, `deleteMission`, and `computePlanning`
  (design-time REST only; never the runtime WebSocket client).
- **`/missions`** — mission list + create (pick a prepared field, name it).
- **`/missions/[missionId]`** — the Mission Designer, with sections:
  1. Mission Information (name, description, priority, date, notes)
  2. Zone Selection (read-only `FieldCanvas` render + include/exclude toggles,
     "Select entire field")
  3. Agricultural Operation (spraying / fertilization / seeding / mapping /
     inspection / custom)
  4. Product Configuration (add from catalog; rate, tank, concentration,
     dilution, safety notes; multiple products; remove)
  5. Operational Parameters (altitude, speed, overlap, safety margin, coverage
     direction, route preference, planning mode, drones requested)
  6. Fleet Selection (add available assets from Fleet Inventory; read-only
     specs; remove)
  7. Completeness checklist (interface completeness only)
  8. Mission Definition preview
  9. Submit to Planning Core → read-only Mission Package result
- **Sidebar**: added a **Missions** nav entry (additive; `/planning` and
  Mission Control left intact).

## Boundary preservation

- The Designer only reads field/fleet inventory and writes a `MissionDefinition`
  via the design-time REST API.
- It never imports or calls the Digital Twin runtime client; the read-only
  Mission Package is produced entirely by the existing Planning Core.
- Zone participation reuses the existing `Zone.enabled` flag; the prepared field
  is never mutated by the mission workflow.
- Fleet `drone_id` values are sequential selection slots, not runtime
  allocations.
- Forbidden-import scan on `backend/mission_pipeline/`: **0**.

## Files changed

- `backend/mission_pipeline/models.py` — additive contract fields + (de)serialization.
- `orion-ui/src/contracts/mission.ts` — mirrored additive types + `FleetModel`.
- `orion-ui/src/lib/pipelineClient.ts` — mission CRUD + `computePlanning`.
- `orion-ui/src/app/missions/page.tsx` — mission list + create (new).
- `orion-ui/src/app/missions/[missionId]/page.tsx` — Mission Designer (new).
- `orion-ui/src/components/layout/Sidebar.tsx` — Missions nav entry.
- `tests/test_mission_designer.py` — 7 focused tests (new).
- `docs/guides/user_workflow.md` — Mission Designer workflow section.
