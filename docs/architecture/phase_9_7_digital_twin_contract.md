# Phase 9.7 — Digital Twin Contract (DTC)

## Status: ACTIVE DESIGN CONSTRAINT

---

## Purpose

Defines the architectural contract for the Digital Twin layer — the single source of truth for system state visualization. The Digital Twin reconciles data from multiple sources with deterministic priority rules and provides a read-only view to the UI layer.

---

## Core Principle

**Digital Twin = Read-Only State Reconciliation Layer**

The Digital Twin aggregates state from HAL telemetry, simulation telemetry, and Hive predicted state into a single consistent view. It never emits commands, modifies system state, or influences decisions.

---

## Contract Rules

### 1. Single Source of Truth

The Digital Twin is the ONLY source of truth for:

| Data | Source |
|------|--------|
| Drone positions | Reconciled from telemetry sources |
| Fleet status | Aggregated from telemetry frames |
| Mission progress | Derived from task states |
| System health | Derived from emergency signals |

### 2. Read-Only Contract

| ID | Rule |
|----|------|
| DTC-R1 | Digital Twin is read-only for all consuming layers |
| DTC-R2 | UI layer reads from Digital Twin, never writes |
| DTC-R3 | Digital Twin cannot emit commands to HAL or adapters |
| DTC-R4 | Digital Twin cannot modify Hive mission state |
| DTC-R5 | Digital Twin cannot trigger planning recalculation |
| DTC-R6 | Digital Twin cannot influence resource allocation |

### 3. Data Reconciliation Priority

When multiple data sources provide conflicting state, the Digital Twin resolves conflicts using deterministic priority:

| Priority | Source | Rationale |
|----------|--------|-----------|
| 1 (Highest) | HAL real telemetry | Ground truth from hardware |
| 2 | Simulation telemetry | Best available when no hardware |
| 3 (Lowest) | Hive predicted state | Planning estimate, may diverge |

Reconciliation rules:

| ID | Rule |
|----|------|
| DTC-P1 | If HAL real telemetry is available, it overrides all other sources |
| DTC-P2 | If HAL real telemetry is unavailable, simulation telemetry is used |
| DTC-P3 | Hive predicted state is used only when no telemetry source is available |
| DTC-P4 | Priority resolution is deterministic — same inputs always produce same output |
| DTC-P5 | No weighted averaging or fuzzy reconciliation — strict priority override |

### 4. Schema Consistency

The Digital Twin consumes these HAL schemas without modification:

| Schema | Usage | Constraint |
|--------|-------|-----------|
| `DroneTelemetryFrame` | Per-drone state | CONSUMED AS-IS |
| `FleetTelemetrySnapshot` | Fleet-wide state | CONSUMED AS-IS |
| `TaskState` | Drone activity state | CONSUMED AS-IS |
| `GPSFixQuality` | GPS quality | CONSUMED AS-IS |
| `EmergencySignal` | Emergency events | CONSUMED AS-IS |

No schema extensions or modifications are permitted.

### 5. Forbidden Behaviors

| ID | Forbidden Behavior | Reason |
|----|-------------------|--------|
| DTC-F1 | Command emission | Digital Twin is read-only |
| DTC-F2 | State mutation | No writes to any system layer |
| DTC-F3 | Decision-making | No intelligence in visualization |
| DTC-F4 | Prediction | No forecasting or trend analysis |
| DTC-F5 | Recommendation | No suggested actions |
| DTC-F6 | Direct hardware access | Must go through HAL |
| DTC-F7 | Cross-mission data merging | Each mission viewed independently |

### 6. Import Boundaries

| Digital Twin May Import | Digital Twin Must NOT Import |
|------------------------|----------------------------|
| `core.hal_interfaces` (schemas) | `core.hive` (state mutation) |
| `core.hal_telemetry` (frames) | `core.hive_integration` |
| `core.hal_safety` (signals) | `core.mission_orchestrator` |
| stdlib modules | `core.fleet_manager` |
| | `core.resource_system` |
| | `core.swarm_planner` |
| | `core.route_planner` |
| | `core.decision_engine` |

---

## Current Implementation Status

The Digital Twin contract is defined as an architectural specification. The current system satisfies DTC requirements through:

1. **Telemetry layer** (`hal_telemetry.py`) — produces `DroneTelemetryFrame` and `FleetTelemetrySnapshot` as read-only state
2. **UI layer** (`ui/`) — reads from planning pipeline output, does not write to HAL or Hive
3. **Import boundaries** — UI imports only from Phase 0–7 planning modules (data types), not from HAL or Hive mutation methods

Phase 10+ may implement a dedicated Digital Twin module that formally implements this contract.

---

## UI Layer Contract (Derived from DTC)

The UI layer has its own derived constraints:

| Rule | Constraint |
|------|-----------|
| UI-R1 | UI reads planning results only (Phase 0–7 output types) |
| UI-R2 | UI does not import HAL modules directly |
| UI-R3 | UI does not import Hive mutation methods |
| UI-R4 | UI does not call `send_command()` or any adapter method |
| UI-R5 | UI rendering is stateless — no cross-request state |

Current compliance: The UI layer (`ui/*.py`) imports only data types (`FieldGeometry`, `MissionRecommendation`, `SwarmPlan`, `RoutePlan`, etc.) for rendering. It does not import or call any HAL or Hive mutation methods.

---

## Verification

DTC compliance is verified by:

1. Import isolation tests — UI does not import HAL/Hive mutation
2. Schema consistency tests — telemetry schemas match
3. Cross-layer leak detection — no UI → HAL direct calls
4. Architecture validation — read-only data flow

---

## DTC Freeze

This contract is frozen as of Phase 9.7. A formal Digital Twin module may be implemented in Phase 10+ following this contract without modifications.
