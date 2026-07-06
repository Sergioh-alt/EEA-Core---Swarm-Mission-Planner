# Phase 10C.1 — ORION UI Architecture

**Status:** DESIGN SPECIFICATION  
**Phase:** 10C.1 (Architecture Only — No Implementation)  
**Stack:** Next.js 14, WebSockets, Mapbox GL, Recharts  

---

## 1. Core Principle

The UI is a **visualization-only endpoint**. It consumes read-only state from the Digital Twin and renders it for the human operator. The UI never makes decisions, sends commands directly to hardware, or contains scheduling/optimization logic.

```
Data Flow (STRICT):
  Digital Twin (read-only) → WebSocket → UI State Store → React Components → Operator Screen

Intent Flow (STRICT):
  Operator Action → UI Intent Layer → Backend Intent Handler → Hive (decision authority)
```

The UI is the last link in the chain:
```
Hive → HAL → MAVLink → Drone → Telemetry → ROS2 → Digital Twin → UI
```

---

## 2. Application Architecture Overview

### 2.1 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | Next.js 14 (App Router) | Server/client rendering, routing |
| Real-time | WebSockets | Live telemetry streaming from Digital Twin |
| Mapping | Mapbox GL JS | 2D/3D field visualization, drone positions |
| Charts | Recharts | Telemetry analytics, battery trends, coverage |
| State | Zustand | Lightweight client state management |
| Styling | Tailwind CSS | Utility-first styling, dark theme |
| Types | TypeScript | End-to-end type safety |

### 2.2 Module Organization

```
orion-ui/
  src/
    app/                        # Next.js 14 App Router
      layout.tsx                # Root layout (navigation shell)
      page.tsx                  # Dashboard (default route)
      fleet/
        page.tsx                # Fleet overview
        [droneId]/
          page.tsx              # Individual drone detail
      mission/
        page.tsx                # Mission monitoring
        replay/
          page.tsx              # Mission replay
      map/
        page.tsx                # Full-screen field map
      alerts/
        page.tsx                # Alert center
      settings/
        page.tsx                # System settings

    components/
      layout/
        Sidebar.tsx             # Main navigation sidebar
        TopBar.tsx              # Status bar + alerts badge
        PageShell.tsx           # Common page wrapper

      dashboard/
        SwarmSummaryCard.tsx     # High-level swarm metrics
        MissionStatusCard.tsx   # Current mission state
        EnvironmentCard.tsx     # Wind, conditions
        AlertsFeed.tsx          # Recent alerts stream
        SystemHealthBadge.tsx   # Global health indicator

      fleet/
        FleetGrid.tsx           # Grid of all drone cards
        DroneCard.tsx           # Single drone summary card
        DroneDetailPanel.tsx    # Expanded drone view
        BatteryIndicator.tsx    # Battery level + voltage
        GPSIndicator.tsx        # GPS fix quality
        CommIndicator.tsx       # Communication status
        DroneStateTag.tsx       # Mode/state badge

      map/
        FieldMap.tsx            # Mapbox GL field renderer
        DroneMarker.tsx         # Per-drone position marker
        MissionZoneLayer.tsx    # Coverage area overlay
        FlightPathLayer.tsx     # Drone trajectory traces
        FailureOverlay.tsx      # Failure zone indicators
        WindIndicator.tsx       # Wind direction/speed overlay

      mission/
        MissionTimeline.tsx     # Playback timeline (play/pause/scrub)
        MissionProgress.tsx     # Coverage percentage bar
        TaskList.tsx            # Task completion list
        EventLog.tsx            # Time-ordered event feed

      telemetry/
        BatteryChart.tsx        # Per-drone battery over time
        AltitudeChart.tsx       # Altitude profile
        SpeedChart.tsx          # Ground speed chart
        CoverageChart.tsx       # Coverage progress chart
        EnvironmentChart.tsx    # Wind/conditions over time

      alerts/
        AlertBanner.tsx         # Critical alert banner (top)
        AlertCard.tsx           # Individual alert entry
        AlertFilterBar.tsx      # Filter by severity/type
        AlertHistory.tsx        # Historical alert list

      replay/
        ReplayControls.tsx      # Play/pause/speed/scrub
        ReplayTimeline.tsx      # Frame timeline bar
        SnapshotList.tsx        # Available snapshot versions
        StateComparison.tsx     # Side-by-side state diff

      common/
        StatusDot.tsx           # Color-coded status indicator
        MetricCard.tsx          # Numeric metric display
        LiveBadge.tsx           # "LIVE" / connection badge
        TimeAgo.tsx             # Relative timestamp
        LoadingSpinner.tsx      # Loading state

    stores/
      swarmStore.ts             # Zustand: SwarmState from Digital Twin
      droneStore.ts             # Zustand: per-drone state cache
      missionStore.ts           # Zustand: mission status
      alertStore.ts             # Zustand: alert queue
      replayStore.ts            # Zustand: replay state
      connectionStore.ts        # Zustand: WebSocket status

    contracts/
      types.ts                  # TypeScript types mirroring Digital Twin models
      events.ts                 # WebSocket event type definitions
      intents.ts                # UI intent type definitions

    hooks/
      useSwarmState.ts          # Subscribe to swarm state updates
      useDroneState.ts          # Subscribe to individual drone
      useAlerts.ts              # Alert management hook
      useReplay.ts              # Replay controls hook
      useWebSocket.ts           # WebSocket connection management

    lib/
      ws-client.ts              # WebSocket client wrapper
      mapbox-config.ts          # Mapbox GL configuration
      formatters.ts             # Data formatting utilities
      constants.ts              # UI constants, thresholds
```

