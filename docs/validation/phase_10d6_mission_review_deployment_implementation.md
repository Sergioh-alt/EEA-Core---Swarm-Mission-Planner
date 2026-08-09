# Phase 10D.6 — Mission Review & Deployment (Implementation Report)

Mission Review is the operational gateway between the Mission Definition
Pipeline and the Digital Twin runtime. It verifies an **already completed**
Mission Package, collects operator confirmation, and — on explicit
authorization — transfers that package, unchanged, into the Twin.

```
Mission Definition → Planning Core → Mission Package → [Mission Review] → Digital Twin → Mission Control
```

No planning, optimization, allocation, scheduling or routing was introduced in
this phase, and deployment never starts execution.

---

## 1. Backend

### `backend/mission_pipeline/deployment.py` (new)

The deployment domain, deliberately free of any runtime import.

| Element | Responsibility |
| --- | --- |
| `DeploymentState` | `draft → ready_for_review → approved → deploying → deployed → executing → completed → archived` |
| `LOCKED_STATES` | `deployed`, `executing`, `completed`, `archived` — the package is immutable from `deployed` onward |
| `DEFAULT_CHECKLIST` | weather / area / products / fleet / batteries / parameters / safety perimeter |
| `DeploymentRecord` | per-mission review state: checklist, state, locked package, deployment id/time |
| `TwinDeploymentGateway` | `Protocol` with the single method `deploy_mission_package(package) -> receipt` |
| `deploy_mission(...)` | rejects locked missions and incomplete checklists, freezes a copy of the package, calls the gateway, stores the result |

`DeploymentRecord.confirm()` derives state from confirmations only:
no confirmations → `draft`; some → `ready_for_review`; all required →
`approved`. The checklist never touches Planning Core output.

The `Protocol` is the entire boundary: the pipeline holds no reference to the
Digital Twin, `backend/twin_server.py` injects the runtime as the gateway.

### `backend/mission_pipeline/persistence.py`

`DefinitionStore` gains `save_deployment` / `get_deployment` /
`delete_deployment`, implemented by both `SQLiteDefinitionStore` (new
`mission_deployments` table) and `InMemoryDefinitionStore`. Persistence stays
replaceable exactly as in 10D.2.

### `backend/mission_pipeline/api.py`

Three additive endpoints:

| Endpoint | Behavior |
| --- | --- |
| `GET /api/missions/{id}/review` | mission + package + deployment record + `deployment_available`. Returns the **locked** package once deployed, otherwise builds one through the Planning Core. Never contacts the runtime. |
| `PUT /api/missions/{id}/checklist` | `{"confirmations": {item_id: bool}}` → updated deployment record |
| `POST /api/missions/{id}/deploy` | builds the package from the stored definition, hands it to the gateway, persists the locked record. `503` when no gateway is attached. |

Locking is enforced at the API edge: `PUT /api/missions/{id}` and
`DELETE /api/missions/{id}` return `409` for a deployed mission, and the
package endpoints return the stored immutable package instead of recomputing.

### `backend/twin_runtime.py` / `backend/twin_server.py`

`TwinRuntime.deploy_mission_package()` implements the gateway protocol: it
stores the package verbatim, records a deployment id/time, emits a deployment
event and returns a receipt. It does **not** call `start_mission()` — the
mission still waits for an operator START intent in Mission Control.
`TwinRuntime.deployed_mission()` exposes it read-only via the new
`GET /api/twin/deployment`. The hard-coded demo route remains the fallback when
nothing is deployed, so the standing demo is unaffected.

---

## 2. Frontend

| File | Role |
| --- | --- |
| `contracts/mission.ts` | deployment/review types, ordered states + labels, new endpoint constants |
| `lib/pipelineClient.ts` | `getReview`, `updateChecklist`, `deployMission`, `getTwinDeployment` |
| `lib/missionPackageView.ts` | typed read-only views over the package (no `any`, no derived operational values) |
| `app/missions/[missionId]/review/page.tsx` | the Mission Review workspace |
| `components/review/MissionPreview.tsx` | read-only execution preview |
| `components/review/DeploymentStatus.tsx` | lifecycle visualization |
| `components/review/DeployedMissionBar.tsx` | deployed-package strip in Mission Control |

**Workspace** — mission, field, area, operation, zones, products, fleet, drone
count, duration, coverage, liquid usage, battery cycles/consumption, per-drone
resource consumption, timeline summary, route count, risk assessment,
confidence, recommendations and validation warnings. Every figure is read from
the Mission Package through `missionPackageView`; the UI performs no
operational arithmetic.

**Checklist** — each toggle `PUT`s a single confirmation; the Deploy button is
disabled until `checklist_complete` is true (and stays disabled once locked).

**Preview** — optional, collapsed by default. Draws the package's
`execution.field_polygon_m` and `execution.routes_m` (start markers, coverage
order, per-route sequence table joined with the package timeline). It issues no
requests at all — no `/api/intents`, no Twin start, no simulation state.

**Deployment & handoff** — one `POST /api/missions/{id}/deploy`, then a lock
banner and an automatic `router.push("/control")`. Mission Control is unchanged
apart from the additive strip, which renders only when a package is deployed.

---

## 3. Boundaries

- `backend/mission_pipeline/` imports only `core/`, `config`, `utils`,
  `backend.serializers` and its own modules — no Hive, HAL, PX4, MAVLink, ROS2,
  Simulation Core or Twin runtime (asserted by an AST scan in
  `tests/test_mission_review.py`).
- Deployment occurs exclusively through `TwinDeploymentGateway`.
- Package contents are transferred byte-for-byte; a test asserts the object the
  Twin receives equals the computed package.
- Deployment does not start execution; a test asserts mission status is
  unchanged after deploying.

---

## 4. Issues fixed during this phase

| Issue | Resolution |
| --- | --- |
| Package recomputation after deployment would break immutability (Planning Core is deterministic but the definition could drift) | `_locked_package()` returns the stored package for deployed missions on both `/review` and `/package` |
| Mission edits after deployment would silently invalidate the deployed package | `PUT`/`DELETE /api/missions/{id}` return `409` once locked |
| A pipeline import of the Twin runtime would have violated the boundary | injected `TwinDeploymentGateway` protocol, composed in `twin_server.py` |
| Package sub-objects are untyped records on the wire | `lib/missionPackageView.ts` narrows them with explicit guards instead of `any` |
