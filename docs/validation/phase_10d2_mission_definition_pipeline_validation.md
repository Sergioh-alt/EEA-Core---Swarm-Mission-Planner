# Phase 10D.2 — Mission Definition Pipeline — Validation Report

## Scope

Backend foundation for the **Mission Definition Pipeline** — the central
design-time contract bridging the user planning experience and Digital Twin
execution:

```
Mission Definition → Planning Core → Mission Package → Digital Twin → Mission Control
```

Delivered:

- Mission Definition + Mission Package data models (the contract).
- Replaceable persistence (SQLite + in-memory) for fields and mission definitions.
- Planning Core integration wrapping the existing `core/` chain (no new algorithms).
- Fleet inventory (available assets, read-only).
- REST API contract mounted on the existing Digital Twin server.
- Frontend TypeScript contract (`orion-ui/src/contracts/mission.ts`, types only).

No frontend planning screens (10D.3+), no Mission Control redesign, no runtime
changes to the Digital Twin.

## API Contract

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/fleet/inventory` | Available drones, products, supported crops |
| GET / POST | `/api/fields` | List / create field records |
| GET / PUT / DELETE | `/api/fields/{field_id}` | Read / update / delete a field |
| GET / POST | `/api/missions` | List / create mission definitions |
| GET / PUT / DELETE | `/api/missions/{mission_id}` | Read / update (version++) / delete |
| POST | `/api/planning/compute` | Definition (inline or `{mission_id}`) → Mission Package |
| POST | `/api/missions/{mission_id}/package` | Stored definition → Mission Package |

**Input** (Mission Definition): field information + preparation data (name,
crop, boundary points, zones, obstacles), operation parameters, environment,
fleet selection, products/resources.

**Processing**: `Mission Definition → Planning Core (core/) → Mission Package`.

**Output** (Mission Package): generated routes, resource requirements, mission
timeline, risk/recommendation, validation, and an execution package
(field polygon + per-drone routes in metric space) for the Digital Twin.

## Persistence

- `DefinitionStore` abstract interface — the pipeline/API depend on nothing else.
- `SQLiteDefinitionStore` — demonstration store; JSON blobs keyed by id, so the
  contract (not the table shape) is authoritative. Default DB `data/mission_pipeline.db`
  (git-ignored); override with `ORION_DEFINITION_DB`, or `""` for in-memory.
- `InMemoryDefinitionStore` — tests / ephemeral usage.
- Replaceable for commercial infrastructure in Phase 11 with no contract change.

## Validation

| Check | Result |
|-------|--------|
| New pipeline tests (`tests/test_mission_pipeline.py`) | **14 passed** |
| Full Python regression (`pytest`) | **872 passed** |
| HAL boundary + architecture validation suites | 80 passed |
| Forbidden-import scan (pipeline → hive/hal/px4/mavlink/ros2/simulation/digital_twin/runtime) | **0 matches** |
| TypeScript `tsc --noEmit` | clean |
| ESLint (`next lint`) | 0 warnings/errors |
| Next.js production build | 13/13 routes |
| App builds with pipeline router mounted | 7 new endpoints present |

## Boundary Compliance

- The pipeline imports **only** the existing Planning Core (`core/`), `config`,
  and `backend.serializers`. It does **not** import Hive, HAL, PX4, MAVLink,
  ROS2, Simulation Core, the Digital Twin, or the Twin runtime.
- It contains **no** planning, optimization, allocation, or decision algorithms —
  those remain in `core/`. It only orchestrates and serializes.
- It **never** mutates Digital Twin runtime state (asserted by
  `test_pipeline_does_not_touch_runtime`): computing/persisting definitions
  leaves `mission_status` unchanged.
- The Mission Definition / Mission Package are design-time artifacts owned by
  the pipeline; the Digital Twin remains the sole runtime source of truth.

## Mission Control Integrity

The existing Digital Twin REST/WebSocket endpoints, runtime, and Mission Control
UI are unchanged. The pipeline is additive: the hardcoded demonstration route
still drives the live simulation when no Mission Definition is deployed.
Definition-driven runtime deployment is deferred to 10D.6 (with approval).

## Known Limitations

- The current Planning Core assumes a homogeneous fleet; a heterogeneous
  selection uses conservative representative capacities (min battery/tank).
  True per-drone heterogeneity is 10D.5.
- `operation.flight_altitude_m` is stored and returned in the execution package,
  but the core still derives altitude from the crop profile.
- Execution routes are in local metric coordinates; georeferencing onto the live
  map (definition-driven runtime) is 10D.6.
- No authentication/multi-tenancy (Phase 11).