---

## 3. Navigation Map

### 3.1 Primary Navigation (Sidebar)

```
[ORION Logo]
  |
  +-- Dashboard          /                    (default)
  +-- Fleet              /fleet
  |     +-- Drone Detail /fleet/[droneId]
  +-- Mission            /mission
  |     +-- Replay       /mission/replay
  +-- Field Map          /map
  +-- Alerts             /alerts
  +-- Settings           /settings
```

### 3.2 Navigation Behavior

| Route | Content | Update Frequency |
|-------|---------|-----------------|
| `/` | Dashboard: swarm summary, mission status, alerts, environment | Real-time (1 Hz) |
| `/fleet` | All drones in grid layout with live status | Real-time (1 Hz) |
| `/fleet/[id]` | Single drone: telemetry charts, position, full detail | Real-time (2 Hz) |
| `/mission` | Active mission: timeline, progress, task list, events | Real-time (1 Hz) |
| `/mission/replay` | Historical replay: snapshot playback, state comparison | On-demand |
| `/map` | Full-screen Mapbox: drones, zones, paths, failures | Real-time (2 Hz) |
| `/alerts` | Alert center: history, filtering, severity breakdown | Real-time (event-driven) |
| `/settings` | System configuration: thresholds, display preferences | Static |

---

## 4. Screen Definitions

### 4.1 Dashboard (/)

The operator's primary view. Shows system health at a glance.

```
+--------------------------------------------------------------+
| TopBar: [ORION] [LIVE] [Mission: RUNNING] [Alerts: 2]  [?]  |
+------+-------------------------------------------------------+
|      |  +-------------------+  +-------------------+         |
| Side |  | Swarm Summary     |  | Mission Status    |         |
| bar  |  | 3 active, 0 fail  |  | Coverage: 67%     |         |
|      |  | Health: OK        |  | Time: 12:34       |         |
|      |  +-------------------+  +-------------------+         |
|      |                                                        |
|      |  +-------------------+  +-------------------+         |
|      |  | Environment       |  | Alerts Feed       |         |
|      |  | Wind: 5.2 m/s NE  |  | [!] Battery low   |         |
|      |  | Condition: OK     |  | [!] GPS drift D2   |         |
|      |  +-------------------+  +-------------------+         |
|      |                                                        |
|      |  +----------------------------------------------+     |
|      |  | Mini Map (field + drone positions)            |     |
|      |  |  [D1]   [D2]                                  |     |
|      |  |              [D3]                              |     |
|      |  +----------------------------------------------+     |
+------+-------------------------------------------------------+
```

