# Phase 10C.3 — Mission Control UI — Interaction Report

**Phase:** 10C.3 — Mission Control UI
**Route:** `/control`
**Interaction model:** Read-only state + intent submission only

---

## 1. Data Flow (one-way)

```
Digital Twin (WebSocket/REST)   ── production ──┐
                                                 ├─► Zustand stores ─► React components (render only)
Mock Data Provider (~1 Hz)      ── local dev ───┘
        │
        └─ swarmStore / droneStore / missionStore / alertStore / connectionStore

Operator action ─► IntentBar ─► POST /api/intents ─► (backend) ─► Hive
                                   (fire-and-forget; UI never mutates state)
```

The UI subscribes to store slices and re-renders. It never writes execution
state, never calls PX4/ROS2/MAVLink/Hive, and never computes routes or
allocations.

---

## 2. Interactive Elements

| Element | Location | Action | Effect | Decision logic? |
|---------|----------|--------|--------|-----------------|
| Drone card | Fleet Panel | click | `droneStore.selectDrone(id)`; map flies to drone; telemetry filters to that drone; click again deselects | No |
| Map marker | Map | rendered from `droneStore.drones`; health-colored + heading | position/color update on state change only | No |
| Layers button | Map (top-right) | click | opens layer panel | No |
| Drones / Routes / Zones / Alerts toggles | Layers panel | click | local `layerVisibility` state → show/hide map layers | No |
| START button | Intent Bar | click | `POST /api/intents {type:"START_MISSION"}` | No — intent only |
| PAUSE button | Intent Bar | click | `POST /api/intents {type:"PAUSE"}` | No — intent only |
| STOP button | Intent Bar | click | `POST /api/intents {type:"STOP"}` | No — intent only |
| REPLAY button | Intent Bar | click | `POST /api/intents {type:"REPLAY"}` | No — intent only |
| Mark read | Alert Feed | click | `alertStore.markAllRead()` (UI read-state only) | No |

Intent buttons are enabled/disabled purely as a function of the current
mission status read from the store (e.g. START disabled while RUNNING). This
is presentational gating, not decision-making.

---

## 3. Live Behavior Verified (production build)

Recorded end-to-end walkthrough. Observed with 3 simulated drones:

1. **Panels render** — map (OSM basemap + field-zone polygon + 3 drone
   markers), fleet panel, 3 telemetry charts, mission status, alert feed,
   intent bar.
2. **Click-to-focus** — selecting *Drone 2* highlighted its fleet card, flew
   and zoomed the map to it (selection ring on marker), and filtered the
   telemetry panel to *Drone 2*.
3. **Live streaming (~1 Hz)** — mission progress advanced (1% → 33%),
   telemetry charts accumulated 3 colored per-drone series, drone headings /
   altitudes changed, battery drained; alerts appeared with an unread badge and
   populated the event log.
4. **Intent submission** — PAUSE submitted the intent without changing mission
   state directly (state remains Digital-Twin-driven), confirming the strict
   read-only / intent-only model.
5. **Layer toggles** — turning Zones + Drones off removed the field polygon and
   all drone markers; turning them back on restored both.
6. **Console** — empty (zero errors) throughout load and all interactions.

---

## 4. Visual Design

Dark aerospace/mission-control theme, map as central anchor, modular panels
(fleet left, telemetry right, mission + alerts bottom, intent bar footer),
high-contrast health colors (OK `#22c55e`, WARNING `#f59e0b`,
CRITICAL `#ef4444`).

---

## 5. Conclusion

All Mission Control interactions are read-only or intent-based. No interactive
element performs planning, optimization, allocation, scheduling, or direct
state mutation. Interaction model is fully compliant with the Phase 10
System Boundary Spec.
