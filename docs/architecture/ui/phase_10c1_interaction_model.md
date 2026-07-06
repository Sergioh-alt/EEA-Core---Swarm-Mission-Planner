# Phase 10C.1 — Interaction Model & Operator Workflow

**Status:** DESIGN SPECIFICATION  

---

## 1. Operator Roles & Workflows

### 1.1 Primary Operator Workflow

The operator monitors the swarm through the UI. All control actions are submitted as **intents** — the operator requests, Hive decides.

```
Operator Daily Workflow:

1. LOGIN → Dashboard (/)
   See: swarm health, environment, pending alerts
   Action: assess system readiness

2. REVIEW FLEET → Fleet (/fleet)
   See: all drone status, battery levels, GPS quality
   Action: verify fleet is ready for mission

3. MONITOR MISSION → Mission (/mission)
   See: timeline, coverage progress, event log
   Action: observe mission execution (read-only)

4. RESPOND TO ALERTS → Alerts (/alerts)
   See: categorized alerts, severity breakdown
   Action: acknowledge alerts, submit pause/stop intent if critical

5. REVIEW MAP → Field Map (/map)
   See: drone positions, coverage, flight paths
   Action: visual verification of coverage pattern

6. POST-MISSION REPLAY → Replay (/mission/replay)
   See: deterministic replay of completed mission
   Action: review specific events, compare states
```

### 1.2 Alert Response Workflow

```
Alert occurs (e.g., Battery Critical on Drone 2)
  |
  v
TopBar alert badge increments (red dot)
  |
  v
AlertBanner appears at top (CRITICAL severity only)
  |
  v
Operator clicks alert badge → /alerts
  |
  v
Operator reviews alert detail:
  - Source: Drone 2
  - Category: BATTERY_DEGRADATION
  - Battery: 8%
  - Timestamp: 12:45:30
  |
  v
Operator decides response:
  Option A: Continue monitoring (no action — Hive handles RTL automatically)
  Option B: Submit PAUSE intent → Hive decides whether to pause mission
  Option C: Submit STOP intent → Hive decides whether to abort mission
  |
  v
If intent submitted:
  - UI shows "Intent submitted" confirmation
  - UI waits for Hive response via WebSocket
  - Mission status updates in real-time
```

### 1.3 Failure Monitoring Workflow

```
Failure injected (e.g., GPS Loss on Drone 3)
  |
  v
Digital Twin updates: active_failures includes GPS_LOSS
  |
  v
WebSocket pushes SwarmState with updated failures
  |
  v
UI Components react:
  - Dashboard: EnvironmentCard shows failure
  - Fleet: Drone 3 card shows GPS indicator RED
  - Map: Drone 3 marker shows failure overlay
  - Alerts: New CRITICAL alert added
  |
  v
Operator observes failure propagation across all views
No manual intervention required — system handles automatically
```

---

## 2. User Interaction Catalog

### 2.1 Dashboard Interactions

| Element | Interaction | Result |
|---------|------------|--------|
| Swarm Summary Card | Click drone count | Navigate to /fleet |
| Mini Map drone marker | Click | Navigate to /fleet/[droneId] |
| Alert Feed item | Click | Navigate to /alerts with filter |
| Mission Status Card | Click "View Mission" | Navigate to /mission |
| Environment Card | Hover wind indicator | Show detailed wind info tooltip |

### 2.2 Fleet Interactions

| Element | Interaction | Result |
|---------|------------|--------|
| Drone Card | Click | Navigate to /fleet/[droneId] |
| View Toggle | Click Grid/List | Switch layout mode |
| Battery Chart | Hover bar | Show exact percentage tooltip |
| Drone Card status indicator | Hover | Show full health details |

### 2.3 Drone Detail Interactions

| Element | Interaction | Result |
|---------|------------|--------|
| Back Button | Click | Navigate to /fleet |
| Position Map | Scroll/zoom | Pan/zoom Mapbox view |
| Telemetry Chart | Hover point | Show value at timestamp |
| Telemetry Chart tabs | Click Battery/Altitude/Speed | Switch chart |
| GPS Indicator | Hover | Show accuracy in meters |

### 2.4 Mission Interactions

| Element | Interaction | Result |
|---------|------------|--------|
| Timeline bar | Click position | Show state at that time |
| Task list item | Hover | Show task details |
| Event log entry | Click | Highlight on timeline |
| "View Replay" button | Click | Navigate to /mission/replay |
| Coverage chart | Hover | Show percentage at timestamp |

### 2.5 Replay Interactions

| Element | Interaction | Result |
|---------|------------|--------|
| Play/Pause button | Click | Toggle playback |
| Step Forward | Click | Advance one frame |
| Step Back | Click | Go back one frame |
| Skip Forward | Click | Jump to next snapshot |
| Skip Back | Click | Jump to previous snapshot |
| Speed selector | Click 0.5x/1x/2x/4x | Change playback speed |
| Timeline scrubber | Drag | Seek to frame |
| Snapshot list item | Click | Jump to that snapshot's frame |
| Replay map | Pan/zoom | Navigate map at current frame |

### 2.6 Map Interactions

| Element | Interaction | Result |
|---------|------------|--------|
| Drone marker | Click | Show drone detail overlay |
| Drone marker | Hover | Show brief status tooltip |
| Farm polygon | Click sector | Highlight sector coverage |
| Layer toggles | Click | Show/hide map layers |
| Map | Scroll/zoom/pan | Navigate map |
| Wind indicator | Hover | Show speed + direction |

### 2.7 Alert Interactions

| Element | Interaction | Result |
|---------|------------|--------|
| Filter buttons | Click | Filter by severity |
| Alert card | Click | Expand details |
| Alert source link | Click | Navigate to drone or system |
| Clear resolved | Click | Hide resolved alerts |