**Data sources:**
- `SwarmState.total_drones`, `active_drones`, `failed_drones`
- `SwarmState.mission_status`, `mission_id`
- `SwarmState.global_health`
- `SwarmState.environment_state` (wind, condition)
- `SwarmState.active_failures`
- `DroneState[]` for mini map positions

### 4.2 Fleet Overview (/fleet)

Grid of all drones with live status cards.

```
+------+-------------------------------------------------------+
|      |  Fleet Overview                          [Grid][List]  |
| Side |                                                        |
| bar  |  +----------+  +----------+  +----------+             |
|      |  | Drone 1  |  | Drone 2  |  | Drone 3  |             |
|      |  | GUIDED   |  | GUIDED   |  | STANDBY  |             |
|      |  | Bat: 87% |  | Bat: 92% |  | Bat: 100%|             |
|      |  | GPS: OK  |  | GPS: OK  |  | GPS: OK  |             |
|      |  | Comm: OK |  | Comm: OK |  | Comm: OK |             |
|      |  | Health:OK|  | Health:OK|  | Health:OK|             |
|      |  | Task: IP |  | Task: IP |  | Task: -- |             |
|      |  +----------+  +----------+  +----------+             |
|      |                                                        |
|      |  Fleet Summary                                         |
|      |  +----------------------------------------------+     |
|      |  | Battery Distribution (bar chart)              |     |
|      |  | [D1: 87%] [D2: 92%] [D3: 100%]               |     |
|      |  +----------------------------------------------+     |
+------+-------------------------------------------------------+
```

**Data sources:**
- `DroneState.drone_id`, `mode`, `battery_pct`, `gps_available`, `communication_active`, `health`, `current_task`

### 4.3 Drone Detail (/fleet/[droneId])

Full telemetry view for one drone.

```
+------+-------------------------------------------------------+
|      |  <- Back to Fleet     Drone 1 - GUIDED                |
| Side |                                                        |
| bar  |  +------------------+  +---------------------------+  |
|      |  | Status           |  | Position Map              |  |
|      |  | Armed: Yes       |  | [Mapbox mini view]        |  |
|      |  | Mode: GUIDED     |  | Lat: -34.61               |  |
|      |  | Health: OK       |  | Lon: -58.38                |  |
|      |  | Task: IN_PROGRESS|  | Alt: 15.2m                 |  |
|      |  | Heading: 245 deg |  |                             |  |
|      |  +------------------+  +---------------------------+  |
|      |                                                        |
|      |  +------------------+  +---------------------------+  |
|      |  | Battery          |  | Velocity                  |  |
|      |  | 87.2% [bar]      |  | Vx: 2.1  Vy: -0.3        |  |
|      |  | 11.8V            |  | Vz: 0.0  GS: 2.1 m/s     |  |
|      |  +------------------+  +---------------------------+  |
|      |                                                        |
|      |  +----------------------------------------------+     |
|      |  | Telemetry History (Recharts)                  |     |
|      |  | [Battery %] [Altitude] [Speed] over time      |     |
|      |  +----------------------------------------------+     |
+------+-------------------------------------------------------+
```

**Data sources:**
- Full `DroneState` for selected drone
- Historical data from replay timeline (per-drone)

### 4.4 Mission Monitoring (/mission)

Active mission visualization.

