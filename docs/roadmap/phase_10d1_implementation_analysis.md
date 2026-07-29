# ORION Phase 10D.1 — Architectural Analysis & Implementation Proposal

**Type:** Analysis + implementation proposal (no code, no architecture changes)
**Status:** Draft for approval — implementation (10D.2+) awaits explicit sign-off
**Inputs:** `docs/architecture/ORION Phase 10D Architecture Specification`,
`docs/architecture/ORION Phase 10D Boundary Specification`,
`docs/roadmap/ORION Phase 10D Roadmap`,
`docs/roadmap/ORION Operational Workflow Specification`
**Method:** Static inspection of the current repository (backend `core/`,
`backend/`, `digital_twin/`, `simulation/`; frontend `orion-ui/`) mapped against
the Phase 10D documents.

---

## 1. Executive summary

Phase 10D adds the **Mission Planning experience that precedes Mission Control**:
Field Acquisition → Field Preparation → Mission Planning → Fleet Configuration →
Mission Review → Deployment → (existing) Mission Control → Replay/Analytics →
Mission Library. Everything already built (Mission Control, Digital Twin, thin
FastAPI transport, Simulation Core, the `core/` planning pipeline) stays and
keeps working; 10D **extends** the front of the workflow.

The single most important finding:

> **The planning intelligence Phase 10D needs already exists in `core/`** —
> `mission_intake`, `environment_analyzer`, `swarm_planner`, `route_planner`,
> `resource_planner`, `risk_engine`, `decision_engine`, `mission_timeline`,
> `fleet_manager`. It is currently exercised only by the **Streamlit** app
> (`app.py`), **not** by the Next.js/FastAPI runtime. The live Digital Twin
> runtime (`backend/twin_runtime.py`) instead uses a **hardcoded demonstration
> route** (`_planned_route()` / `_field_polygon()`).

Therefore Phase 10D is primarily an **integration + presentation** effort, not a
new-algorithm effort:

1. **Backend (thin, no new decision logic):** expose the *existing* `core/`
   planning pipeline and add **mission-definition persistence** behind new
   read/compute/persist REST endpoints, and let the Twin runtime consume a
   selected mission definition instead of the hardcoded route.
2. **Frontend:** build the new planning screens (currently `/planning` is a
   static placeholder) that collect operator input and *submit* definitions/
   intents — never planning locally.
3. **Persistence:** introduce a mission/field/template/schedule store (none
   exists today).

Boundaries are preserved throughout: the UI collects input and submits;
`core/` + Hive + Digital Twin do all planning, orchestration, and runtime.

---

## 2. Current-state inventory (what exists today)

### 2.1 Backend planning pipeline — `core/` (EXISTS, reusable)

| Module | Role for 10D | Reuse |
|--------|--------------|-------|
| `mission_intake.py` (`MissionProfile`, `create_mission_profile`) | Mission definition + input validation | **Direct reuse** |
| `geometry.py` (`FieldGeometry.from_points`, `from_hectares`, MABR, orientation) | Field polygon from **user-drawn vertices** already supported | **Direct reuse** |
| `environment_analyzer.py` (`analyze_environment`) | Wind/effective spray width/speed assessment | **Direct reuse** |
| `swarm_planner.py` (`plan_swarm`, strip partition) | Sector partitioning | **Direct reuse** |
| `route_planner.py` (`plan_routes` → `RoutePlan`/`DroneRoute`/`Waypoint`) | Coverage route generation | **Direct reuse** |
| `resource_planner.py` (`plan_resources`) | Battery/liquid resource estimates | **Direct reuse** |
| `risk_engine.py` (`evaluate_risks`) | Mission warnings | **Direct reuse** |
| `decision_engine.py` (`generate_recommendation`) | Go/No-Go summary | **Direct reuse** |
| `mission_timeline.py` (`generate_timeline`) | Duration/coverage estimation | **Direct reuse** |
| `fleet_manager.py`, `resource_system.py`, `swarm_optimizer.py`, `reallocation_engine.py`, `hive.py`, `mission_orchestrator.py` | Fleet inventory, orchestration | **Reuse (read for Fleet Config / estimates)** |