---

## 3. Error Visualization

### 3.1 Error Categories & Visual Treatment

| Error Category | Visual Indicator | Location |
|---------------|-----------------|----------|
| Battery Critical (<10%) | Red battery icon, pulsing | DroneCard, DroneDetail, Map marker |
| Battery Warning (<25%) | Amber battery icon | DroneCard, DroneDetail |
| GPS Loss | Red GPS icon with X | DroneCard, DroneDetail, Map marker |
| GPS Degraded (>5m) | Amber GPS icon | DroneCard, DroneDetail |
| Communication Loss | Red comm icon, dashed marker | DroneCard, DroneDetail, Map marker |
| Wind Severe (>15 m/s) | Red wind icon | EnvironmentCard, Map overlay |
| Wind Degraded (>8 m/s) | Amber wind icon | EnvironmentCard |
| Mission Failed | Red status badge | MissionStatusCard, MissionTimeline |
| Drone Failed | Red state tag, pulse animation | DroneCard, Map marker |
| WebSocket Disconnected | Red "DISCONNECTED" badge | TopBar LiveBadge |
| Data Stale (>5s) | Amber "STALE" badge, dimmed values | TopBar, affected components |

### 3.2 Alert Severity Visual System

```
CRITICAL (Red)
  - Full-width banner at top of page
  - Red background, white text
  - Icon: exclamation triangle
  - Sound notification (optional, configurable)
  - Auto-expanded in alert feed

WARNING (Amber)
  - Alert feed entry with amber left border
  - Amber icon
  - No banner (unless multiple warnings)
  - Collapsed by default

INFO (Blue)
  - Alert feed entry with blue left border
  - Blue icon
  - Collapsed by default
  - Auto-dismiss after 60s (configurable)
```

---

## 4. Drone Status Visualization

### 4.1 Drone Card States

```
HEALTHY (Green border)
  +------------------+
  | Drone 1    [OK]  |
  | Mode: GUIDED     |
  | Bat: 92% [====] |
  | GPS: 1.0m  [OK]  |
  | Comm: [OK]       |
  | Task: IN_PROGRESS|
  +------------------+

WARNING (Amber border)
  +------------------+
  | Drone 2    [!]   |
  | Mode: GUIDED     |
  | Bat: 22% [==  ]  |
  | GPS: 3.5m  [!]   |
  | Comm: [OK]       |
  | Task: IN_PROGRESS|
  +------------------+

CRITICAL (Red border, pulse)
  +------------------+
  | Drone 3   [!!!]  |
  | Mode: STANDBY    |
  | Bat: 8%  [=   ]  |
  | GPS: ---  [X]    |
  | Comm: [LOST]     |
  | Task: FAILED     |
  +------------------+

OFFLINE (Gray border, dimmed)
  +------------------+
  | Drone 4   [---]  |
  | Mode: ---        |
  | Bat: ---         |
  | GPS: ---         |
  | Comm: [---]      |
  | Task: ---        |
  +------------------+
```

### 4.2 Map Marker States

| State | Color | Shape | Animation |
|-------|-------|-------|-----------|
| ACTIVE (healthy) | Green (#22C55E) | Circle with heading arrow | None |
| ACTIVE (warning) | Amber (#F59E0B) | Circle with heading arrow | None |
| RETURNING | Blue (#3B82F6) | Circle with return arrow | None |
| IDLE | Gray (#6B7280) | Hollow circle | None |
| FAIL | Red (#EF4444) | Circle with X | Pulse ring |
| Disconnected | Red outline (#EF4444) | Dashed circle | Blink |

---

## 5. Mission Monitoring Layout

### 5.1 Mission States

| Status | TopBar Badge | Timeline Color | Card Color |
|--------|-------------|---------------|------------|
| IDLE | Gray "IDLE" | Gray | Gray background |
| RUNNING | Green "RUNNING" + pulsing dot | Green progress bar | Green accent |
| PAUSED | Amber "PAUSED" | Amber progress bar | Amber accent |
| FAILED | Red "FAILED" | Red progress bar | Red accent |
| COMPLETED | Blue "COMPLETED" | Blue full bar | Blue accent |

### 5.2 Event Log Types

| Event Type | Icon | Color | Example |
|------------|------|-------|---------|
| Waypoint reached | Pin | Green | "Drone 1 reached WP3" |
| Task completed | Check | Green | "Sector A coverage complete" |
| Battery alert | Battery | Amber | "Drone 2 battery at 22%" |
| Failure detected | Warning | Red | "GPS loss on Drone 3" |
| Wind change | Wind | Blue | "Wind shift to 12 m/s NE" |
| Mission state change | Flag | Purple | "Mission paused by operator" |

---

## 6. Swarm Overview Layout

### 6.1 Dashboard Swarm Summary

```
+-------------------------------------------+
| SWARM STATUS                              |
|                                            |
|   Total: 5    Active: 3    Failed: 1      |
|   Idle: 1     Health: WARNING              |
|                                            |
|   [===== 3/5 active ==========]            |
|                                            |
|   Active Failures:                         |
|   [!] battery_degradation (D2)            |
|   [!] gps_loss (D4)                       |
+-------------------------------------------+
```

### 6.2 Fleet Grid Layout Rules

| Drone Count | Grid Columns | Card Size |
|-------------|-------------|-----------|
| 1-3 | 3 | Large (full detail) |
| 4-6 | 3 | Medium (key metrics) |
| 7-12 | 4 | Compact (status + battery) |
| 13-20 | 5 | Mini (status dot + ID) |
| 20+ | Table view (auto) | Row per drone |