```
+------+-------------------------------------------------------+
|      |  Mission: AGR-2026-001             Status: RUNNING     |
| Side |                                                        |
| bar  |  +----------------------------------------------+     |
|      |  | Mission Timeline                              |     |
|      |  | |===========----------|  67% complete          |     |
|      |  | [Start]    [Now]     [Est. End]                |     |
|      |  +----------------------------------------------+     |
|      |                                                        |
|      |  +------------------+  +---------------------------+  |
|      |  | Task List        |  | Event Log                 |  |
|      |  | [x] Sector A     |  | 12:30 D1 reached WP3     |  |
|      |  | [x] Sector B     |  | 12:28 D2 battery 85%     |  |
|      |  | [ ] Sector C     |  | 12:25 Wind shift 12 deg  |  |
|      |  | [ ] Sector D     |  | 12:20 Mission started     |  |
|      |  +------------------+  +---------------------------+  |
|      |                                                        |
|      |  +----------------------------------------------+     |
|      |  | Coverage Progress (Recharts area chart)       |     |
|      |  +----------------------------------------------+     |
+------+-------------------------------------------------------+
```

### 4.5 Mission Replay (/mission/replay)

Deterministic replay from Digital Twin snapshots.

```
+------+-------------------------------------------------------+
|      |  Mission Replay                                        |
| Side |                                                        |
| bar  |  +----------------------------------------------+     |
|      |  | Replay Map (Mapbox)                           |     |
|      |  | [D1] [D2] [D3] at selected frame             |     |
|      |  +----------------------------------------------+     |
|      |                                                        |
|      |  +----------------------------------------------+     |
|      |  | [<<] [<] [Play/Pause] [>] [>>] [1x/2x/4x]   |     |
|      |  | Frame: 42/120     Snapshot v42                |     |
|      |  | |===========-------|                           |     |
|      |  +----------------------------------------------+     |
|      |                                                        |
|      |  +------------------+  +---------------------------+  |
|      |  | Snapshot List    |  | State at Frame            |  |
|      |  | v1  12:20:00     |  | Drones: 3                 |  |
|      |  | v2  12:20:30     |  | Active: 3                 |  |
|      |  | v3  12:21:00  *  |  | Health: OK                |  |
|      |  | v4  12:21:30     |  | Failures: none            |  |
|      |  +------------------+  +---------------------------+  |
+------+-------------------------------------------------------+
```

### 4.6 Field Map (/map)

Full-screen interactive map.

```
+------+-------------------------------------------------------+
|      |  +--------------------------------------------------+ |
| Side |  |                                                    | |
| bar  |  |  [Mapbox GL Full Screen]                           | |
|      |  |                                                    | |
|      |  |    [Farm Polygon]                                  | |
|      |  |      /----------\                                  | |
|      |  |     / Sector A   \    [D1] ->                      | |
|      |  |    |   Sector B   |                                | |
|      |  |     \  Sector C  /       [D2] ->                   | |
|      |  |      \----------/                                  | |
|      |  |                        [D3] ->                     | |
|      |  |                                                    | |
|      |  |  Legend: [Active] [Returning] [Idle] [Fail]        | |
|      |  |  Wind: -> 5.2 m/s NE                               | |
|      |  +--------------------------------------------------+ |
|      |  +--------------------------------------------------+ |
|      |  | Layer Controls: [Drones] [Paths] [Zones] [Wind]  | |
|      |  +--------------------------------------------------+ |
+------+-------------------------------------------------------+
```

**Map Layers:**
- Farm polygon (mission boundary)
- Sector boundaries (coverage zones)
- Drone markers (real-time positions, color-coded by state)
- Flight path traces (historical trajectory)
- Wind direction indicator
- Failure zone overlay (GPS loss area, link loss area)

### 4.7 Alert Center (/alerts)

Centralized alert management.

```
+------+-------------------------------------------------------+
|      |  Alert Center                    [All][Critical][Warn] |
| Side |                                                        |
| bar  |  +----------------------------------------------+     |
|      |  | [CRITICAL] Drone 3 - Communication Lost       |     |
|      |  | 12:45:30 | Link Loss | Active                 |     |
|      |  +----------------------------------------------+     |
|      |  | [WARNING]  Drone 1 - Battery Below 25%        |     |
|      |  | 12:43:15 | Battery | Active                    |     |
|      |  +----------------------------------------------+     |
|      |  | [INFO]     Wind speed increased to 12 m/s     |     |
|      |  | 12:40:00 | Environment | Resolved              |     |
|      |  +----------------------------------------------+     |
|      |                                                        |
|      |  Alert Statistics                                      |
|      |  +----------------------------------------------+     |
|      |  | [Severity distribution chart]                 |     |
|      |  +----------------------------------------------+     |
+------+-------------------------------------------------------+
```

