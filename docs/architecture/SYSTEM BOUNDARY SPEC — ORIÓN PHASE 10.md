SYSTEM BOUNDARY SPEC — ORIÓN PHASE 10

Version: 2.0
Status: Active
Project: Ecosistema Orión

0. GENERAL DEFINITION

This specification defines the strict communication boundaries between all
major subsystems introduced during Phase 10.

System Layers:

Simulation Layer (PX4 SITL)
Hive Core (Decision & Orchestration)
HAL (Hardware Abstraction Layer)
ROS2 Swarm Bus
MAVLink Execution Layer
Digital Twin
UI Ground Control Station (GCS)

Each layer has a single responsibility and may communicate only through
approved contracts.

No implicit coupling is permitted.

────────────────────────────────────────

1. ROS2 MESSAGE SCHEMA (SWARM BUS)

1.1 DroneState.msg

{
  "drone_id": "string",
  "timestamp": "int64",
  "position": {
    "lat": "float",
    "lon": "float",
    "alt": "float"
  },
  "velocity": {
    "vx": "float",
    "vy": "float",
    "vz": "float"
  },
  "battery": {
    "percentage": "float",
    "voltage": "float"
  },
  "state": "IDLE | ACTIVE | RETURNING | CHARGING | FAIL",
  "health": "OK | WARNING | CRITICAL"
}

1.2 SwarmState.msg

{
  "mission_id": "string",
  "active_drones": ["drone_id"],
  "completed_tasks": ["task_id"],
  "pending_tasks": ["task_id"],
  "global_coverage": "float",
  "timestamp": "int64"
}

1.3 Event.msg

{
  "event_type": "FAILURE | BATTERY_LOW | GEO_ALERT | PLAGUE_DETECTED",
  "source": "drone_id",
  "severity": "LOW | MEDIUM | HIGH",
  "payload": {},
  "timestamp": "int64"
}

────────────────────────────────────────

2. MAVLINK COMMAND ENVELOPE

2.1 CommandSchema

{
  "command_id": "string",
  "drone_id": "string",
  "command_type":
      "TAKEOFF | LAND | GOTO | SPRAY | HOVER | RTH",

  "params": {
      "lat":"float",
      "lon":"float",
      "alt":"float",
      "duration":"float",
      "intensity":"float"
  },

  "priority":
      "LOW | NORMAL | HIGH | EMERGENCY",

  "ack_required": true,
  "timeout_ms": 3000
}

2.2 ExecutionResult

{
  "command_id":"string",
  "status":"ACK | NACK | TIMEOUT",
  "drone_state":"string",
  "error":"string | null",
  "timestamp":"int64"
}

Critical Rule

No command may be considered executed without an ACK from the lower layer.

────────────────────────────────────────

3. DIGITAL TWIN STATE MODEL

3.1 Single Source of Truth

The Digital Twin is the only authoritative runtime representation exposed
to the frontend.

Sources:

• HAL telemetry
• Simulation telemetry
• Hive mission state

Priority:

1. HAL
2. Simulation
3. Hive prediction

3.2 Synchronization Rules

Simulation NEVER overrides the Twin directly.

Twin MAY reconcile simulation drift.

Every state update:

• timestamped
• immutable
• deterministic

3.3 Replay System

Replay SHALL reconstruct:

Mission state

Fleet state

Drone states

Alerts

Timeline

Failures

bit-by-bit.

────────────────────────────────────────

4. UI DATA CONTRACT

The UI communicates ONLY with the Digital Twin.

Never:

ROS2

HAL

PX4

MAVLink

Hive

directly.

4.1 UI State

{
  "fleet": [],
  "missions": [],
  "alerts": [],
  "telemetry_stream": [],
  "map_layers": [],
  "simulation_time": "int64",
  "selected_drone":"string"
}

4.2 UI Rules

The UI:

✓ visualizes

✓ submits intents

✓ renders telemetry

✓ renders replay

✓ renders analytics

The UI NEVER:

calculates routes

assigns drones

optimizes missions

changes Twin state

writes ROS2

sends MAVLink

4.3 Intent Layer

{
    "intent_type":
        "START_MISSION |
         PAUSE |
         STOP |
         REPLAY",

    "payload":{},
    "user_id":"string",
    "timestamp":"int64"
}

────────────────────────────────────────

5. UI IMPLEMENTATION PHASES

The frontend is divided into five implementation stages.

Phase 10C.1

UI Architecture

Navigation

Contracts

Data Flow

Interaction Model

Scalability

Phase 10C.2

UI Foundation

Next.js

Theme

Layout

Stores

Shared Components

REST

WebSocket Clients

Phase 10C.3

Mission Control UI

Dashboard

Fleet

Mission

Deployment

Replay

Analytics

Alerts

Settings

Mission Control

Operational panels

Phase 10C.4

Advanced UI Integration

Digital Twin synchronization

Live telemetry

Replay timeline

Map layers

Real mission visualization

Historical playback

Performance optimization

Responsive refinement

Phase 10C.5

System Validation

Frontend validation

Boundary validation

Performance

WebSocket

REST

Responsive

Replay

End-to-end verification

────────────────────────────────────────

6. CROSS-LAYER BOUNDARY RULES

Simulation

Cannot modify Hive.

Hive

Cannot render UI.

Cannot execute MAVLink directly.

HAL

Cannot perform decision making.

ROS2

Transport only.

No logic.

MAVLink

Execution only.

Digital Twin

Cannot execute commands.

UI

Cannot bypass Intent Layer.

Cannot mutate runtime state.

────────────────────────────────────────

7. SYSTEM DATA FLOW

Correct execution flow

Hive

↓

HAL

↓

MAVLink

↓

Simulation / Real Drone

↓

Telemetry

↓

ROS2

↓

Digital Twin

↓

UI

Operator interaction

UI

↓

Intent Layer

↓

Hive

────────────────────────────────────────

8. VALIDATION REQUIREMENTS

Every Phase 10 subphase shall pass:

Architecture isolation

Cross-layer leak scan

Regression

Schema validation

Boundary validation

Manual UI validation

Fresh-clone validation

End-to-end validation

────────────────────────────────────────

9. SUCCESS CRITERIA

The architecture is considered valid only if:

0 boundary leaks

0 forbidden imports

Digital Twin remains the only frontend source

Simulation is deterministic

Replay is deterministic

Hive remains sole decision authority

UI remains visualization-only

HAL remains execution-only

System is hardware-ready.
