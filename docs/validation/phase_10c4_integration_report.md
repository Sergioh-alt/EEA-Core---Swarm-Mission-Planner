# Phase 10C.4 — Advanced UI Integration — Integration Report

This report documents the live end-to-end integration between the Next.js Mission
Control UI and the thin Digital Twin API server.

## Data flow (as built)

```
SimulationCore
  → ROS2 SwarmBus (DroneStateMessage)
  → TwinRuntime._sync_from_bus → DroneStateUpdate
  → DigitalTwin (SSOT, immutable SwarmState + snapshots)
  → FastAPI REST  (/api/twin/*, /api/mission/*, /api/alerts, /api/twin/analytics)
  → FastAPI WS    (/ws/twin: SWARM_STATE, MISSION_STATUS, CONNECTION_STATUS, ALERT)
  → Next.js UI    (Zustand stores → panels)
```

Operator actions travel the **only** write path:

```
UI IntentBar → POST /api/intents → TwinRuntime lifecycle (start/pause/resume/stop/snapshot)
```

The UI never decides; the backend accepts/rejects and broadcasts the resulting
`MISSION_STATUS`.

## Running it

```bash
# Backend (terminal 1)
pip install -r requirements.txt
python -m backend.run                       # serves http://localhost:8000

# Frontend (terminal 2)
cd orion-ui
cp .env.example .env.local                  # sets NEXT_PUBLIC_TWIN_API_URL=http://localhost:8000
npm install
npm run dev                                 # http://localhost:3000
```

When `NEXT_PUBLIC_TWIN_API_URL` is unset, the UI runs in self-contained dev-mock mode
(unchanged from 10C.3) so a fresh clone still renders without a backend.

## Manual browser walkthrough (recorded)

Performed against the live backend at `http://localhost:8000`, UI at
`http://localhost:3000`, LIVE mode:

1. **Live state** — `/control` shows "Connected", 3 drones streaming (GPS OK, STANDBY),
   mission zone polygon from `/api/mission/geometry`. *Precondition: mission IDLE.*
2. **Intent** — clicking **Start** issues `POST /api/intents {intent_type:"START_MISSION"}`
   (backend logged `200 OK`); mission → RUNNING, drones → AUTO, event log entry added,
   telemetry charts and executed routes update live.
3. **Map layers** — all 7 toggles present; toggling is local-only (mission progress
   continued 68% → 98% unaffected).
4. **Analytics** — `/analytics` renders 50 snapshots, fleet-utilization area chart,
   100% progress, 0.8 min duration; alert-frequency honestly empty (no failures injected).
5. **Replay** — `/mission/replay` → "Load recorded timeline" fetches a 59-frame timeline;
   Play advances frames (timestamp + scrubber progress); "Last frame" jump reconstructs
   final drone positions in the read-only scatter; live header state untouched.

**Console:** 0 errors in the dev server log during the walkthrough.

## Verification transcripts

- REST: `/api/health` → `{"status":"ok"}`; `/api/twin/state` → 3 drones, versioned
  `SwarmState`; `/api/twin/snapshots` → immutable snapshot list; `/api/twin/replay` →
  frame timeline; `/api/twin/analytics` → aggregated metrics.
- WebSocket: initial `SWARM_STATE` + `MISSION_STATUS` + `CONNECTION_STATUS` on connect,
  then 2 Hz `SWARM_STATE` broadcasts; `MISSION_STATUS` broadcast on intent lifecycle.
- Backend tests (`tests/test_twin_api.py`): 15 passed — serialization, enum wire values,
  every REST route, 404s, replay, analytics, intent lifecycle, link-loss propagation.
- Full Python regression: 858 passed.
- Clean clone: `npm install` + `npm run build` → 15/15 pages; `pytest` → 858 passed.
