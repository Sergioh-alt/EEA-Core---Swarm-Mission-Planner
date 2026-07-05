# Phase 10C.1 — Data Flow & State Management

**Status:** DESIGN SPECIFICATION  

---

## 1. System Data Flow Diagram

```
                    SYSTEM DATA FLOW (STRICT)
                    =========================

  [Hive]                    DECISION AUTHORITY
    |
    v
  [HAL]                     EXECUTION + TRANSLATION
    |
    v
  [MAVLink Bridge]          COMMAND ENVELOPE
    |
    v
  [PX4 SITL / Drone]       PHYSICAL EXECUTION
    |
    v (telemetry)
  [ROS2 Swarm Bus]          STATE TRANSPORT (no logic)
    |
    v
  [Digital Twin]            SINGLE SOURCE OF TRUTH
    |                       - SyncEngine
    |                       - SnapshotEngine
    |                       - ReplayEngine
    |
    +-----> [WebSocket Server]    REAL-TIME STREAM
    |             |
    |             v
    |       [UI WebSocket Client]
    |             |
    |             v
    |       [Zustand Stores]      CLIENT STATE
    |             |
    |             v
    |       [React Components]    VISUALIZATION
    |
    +-----> [REST API]            ON-DEMAND QUERIES
                  |
                  v
            [UI Fetch/SWR]
                  |
                  v
            [React Components]
```

---

## 2. Digital Twin → UI Data Flow

### 2.1 Real-Time Channel (WebSocket)

The primary data channel. Pushes state updates from Digital Twin to UI at configured frequency.

```
Digital Twin                 WebSocket Server              UI Client
    |                              |                          |
    | SwarmState (immutable)       |                          |
    |----------------------------->|                          |
    |                              | serialize to JSON        |
    |                              |------------------------->|
    |                              |                          | parse
    |                              |                          | update Zustand store
    |                              |                          | React re-renders
    |                              |                          |
    | DroneState[] (per tick)      |                          |
    |----------------------------->|                          |
    |                              | diff + delta update      |
    |                              |------------------------->|
    |                              |                          | merge into store
    |                              |                          |
    | Alert event                  |                          |
    |----------------------------->|                          |
    |                              | push notification        |
    |                              |------------------------->|
    |                              |                          | add to alert queue
```

### 2.2 On-Demand Channel (REST API)

For non-streaming queries: snapshot lists, replay data, historical lookups.

```
Endpoint                          Method   Response
/api/twin/state                   GET      Current SwarmState
/api/twin/drone/{id}              GET      DroneState for drone
/api/twin/snapshots               GET      List of Snapshot metadata
/api/twin/snapshots/{id}          GET      Full Snapshot with SwarmState
/api/twin/replay                  POST     ReplayTimeline for version range
/api/twin/replay/drone/{id}       POST     DroneReplayTimeline
/api/twin/version                 GET      Current state version
/api/intents                      POST     Submit operator intent
```

### 2.3 Intent Channel (UI → Backend)

The **only** write path from UI. Intents are submitted to the backend, which routes them to Hive. The UI never communicates directly with Hive, HAL, or any execution layer.

```
UI                        Backend Intent Handler           Hive
  |                              |                          |
  | Intent: START_MISSION        |                          |
  |----------------------------->|                          |
  |                              | validate intent          |
  |                              | route to Hive            |
  |                              |------------------------->|
  |                              |                          | decide
  |                              |                          | (Hive authority)
  |                              | ack/nack                 |
  |                              |<-------------------------|
  | intent_result                |                          |
  |<-----------------------------|                          |
  | update UI state              |                          |
```

**Intent Types:**

| Intent | Payload | Notes |
|--------|---------|-------|
| `START_MISSION` | `{ mission_id }` | Request mission start |
| `PAUSE_MISSION` | `{ mission_id }` | Request mission pause |
| `STOP_MISSION` | `{ mission_id }` | Request mission abort |
| `REPLAY` | `{ start_version, end_version }` | Request replay (read-only) |

The UI does NOT decide whether to start/pause/stop — it submits an intent. Hive decides.

---

## 3. WebSocket Message Protocol

### 3.1 Server → Client Messages

```typescript
// Full state update (sent at configured Hz)
interface SwarmStateMessage {
  type: "swarm_state";
  data: {
    swarm_id: string;
    timestamp_ms: number;
    mission_status: MissionStatus;
    mission_id: string | null;
    simulation_time_ms: number;
    drone_states: DroneState[];
    global_health: HealthLevel;
    active_failures: FailureCategory[];
    environment_state: EnvironmentState;
    total_drones: number;
    active_drones: number;
    failed_drones: number;
    version: number;
  };
}

// Drone state delta (sent when individual drone changes)
interface DroneStateDelta {
  type: "drone_delta";
  data: {
    drone_id: number;
    changes: Partial<DroneState>;
    timestamp_ms: number;
  };
}

// Alert notification
interface AlertMessage {
  type: "alert";
  data: {
    id: string;
    severity: "INFO" | "WARNING" | "CRITICAL";
    source: string;
    message: string;
    category: string;
    timestamp_ms: number;
    active: boolean;
  };
}

// Connection status
interface ConnectionMessage {
  type: "connection";
  data: {
    status: "connected" | "reconnecting" | "disconnected";
    latency_ms: number;
  };
}
```

### 3.2 Client → Server Messages

```typescript
// Subscribe to specific drone updates
interface SubscribeDrone {
  type: "subscribe_drone";
  drone_id: number;
  frequency_hz: number;  // e.g., 2 for drone detail page
}

// Unsubscribe from drone
interface UnsubscribeDrone {
  type: "unsubscribe_drone";
  drone_id: number;
}

// Request full state refresh
interface RefreshRequest {
  type: "refresh";
}
```

