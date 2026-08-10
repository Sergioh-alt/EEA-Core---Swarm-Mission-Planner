# Phase 10D.7 — Mission Library & Scheduler (Implementation Report)

The final functional layer of the Phase 10D demonstration workflow: reusable
saved missions, operator schedules, execution preparation and execution
history.

```
Field → Preparation → Mission Designer → Fleet Configuration → Mission Definition
      → Planning Core → Mission Package → [Mission Library] → [Scheduler]
      → Execution preparation → Digital Twin → Mission Control
```

No architecture change, no parallel mission model, no backend decision logic.
The library stores and retrieves the existing contract; the scheduler stores
explicit operator intent; the Digital Twin remains the only runtime truth.

---

## 1. Backend

### `backend/mission_pipeline/library.py` (new)

Typed models and pure logic — no runtime import.

| Element | Responsibility |
| --- | --- |
| `LibraryEntry` | one saved mission: definition snapshot + the Mission Package planned for it, with `definition_version` / `package_definition_version`, template flag, `ready`/`archived` status, entry `version` |
| `LibraryEntry.package_stale` | true when the stored package predates the stored definition — reported, never auto-fixed |
| `summarize_definition()` | the list/detail summary (field, crop, operation, zones, products, fleet count, area, routes, Go/No-Go, duration) — every operational figure **copied** from the package |
| `ScheduleEntry` | operator intent: `start_date`, `times[]`, recurrence (`one_time`/`daily`/`weekly`/`custom`), `weekdays[]` (0 = Monday), `interval_days`, `enabled`, `last_triggered_ms`, `last_result` |
| `validate_schedule()` | rejects malformed dates/times/weekdays/intervals; surfaces the error, never repairs intent |
| `occurrences()` / `next_occurrence()` / `due_occurrence()` | arithmetic expansion of the operator's own rule; every entry in `times` becomes its own occurrence |
| `ExecutionRecord` | execution history: trigger, schedule reference, status, planned figures, mirrored runtime figures, warnings, deployment id, start/end |
| `planned_metrics()` | copies coverage, confidence, Go/No-Go, duration, liquid, battery cycles and area out of the executed package |
| `apply_runtime_state()` | mirrors the Twin's status/progress/events into an open record and closes it on a terminal state |

Templates (`LibraryEntry`) and history (`ExecutionRecord`) are separate record
types, so an execution can never mutate a reusable mission.

### `backend/mission_pipeline/execution.py` (new)

Execution preparation behind an injected boundary.

```python
class MissionExecutionGateway(Protocol):
    def deploy_mission_package(self, package: JSONObject) -> JSONObject: ...
    def start_mission(self) -> bool: ...
    def get_mission_payload(self) -> JSONObject: ...
```

* `resolve_package(entry)` returns the stored package unchanged; only when an
  entry has none does it delegate to the existing `build_mission_package`.
* `prepare_execution(...)` reads the current runtime state, **rejects a busy
  Twin** (`RUNNING`/`PAUSED`) instead of resolving the conflict, transfers the
  package verbatim through `deploy_mission_package`, opens an `ExecutionRecord`
  and starts the mission when `start_now`.
* `dispatch_due_schedules(...)` runs only enabled schedules with a due
  occurrence, marks the occurrence triggered and stores a readable
  `last_result`. It never queues, retries or reschedules.

### `backend/mission_pipeline/persistence.py`

`DefinitionStore` gains library, schedule and execution methods, implemented by
both `SQLiteDefinitionStore` (new `library_entries`, `mission_schedules`,
`mission_executions` tables) and `InMemoryDefinitionStore`. Persistence stays
the same replaceable abstraction introduced in 10D.2.

### `backend/mission_pipeline/library_api.py` (new)