`app.py` already chains them:
`create_mission_profile → analyze_environment → plan_swarm → plan_routes →
plan_resources → evaluate_risks → generate_recommendation → generate_timeline`.
This is the exact chain the new backend planning endpoint should call.

### 2.2 Digital Twin + transport (EXISTS)

- `digital_twin/` — snapshot, replay, sync, state models, twin API (unchanged).
- `backend/twin_server.py` — FastAPI app; endpoints today:
  `/api/health`, `/api/twin/state|drone|snapshots|replay|analytics`,
  `/api/mission/geometry|status`, `/api/alerts`, `POST /api/intents`, `WS /ws/twin`.
- `backend/twin_runtime.py` — drives the sim; **uses a hardcoded route**
  (`_planned_route`, `_field_polygon`) — the key seam to make definition-driven.
- `simulation/` — `sim_core`, `mavlink_bridge`, `ros2_swarm_bus`,
  `failure_injection` (unchanged).

### 2.3 Frontend — `orion-ui/` (from the functional audit, `docs/audits/ui_functional_audit.md`)

- **Reusable unchanged:** Mission Control `/control`, `/map` (MapView + 7 layers,
  incl. user-drawable groundwork via Mapbox), `/fleet`, `/analytics`,
  `/mission/replay`, `/alerts`, stores (`swarm/drone/mission/alert/replay/
  connection`), `restClient`, `wsClient`, `ConnectionProvider`, error/loading
  boundaries.