---

## 4. Client State Management (Zustand)

### 4.1 Store Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Zustand Stores                     │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ swarmStore    │  │ droneStore   │                 │
│  │              │  │              │                 │
│  │ swarmState   │  │ droneStates  │                 │
│  │ version      │  │ selected     │                 │
│  │ lastUpdate   │  │ histories    │                 │
│  └──────────────┘  └──────────────┘                 │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ missionStore │  │ alertStore   │                 │
│  │              │  │              │                 │
│  │ missionId    │  │ alerts[]     │                 │
│  │ status       │  │ unreadCount  │                 │
│  │ progress     │  │ filters      │                 │
│  │ events[]     │  │              │                 │
│  └──────────────┘  └──────────────┘                 │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ replayStore  │  │ connectionSt │                 │
│  │              │  │              │                 │
│  │ timeline     │  │ status       │                 │
│  │ currentFrame │  │ latency      │                 │
│  │ speed        │  │ lastPing     │                 │
│  │ playing      │  │              │                 │
│  └──────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────┘
```

### 4.2 Store Definitions

```typescript
// swarmStore.ts
interface SwarmStore {
  // State (from Digital Twin)
  swarmState: SwarmState | null;
  version: number;
  lastUpdateMs: number;

  // Actions (internal only — triggered by WebSocket)
  setSwarmState: (state: SwarmState) => void;
}

// droneStore.ts
interface DroneStore {
  // State
  droneStates: Map<number, DroneState>;
  selectedDroneId: number | null;
  droneHistories: Map<number, DroneState[]>;  // last N states

  // Actions
  updateDrone: (id: number, state: DroneState) => void;
  selectDrone: (id: number | null) => void;
}

// missionStore.ts
interface MissionStore {
  // State
  missionId: string | null;
  missionStatus: MissionStatus;
  coveragePct: number;
  events: MissionEvent[];

  // Actions
  setMissionState: (status: MissionStatus, id: string | null) => void;
  addEvent: (event: MissionEvent) => void;
}

// alertStore.ts
interface AlertStore {
  // State
  alerts: Alert[];
  unreadCount: number;
  activeFilter: AlertSeverity | null;

  // Actions
  addAlert: (alert: Alert) => void;
  markRead: (id: string) => void;
  setFilter: (severity: AlertSeverity | null) => void;
}

// replayStore.ts
interface ReplayStore {
  // State
  timeline: ReplayTimeline | null;
  currentFrame: number;
  playing: boolean;
  speed: number;  // 0.5, 1, 2, 4

  // Actions
  loadTimeline: (timeline: ReplayTimeline) => void;
  setFrame: (index: number) => void;
  play: () => void;
  pause: () => void;
  setSpeed: (speed: number) => void;
}

// connectionStore.ts
interface ConnectionStore {
  // State
  status: "connected" | "reconnecting" | "disconnected";
  latencyMs: number;
  lastPingMs: number;

  // Actions
  setStatus: (status: string) => void;
  setLatency: (ms: number) => void;
}
```

### 4.3 Data Flow Through Stores

```
WebSocket Message arrives
    |
    v
ws-client.ts (parse message)
    |
    +-- type: "swarm_state"    → swarmStore.setSwarmState(data)
    |                            droneStore.updateDrone(each drone)
    |                            missionStore.setMissionState(...)
    |
    +-- type: "drone_delta"    → droneStore.updateDrone(id, changes)
    |
    +-- type: "alert"          → alertStore.addAlert(data)
    |
    +-- type: "connection"     → connectionStore.setStatus(status)
    |
    v
React components re-render (selector-based subscriptions)
```

---

## 5. Update Frequency Strategy

| Data Type | Frequency | Transport | Notes |
|-----------|-----------|-----------|-------|
| SwarmState (full) | 1 Hz | WebSocket | Complete state snapshot |
| DroneState (selected) | 2 Hz | WebSocket | Higher rate when viewing detail |
| DroneState (background) | 1 Hz | WebSocket | Standard rate for fleet view |
| Alerts | Event-driven | WebSocket | Pushed immediately on occurrence |
| Snapshots list | On-demand | REST | Fetched when entering replay page |
| Replay frames | On-demand | REST | Fetched when replay requested |
| Settings | Static | Local | No server communication |

### 5.1 Adaptive Update Rate

```
When user is on Dashboard or Fleet:
  → Stream full SwarmState at 1 Hz
  → Include all DroneStates

When user navigates to Drone Detail:
  → Subscribe to specific drone at 2 Hz
  → Maintain 1 Hz for rest of swarm

When user navigates to Map:
  → Stream positions only at 2 Hz (lightweight)
  → Full state on demand

When user is on Replay:
  → Pause live updates (or reduce to 0.5 Hz)
  → Serve replay frames from REST
```

---

## 6. Error Handling & Reconnection

### 6.1 WebSocket Reconnection

```
Connection lost
  → connectionStore.status = "reconnecting"
  → UI shows "Reconnecting..." badge (amber)
  → Exponential backoff: 1s, 2s, 4s, 8s, max 30s
  → On reconnect: request full state refresh
  → connectionStore.status = "connected"
  → UI shows "LIVE" badge (green)
```

### 6.2 Stale Data Detection

```
If no update received for >5 seconds:
  → UI shows "Data Stale" warning
  → Values shown with reduced opacity
  → Timestamps show "Last update: Xs ago"
```

### 6.3 Data Consistency

```
On each SwarmState update:
  → Compare version with stored version
  → If version gap > 1: request full refresh (missed update)
  → If version == stored: skip (duplicate)
  → If version < stored: discard (out of order)
```