### 4.8 Settings (/settings)

System configuration (display preferences only — no control logic).

```
+------+-------------------------------------------------------+
|      |  Settings                                              |
| Side |                                                        |
| bar  |  Display                                               |
|      |  +----------------------------------------------+     |
|      |  | Map Style: [Satellite] [Streets] [Dark]       |     |
|      |  | Update Rate: [1 Hz] [2 Hz] [5 Hz]            |     |
|      |  | Units: [Metric] [Imperial]                    |     |
|      |  +----------------------------------------------+     |
|      |                                                        |
|      |  Alert Thresholds (display only)                       |
|      |  +----------------------------------------------+     |
|      |  | Battery Warning: 25%                          |     |
|      |  | Battery Critical: 10%                         |     |
|      |  | GPS Accuracy Warning: 5.0m                    |     |
|      |  +----------------------------------------------+     |
|      |                                                        |
|      |  Connection                                            |
|      |  +----------------------------------------------+     |
|      |  | WebSocket: [Connected / Disconnected]         |     |
|      |  | Last Update: 2s ago                           |     |
|      |  +----------------------------------------------+     |
+------+-------------------------------------------------------+
```

---

## 5. Boundary Rules (ABSOLUTE)

### 5.1 UI May Access

| Source | Access Type | Data |
|--------|-----------|------|
| Digital Twin | Read-only via WebSocket | SwarmState, DroneState, Snapshots |
| Digital Twin | Read-only via REST | Snapshot list, historical data |

### 5.2 UI Must NEVER Access

| System | Reason |
|--------|--------|
| PX4 / SITL | Hardware layer — UI has no direct access |
| ROS2 Bus | Transport layer — UI reads from Digital Twin only |
| MAVLink Bridge | Execution layer — no direct command path |
| Simulation Core | Physical simulation — no direct access |
| Hive Core | Decision authority — UI cannot influence decisions |
| Swarm Planner | Planning layer — UI does not plan |
| Route Planner | Routing layer — UI does not route |
| Fleet Manager | Management layer — UI does not manage |
| Resource Planner | Resource layer — UI does not allocate |
| Optimizer | Optimization layer — UI does not optimize |

### 5.3 UI Must NEVER Contain

| Forbidden Pattern | Reason |
|------------------|--------|
| Decision-making logic | Hive is sole decision authority |
| Route calculation | Planning is Planner's responsibility |
| Drone assignment | Fleet Manager's responsibility |
| Task scheduling | Hive's responsibility |
| Command emission | All commands go through Hive → HAL |
| State mutation | UI is read-only consumer |
| Optimization logic | Optimizer's responsibility |
| Autonomous behavior | No AI/ML in UI layer |

---

## 6. Scalability Strategy

### 6.1 Drone Count Scaling

| Drones | UI Adaptation |
|--------|--------------|
| 1-5 | Individual drone cards, full detail per drone |
| 6-20 | Grid view with summary cards, detail on click |
| 21-50 | Table view with sorting/filtering, mini cards |
| 51-100 | Aggregated views, cluster markers on map |
| 100+ | Heatmap visualization, statistical summaries |

### 6.2 Mission Scaling

| Missions | UI Adaptation |
|----------|--------------|
| Single | Full dashboard dedicated to one mission |
| Multi (2-5) | Tabbed mission panels, shared fleet view |
| Multi (5+) | Mission list with filtering, detail on selection |

### 6.3 Data Volume Scaling

| Strategy | Implementation |
|----------|---------------|
| Viewport culling | Only render visible drones on map |
| Update throttling | Reduce update rate for off-screen elements |
| Snapshot pagination | Load snapshot history in pages |
| Chart windowing | Show last N minutes of telemetry data |
| WebSocket filtering | Server-side filtering of state updates |