| Endpoint | Behavior |
| --- | --- |
| `GET/POST /api/library` | list saved missions / save a stored Mission Definition together with its Planning Core package |
| `GET/PUT/DELETE /api/library/{id}` | read; metadata-only update (name, description, template, status); remove |
| `POST /api/library/{id}/resync` | explicit re-plan: refresh the definition snapshot, replace the package, bump the entry version |
| `POST /api/library/{id}/duplicate` | new Mission Definition (new id, version 1); the saved mission is untouched |
| `POST /api/library/{id}/execute` | execution preparation; `409` on a busy Twin, `503` without a gateway |
| `GET/POST /api/schedules`, `GET/PUT/DELETE /api/schedules/{id}`, `POST /api/schedules/{id}/enabled` | schedule CRUD; responses include `next_occurrence_ms` and `upcoming_ms` |
| `GET /api/executions`, `GET /api/executions/{id}` | execution history |

### `backend/twin_runtime.py`

The Twin previously stored a deployed package but still flew the hardcoded demo
route. It now **adopts the delivered geometry**: `_adopt_package_geometry()`
reads `package.execution.field_polygon_m` and `routes_m`, converts the local
metric coordinates to geographic ones around `FIELD_CENTER`, and uses the route
order and count exactly as delivered — no route is generated, reordered,
retimed or reassigned. `mission_geometry()` returns the deployed geometry when
present and the hardcoded demo geometry otherwise (fallback preserved). Route
advancement now consumes a per-tick travel budget so densely sampled package
routes progress at the same speed as the sparse demo route.

### `backend/twin_server.py`

Mounts the library router with the runtime as execution gateway and runs a
5 s loop next to the existing tick loop that (a) dispatches the operator's due
occurrences and (b) mirrors Twin state into open history records. The loop is
composed at the root; the library and scheduler modules stay runtime-free.

---

## 2. Frontend

| Route | Content |
| --- | --- |
| `/library` | saved missions with status/template/stale badges, field, operation, drone & product counts, area, routes, Go/No-Go, duration, version and last update; search, archived filter, save-from-mission, duplicate, archive/restore, delete |
| `/library/[entryId]` | Mission Definition summary, operational parameters, execution readiness, Planning Core result, resources, risks and the route table; *Use as template*, *Schedule*, *Execute now*, and an explicit *Re-run Planning Core* when the package is outdated |
| `/schedules` | scheduled missions with recurrence, times, enabled state, next and upcoming occurrences, last run result; create, enable/disable, delete |
| `/history` | executions with trigger, status, field, operation, products, drones, routes, duration, planned figures and mirrored runtime progress; polls while a record is open |

Shared: `components/library/LibraryEntryCard.tsx`,
`components/library/ScheduleForm.tsx`; new **Library / Scheduler / History**
sidebar entries; typed contracts and client methods in
`contracts/mission.ts` and `lib/pipelineClient.ts`.

Every operational number rendered is read from the backend through the existing
`missionPackageView` narrowing helpers — the UI computes none of them.

---

## 3. Boundaries

* `library.py` and `execution.py` import no Hive, HAL, PX4, MAVLink, ROS2,
  simulation or Twin runtime module; the Twin is reached only through the
  injected `MissionExecutionGateway`.
* The library performs no routing, optimization, allocation or feasibility
  evaluation; it stores and returns Planning Core output verbatim.
* The scheduler chooses no time, alters no mission and resolves no conflict.
* The Digital Twin remains the runtime source of truth; Mission Control keeps
  its visualization and intent responsibilities, including the hardcoded demo
  route fallback.

---

## 4. Known limitations

1. Occurrence expansion uses the server's local timezone; no per-schedule
   timezone is stored.
2. Conflicts are surfaced, not queued: an occurrence due while the Twin is busy
   is recorded as a failed run on the schedule and not retried.
3. The demo server autostarts the hardcoded mission, so *Execute now* returns
   `409` until that run is stopped in Mission Control.
4. Execution history mirrors the single runtime mission; only the most recent
   open record is updated.
5. Import/export of library entries is not implemented (roadmap capability,
   not part of the 10D.7 request).
6. SQLite remains the demonstration store; no production database migration.
