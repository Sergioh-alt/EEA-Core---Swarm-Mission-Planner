# ORIÓN Mission Control — Operator Workflow

Mission Control is a **visualization and intent-submission** interface. The
operator observes the Digital Twin and submits intents; all decisions are made by
the backend (Hive). The UI never plans, schedules, optimizes, or mutates state.

## Prerequisites

- Backend (Digital Twin API) running on port 8000:
  ```bash
  TWIN_API_PORT=8000 TWIN_AUTOSTART=0 TWIN_TICK_INTERVAL_S=1.0 python -m backend.run
  ```
- Frontend running (from `orion-ui/`), pointed at the backend:
  ```bash
  NEXT_PUBLIC_TWIN_API_URL=http://localhost:8000 npm run dev
  ```
- Optional: `NEXT_PUBLIC_MAPBOX_TOKEN` for Mapbox Dark tiles (OSM used otherwise).

## Screens

| Route | Purpose |
|-------|---------|
| `/` | Dashboard overview |
| `/control` | Primary Mission Control (map, fleet, telemetry, status, alerts, intents) |
| `/fleet`, `/fleet/[id]` | Fleet list and per-drone detail |
| `/mission` | Mission summary |
| `/map` | Full interactive geographic map |
| `/fields`, `/fields/[id]` | Field acquisition & preparation (create, upload imagery, annotate geometry) |
| `/planning` | Read-only preview of the backend-owned coverage route |
| `/deployment` | Deploy (START_MISSION intent) |
| `/mission/replay` | Read-only historical replay |
| `/analytics` | Backend-derived mission analytics |
| `/alerts` | Alert feed |
| `/settings` | Configuration / boundary info |

## Field preparation workflow (Phase 10D.3)

Before generating a mission, prepare the field. This is **input collection only**
— no planning, routing, or perception happens here.

1. **Create a field.** Open `/fields`, enter a name / crop / location, and create.
2. **Upload imagery.** In the preparation workspace, choose a source
   (satellite / drone / manual) and upload an image. Switch between images with the
   image strip.
3. **Set scale.** Enter meters-per-pixel so drawings map to metric geometry.
4. **Annotate.** Pick a tool — Boundary, Crop / Management / Treatment / Exclusion
   zones, or Obstacle (tree/pole/building/…) — click points on the image, then
   double-click or **Finish** to close the polygon.
5. **Edit.** In Select mode, click a shape to highlight it; rename, enable/disable
   (zones), or remove geometry from the list.
6. **Save / Reload.** **Save Field** persists the definition (geometry + metadata +
   image references); **Reload** restores the last saved state. The saved field is
   later referenced by a Mission Definition and consumed by the Planning Core.

## Mission Designer (10D.4)

Turn a prepared field into a complete **Mission Definition**. The Mission
Designer only collects parameters and constructs the definition — it performs no
planning, routing, optimization, allocation, or scheduling, and never contacts
the Digital Twin.

1. **Create a mission.** Open `/missions`, pick a prepared field, name the
   mission, and create it. This opens the designer at `/missions/{id}`.
2. **Mission information.** Set description, execution priority, estimated
   execution date, and optional notes. (Captured only — no scheduling logic.)
3. **Zone selection.** The prepared field renders read-only. Include/exclude
   individual zones or use **Select entire field**. Fields without zones cover
   the whole boundary.
4. **Agricultural operation.** Choose spraying / fertilization / seeding /
   mapping / inspection / custom.
5. **Product configuration.** Add products from the catalog and set rate, tank,
   concentration, dilution, and safety notes. Multiple products are supported.
   (No consumption or allocation is computed.)
6. **Operational parameters.** Preferences only — flight altitude, nominal
   speed, overlap, safety margin, coverage direction, route preference, planning
   mode, drones requested. The Planning Core decides how to use them.
7. **Fleet selection.** Add available assets from the Fleet Inventory (ORION /
   third-party / mixed). Specifications are read-only; no allocation happens.
8. **Completeness.** The right column checks interface completeness only (name,
   field, zone participation, operation, product, altitude, fleet) — never
   operational feasibility.
9. **Preview.** Review the full Mission Definition summary. This is a definition
   preview, not yet a Mission Package.
10. **Submit to Planning Core.** Saves the definition and submits it to the
    existing `POST /api/planning/compute` (10D.2). The Planning Core runs all
    environment analysis, swarm planning, routing, resourcing, risk analysis,
    timeline and recommendation, and returns a **Mission Package** shown
    read-only. The package card lists any validation warnings/errors verbatim
    (e.g. an unknown crop falls back to the generic profile — a non-blocking
    warning, not an invalid definition).

## Fleet Configuration (10D.5)

Open from the Mission Designer's **Fleet Selection → Fleet Configuration →**
link (route `/missions/[missionId]/fleet`). This workspace enriches the Mission
Definition with the operational fleet; it performs no allocation or planning and
never contacts the Digital Twin.

1. **Fleet selection.** Add one or more available models (heterogeneous fleets
   supported — e.g. ORION Standard, DJI Agras T40, XAG P100). Each shows
   read-only catalog specs: status, payload, battery, endurance, tank capacity,
   supported operations, sensors, equipment.
2. **Equipment configuration** (per drone). Toggle installed equipment and the
   sensor package; choose a camera package, sprayer configuration and (future-
   compatible) granular spreader from the model's advertised options.
3. **Tank & product assignment** (per drone). Assign a mission/catalog product
   to each advertised tank (e.g. Tank A → Herbicide, Tank B → Fertilizer).
4. **Fleet Summary** (informational). Drone count, total payload/liquid
   capacity, limiting endurance, selected equipment, and a configuration-
   completeness readiness indicator. Consumption, required capacity and
   feasibility are computed by the Planning Core, not here.
5. **Save fleet.** Persists the enriched fleet into the Mission Definition via
   `PUT /api/missions/{id}`, ready for the Planning Core.

## Golden-path workflow

1. **Connect.** Open `/control`. The header shows `Connected` when the WebSocket is
   live. If it shows `Disconnected`/`Error`, use the **Reconnect** button.
2. **Review geometry.** The map shows the field polygon and planned coverage routes
   (owned by the backend/Digital Twin).
3. **Start the mission.** Use the Intent Bar **Start** (or the Deployment page
   **Deploy Mission**). This submits `START_MISSION` to `POST /api/intents`. Status
   transitions IDLE → RUNNING.
4. **Monitor live telemetry.** Fleet panel and telemetry charts update at ~1 Hz:
   battery, altitude, speed, GPS, mode. Executed routes trail the drones on the map.
5. **Control lifecycle.** Pause / Resume / Stop via the Intent Bar; enabled actions
   reflect the current mission state.
6. **Completion.** When coverage reaches ~100%, status → COMPLETED and the event log
   records the transition.
7. **Replay.** Open `/mission/replay`, load the timeline, and use play / pause /
   scrubber / speed / jump. Replay is read-only and never affects live state.
8. **Analytics.** Open `/analytics` for backend snapshot-derived metrics.

## Intent reference

`START_MISSION` · `PAUSE_MISSION` · `RESUME_MISSION` · `STOP_MISSION` ·
`REQUEST_SNAPSHOT` — all submitted via `POST /api/intents`. The backend accepts or
rejects; the UI only submits.
