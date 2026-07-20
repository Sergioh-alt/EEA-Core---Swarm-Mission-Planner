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
| `/planning` | Read-only preview of the backend-owned coverage route |
| `/deployment` | Deploy (START_MISSION intent) |
| `/mission/replay` | Read-only historical replay |
| `/analytics` | Backend-derived mission analytics |
| `/alerts` | Alert feed |
| `/settings` | Configuration / boundary info |

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
