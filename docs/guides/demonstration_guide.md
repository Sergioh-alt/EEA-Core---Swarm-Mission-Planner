# ORIÓN Mission Control — Demonstration Guide

A concise script for presentations, validation sessions, and investor meetings.
Target run time: ~5–7 minutes.

## Setup (before the audience)

1. Start the backend:
   ```bash
   TWIN_API_PORT=8000 TWIN_AUTOSTART=0 TWIN_TICK_INTERVAL_S=1.0 python -m backend.run
   ```
2. Start the frontend:
   ```bash
   cd orion-ui && NEXT_PUBLIC_TWIN_API_URL=http://localhost:8000 npm run dev
   ```
3. Confirm health: `curl http://localhost:8000/api/health` → `{"status":"ok",...}`.
4. Open `http://localhost:3000/control`; confirm the header shows **Connected**.
5. (Optional) Maximize the browser window for a clean full-screen view.

## Talk track

1. **Architecture (30s).** "The UI is a pure visualization + intent layer. The
   Digital Twin is the single source of truth. The frontend never talks to PX4,
   ROS2, MAVLink, the Simulation Core, or Hive directly."
2. **Idle state (30s).** Show `/control`: map with the field polygon and planned
   coverage routes, fleet panel with 3 drones, telemetry ready, mission IDLE.
3. **Deploy (1 min).** Press **Start** in the Intent Bar. "This submits a
   START_MISSION *intent* — the UI does not decide anything; the backend does."
   Mission transitions to RUNNING.
4. **Live telemetry (1–2 min).** Point out drones moving along the coverage route,
   executed-route trails, realistic speed (~16 m/s), battery/altitude/GPS updating
   at ~1 Hz, and the mission progress bar climbing.
5. **Map & layers (1 min).** Open `/map`; toggle layers (drones, planned/executed
   routes, mission zone). "Layer visibility is client-side only; it never mutates
   backend state."
6. **Lifecycle (30s).** Demonstrate Pause → Resume → Stop from the Intent Bar.
7. **Replay (1 min).** Open `/mission/replay`; load the timeline and scrub through
   history. "Fully read-only reconstruction from Digital Twin snapshots."
8. **Analytics (30s).** Open `/analytics`; show backend-derived metrics.
9. **Resilience (optional, 30s).** Stop the backend to show the Disconnected state
   and the Reconnect affordance; restart and reconnect.

## Notes

- If Mapbox tiles look like plain raster, that's the OSM fallback — set
  `NEXT_PUBLIC_MAPBOX_TOKEN` for Mapbox Dark styling.
- A full mission completes in ~331 ticks (~5.5 min at 1 tick/s). For a shorter demo,
  lower `TWIN_TICK_INTERVAL_S` (e.g. `0.5`) to speed up the simulation clock.
