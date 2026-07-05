# Phase 10C.1 — UI Contracts

**Status:** DESIGN SPECIFICATION  

---

## 1. TypeScript Type Contracts

These types mirror the Digital Twin Python models exactly. The UI consumes these as read-only data.

### 1.1 Enumerations

```typescript
enum MissionStatus {
  IDLE = "IDLE",
  RUNNING = "RUNNING",
  PAUSED = "PAUSED",
  FAILED = "FAILED",
  COMPLETED = "COMPLETED",
}

enum DroneMode {
  STANDBY = "STANDBY",
  MANUAL = "MANUAL",
  GUIDED = "GUIDED",
  AUTO = "AUTO",
  RTL = "RTL",
  LAND = "LAND",
}

enum HealthLevel {
  OK = "OK",
  WARNING = "WARNING",
  CRITICAL = "CRITICAL",
}

enum TaskState {
  NONE = "NONE",
  IN_PROGRESS = "IN_PROGRESS",
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
}

enum FailureCategory {
  BATTERY_DEGRADATION = "battery_degradation",
  GPS_LOSS = "gps_loss",
  LINK_LOSS = "link_loss",
  WIND_DISTURBANCE = "wind_disturbance",
}

enum EnvironmentCondition {
  NOMINAL = "NOMINAL",
  DEGRADED = "DEGRADED",
  SEVERE = "SEVERE",
}
```

### 1.2 Data Models

```typescript
interface Position {
  latitude: number;
  longitude: number;
  altitude_m: number;
}

interface Velocity {
  vx: number;
  vy: number;
  vz: number;
}

interface DroneState {
  drone_id: number;
  armed: boolean;
  mode: DroneMode;
  position: Position;
  velocity: Velocity;
  heading_deg: number;
  battery_pct: number;
  battery_voltage: number;
  gps_available: boolean;
  gps_accuracy_m: number;
  communication_active: boolean;
  health: HealthLevel;
  current_task: TaskState;
  last_update_ms: number;
}

interface EnvironmentState {
  wind_speed_m_s: number;
  wind_direction_deg: number;
  condition: EnvironmentCondition;
  timestamp_ms: number;
}

interface SwarmState {
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
}
```

### 1.3 Snapshot & Replay Models

```typescript
interface Snapshot {
  snapshot_id: string;
  version: number;
  timestamp_ms: number;
  swarm_state: SwarmState;
  description: string;
}

interface ReplayFrame {
  frame_index: number;
  timestamp_ms: number;
  swarm_state: SwarmState;
}

interface DroneReplayFrame {
  frame_index: number;
  timestamp_ms: number;
  drone_state: DroneState;
}

interface ReplayTimeline {
  timeline_id: string;
  start_ms: number;
  end_ms: number;
  frames: ReplayFrame[];
  total_frames: number;
  description: string;
}

interface DroneReplayTimeline {
  drone_id: number;
  timeline_id: string;
  start_ms: number;
  end_ms: number;
  frames: DroneReplayFrame[];
  total_frames: number;
}
```

### 1.4 Alert Model

```typescript
interface Alert {
  id: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  source: string;               // drone_id or "system"
  message: string;
  category: FailureCategory | "SYSTEM" | "ENVIRONMENT";
  timestamp_ms: number;
  active: boolean;
  resolved_ms: number | null;
}
```

### 1.5 Intent Model

```typescript
interface UIIntent {
  intent_type: "START_MISSION" | "PAUSE" | "STOP" | "REPLAY";
  payload: Record<string, unknown>;
  user_id: string;
  timestamp_ms: number;
}

interface IntentResult {
  intent_type: string;
  accepted: boolean;
  reason: string | null;
  timestamp_ms: number;
}
```

---

## 2. Contract Rules

### 2.1 Immutability Contract

| Rule | Enforcement |
|------|------------|
| UI never modifies received `SwarmState` | TypeScript `Readonly<>` types |
| UI never modifies received `DroneState` | Object.freeze() on receipt |
| Stores produce new state on update | Zustand immutable updates |
| Components receive readonly props | React prop types |

### 2.2 Schema Consistency Contract

| Python Model | TypeScript Type | Validation |
|-------------|----------------|------------|
| `digital_twin.state_models.SwarmState` | `SwarmState` | Fields match 1:1 |
| `digital_twin.state_models.DroneState` | `DroneState` | Fields match 1:1 |
| `digital_twin.state_models.Position` | `Position` | Fields match 1:1 |
| `digital_twin.state_models.Velocity` | `Velocity` | Fields match 1:1 |
| `digital_twin.state_models.EnvironmentState` | `EnvironmentState` | Fields match 1:1 |
| `digital_twin.snapshot_engine.Snapshot` | `Snapshot` | Fields match 1:1 |
| `digital_twin.replay_engine.ReplayFrame` | `ReplayFrame` | Fields match 1:1 |
| `digital_twin.replay_engine.ReplayTimeline` | `ReplayTimeline` | Fields match 1:1 |

Any change to the Python models MUST be reflected in the TypeScript types.

### 2.3 Read-Only Contract

| ID | Rule |
|----|------|
| UI-C1 | UI components accept `Readonly<SwarmState>` |
| UI-C2 | Stores never expose setters to components |
| UI-C3 | No component may call Digital Twin sync methods |
| UI-C4 | No component may construct `DroneStateUpdate` |
| UI-C5 | No component may construct `SwarmStateUpdate` |
| UI-C6 | `fetch` calls use GET only (except intent POST) |

### 2.4 Import Boundary Contract

| UI May Import | UI Must NOT Import |
|--------------|-------------------|
| `contracts/types.ts` (local TS types) | `digital_twin/*` (Python modules) |
| `contracts/events.ts` | `simulation/*` |
| `contracts/intents.ts` | `core/*` |
| React / Next.js / Zustand | `pymavlink` |
| Mapbox GL / Recharts | ROS2 libraries |
| Tailwind CSS | Any Python module |

---

## 3. API Contracts

### 3.1 REST API Contract

```
GET  /api/twin/state
  Response: SwarmState (JSON)
  Rate limit: none (cached at 1s)

GET  /api/twin/drone/:id
  Response: DroneState (JSON)
  404 if drone not registered

GET  /api/twin/snapshots
  Response: { snapshots: SnapshotMetadata[] }
  SnapshotMetadata = { snapshot_id, version, timestamp_ms, description }

GET  /api/twin/snapshots/:id
  Response: Snapshot (full, including SwarmState)
  404 if snapshot not found

POST /api/twin/replay
  Body: { start_version?: number, end_version?: number, description?: string }
  Response: ReplayTimeline (JSON)

POST /api/twin/replay/drone/:id
  Body: { start_version?: number, end_version?: number }
  Response: DroneReplayTimeline (JSON)

GET  /api/twin/version
  Response: { version: number }

POST /api/intents
  Body: UIIntent (JSON)
  Response: IntentResult (JSON)
```

### 3.2 WebSocket Contract

```
Endpoint: ws://host:port/ws/twin

Client → Server:
  { type: "subscribe_drone", drone_id: number, frequency_hz: number }
  { type: "unsubscribe_drone", drone_id: number }
  { type: "refresh" }

Server → Client:
  { type: "swarm_state", data: SwarmState }
  { type: "drone_delta", data: { drone_id, changes, timestamp_ms } }
  { type: "alert", data: Alert }
  { type: "connection", data: { status, latency_ms } }
```