- **Placeholder to be replaced:** `/planning` (static "Interactive planning not
  enabled"), `/deployment` (has START intent; needs to consume a real package),
  `/mission` inert buttons, `/settings` (display-only), `/fleet/{id}` charts.
- **No** Next.js API routes (UI → FastAPI only) — good; keeps the boundary.

### 2.4 Persistence — **DOES NOT EXIST**

No database, ORM, or file-backed mission store anywhere in `backend/`, `core/`,
`digital_twin/`. All state is in-memory/runtime. Mission definitions, fields,
templates, and schedules (10D core artifacts) have **no home today**.

---

## 3. Compatibility matrix (Phase 10D module → current repo)

| 10D module | Backend support | Frontend support | Verdict |
|------------|-----------------|------------------|---------|
| Mission Creation | `MissionProfile` exists; **no persistence** | none (placeholder) | Partial — needs store + UI |
| Environment Builder | `FieldGeometry.from_points` accepts drawn polygons; no obstacle/zone model | none | Partial — needs env model + drawing UI |
| Mission Designer | full planner chain exists (manual/assisted/auto map to existing params) | none | Partial — needs request API + UI |
| Fleet Configuration | `fleet_manager`/`resource_system` exist | `/fleet` read-only view | Partial — needs inventory API + selection UI |
| Mission Library | none | none | Missing — new store + UI |
| Mission Scheduler | none | none | Missing — new store + UI (stores plan only) |
| Deployment Review | planner produces estimates; `POST /api/intents` exists | `/deployment` checklist + START | Partial — needs package summary API + UI |
| Mission Control | complete | complete | **Reuse as-is** |
| Replay / Analytics / History | complete (analytics/replay endpoints) | complete | **Reuse as-is** |

---

## 4. Gap analysis

### 4.1 Missing backend modules
1. **Mission Planning API** (`backend/planning_server.py` or a router mounted on
   the existing app): thin endpoints that call the `core/` chain and return
   plan/estimates/warnings. **No new algorithms** — serialization + orchestration
   of existing functions only.
   - `POST /api/planning/compute` → run planner chain on a definition, return
     routes + coverage + duration + resource + risk (read-compute, no persist).
   - `GET /api/fleet/inventory` → available drones/stations/payloads/products.
2. **Persistence layer** (`backend/store/`): mission definitions, fields,
   environment models, templates, schedules. Recommend SQLite + a thin
   repository module (respect "no database redesign" — additive, file-backed).
   - `POST/GET/PUT/DELETE /api/missions`, `/api/fields`, `/api/templates`,
     `/api/schedules`.
3. **Definition-driven Twin runtime**: extend `twin_runtime` so a deployed
   mission definition supplies geometry + routes (replacing hardcoded
   `_planned_route`/`_field_polygon`) via the existing command pipeline — **no**
   Twin state mutation from the UI; deployment still flows through `POST
   /api/intents` (+ a definition reference).
4. **Environment model** (`core/environment_model.py` or extend `geometry`):
   typed obstacles/exclusion/crop zones/infrastructure consumed by the planner.

### 4.2 Missing frontend modules/screens
- `/fields` (Field Acquisition: create/open, image upload) + field store.
- `/fields/[id]/prepare` (Environment Builder: draw boundary/zones/obstacles,
  layers, undo/redo) — Mapbox draw tooling.
- Replace `/planning` (Mission Designer: zones, planning mode, flight params,
  request compute, coverage preview).
- `/fleet/configure` (Fleet Configuration: select drones/payloads/products).
- Rework `/deployment` into Mission Review (summary, estimates, warnings, deploy/
  save/schedule/export).
- `/library` (Mission Library) and `/schedule` (Scheduler, plan-storage only).
- New stores: `missionDefinitionStore`, `fieldStore`, `environmentStore`,
  `fleetConfigStore`, `libraryStore`, `scheduleStore`.
- New REST client methods for all endpoints in §4.1.

### 4.3 Missing workflow transitions
Field → Prepare → Plan → Fleet → Review → Deploy → Control → Replay/Analytics →
Library. Today only Deploy → Control → Replay/Analytics exists. Needs a guided
left-to-right flow + navigation (breadcrumbs/stepper — none today).

### 4.4 Missing persistence
Everything editable (fields, missions, templates, schedules) — see §4.1.2.

### 4.5 Missing simulation capabilities
- Twin runtime must accept **arbitrary field polygons + generated routes** from a
  deployed definition (today: single fixed geometry).
- Emergency Stop intent (roadmap 10D.6) — currently START/PAUSE/RESUME/STOP only.
- Heterogeneous fleet (ORION/DJI/mixed, per-drone working width) in the sim.

### 4.6 Missing validation logic
- Per-boundary forbidden-import scan for the **new** planning frontend (must not
  import Hive/HAL/Route Planner/etc. — Boundary Spec §Forbidden Dependencies).
- Mission-definition schema validation (reuse `state_validation`/`mission_intake`
  validators server-side; UI only surfaces results).

### 4.7 Missing documentation
- Per-sub-phase validation reports under `docs/validation/`.
- API contract doc for the new planning/persistence endpoints.
- Updated user workflow + demo guide covering the full 10D flow.

---

## 5. Recommended implementation subdivision

The roadmap numbers functional stages 10D.1–10D.7. To **minimize architectural
risk and maximize reuse**, I recommend sequencing by *dependency*, building the
backend seam first so every UI screen has a real endpoint to talk to. (Note: the
user's current task is the **analysis**, labeled 10D.1; the implementation
sub-phases below start at 10D.2, consistent with "wait for approval before
10D.2".)

> **Numbering update (authoritative).** Per the approved Phase 10D documentation
> clarification, 10D.2 is the **Mission Definition Pipeline** — it establishes the
> Mission Definition / Mission Package contract, not just backend endpoints.
> Sub-phases 10D.3–10D.7 only *enrich* that contract; they add no new execution
> path. Mission execution is not a separate build — Mission Review (10D.6) deploys
> the Mission Package to the existing Mission Control.

| Sub-phase | Scope | Depends on | Rationale |
|-----------|-------|------------|-----------|
| **10D.2 — Mission Definition Pipeline** | Mission Definition + Mission Package contract; SQLite persistence (replaceable repos) for fields + definitions; Planning Core integration (definition → existing `core/` chain → package); fleet inventory; `POST /api/planning/compute`, CRUD APIs. No UI. Full test coverage. | — | De-risks everything; formalizes the central contract using existing intelligence, no new algorithms. |
| **10D.3 — Field Acquisition** | Enriches the definition with field geometry, images, zones, obstacles, environmental info. `/fields` + preparation UI, drawing, layers, undo/redo. | 10D.2 | Produces geometry the planner consumes. |
| **10D.4 — Mission Designer** | Enriches with crop zones, operation type, route preferences, manual editing, automatic planning request. Replaces `/planning` placeholder; coverage preview + estimates. | 10D.2–3 | Turns field into executable definition. |
| **10D.5 — Fleet Configuration** | Enriches with available drones, capabilities, tank/product info, operational constraints. `/fleet/configure` from inventory. | 10D.2 | Completes the mission package. |
| **10D.6 — Mission Review** | Validates generated plan, resource requirements, estimated execution, Digital Twin deployment readiness; deploys Mission Package to the existing Mission Control; Emergency Stop. | 10D.2–5 | Bridges planning → existing Mission Control. |
| **10D.7 — Mission Library** | Mission storage, reusable templates, scheduling metadata (plan storage only), historical reference; duplicate/version/import/export/archive/search. | 10D.2 | Reuse loop; scheduling stores plans only (execution = Phase 11). |
| **10D.8 — Integration validation + docs** | End-to-end walkthrough, boundary/forbidden-import scans, regression, validation reports, demo guide. | all | Final demonstration sign-off. |

Each sub-phase ships behind the existing boundary checks and leaves prior work
untouched and functional.

---

## 6. Architecture impact & boundary verification

- **No responsibility moves to the UI.** New screens only *collect input* and
  *submit* (definitions + intents). All planning stays in `core/`; orchestration
  in Hive; runtime in the Digital Twin.
- **Communication chain preserved:** Mission Planning → Intent/Definition API →
  Backend (`core/`) → Hive → Simulation → Digital Twin → REST/WS → Mission
  Control. No module bypasses it; UI never imports Hive/HAL/PX4/MAVLink/ROS2 or
  the planners.
- **Single source of truth intact:** editable *definitions* are owned by the new
  persistence layer (design-time); *runtime* state remains owned solely by the
  Digital Twin. No duplicated runtime truth.
- **Additive only:** no redesign of existing modules; hardcoded demo route
  becomes one code path among definition-driven routes (existing demo keeps
  working if no definition is deployed).

## 7. Dependency analysis (build order risks)
- Persistence + planning API (10D.2) is the critical path — everything else
  depends on it; build and fully test first.
- Field geometry (`from_points`) already supports drawn polygons → low risk for
  10D.3's core data path; risk is concentrated in Mapbox drawing UX.
- Twin runtime change (10D.6) is the highest-risk seam (touches the live demo);
  gate it behind a definition reference so the existing fixed-route demo is a
  fallback.

## 8. Explicit non-goals (per roadmap "Out of Scope")
No hardware/PX4/HAL/Hive/optimizer/Decision-Engine changes, no commercial auth,
no cloud sync, no database *redesign*, no production scalability work. Phase 11
begins only after 10D validation.

---

## 9. Deliverables of this analysis
- Architecture impact analysis (§6), boundary verification (§6), dependency
  analysis (§7), module reuse analysis (§2–3), gap analysis (§4), recommended
  roadmap (§5).
- **No code, no architecture modification** — proposal only. Awaiting explicit
  approval before beginning Phase 10D.2.
