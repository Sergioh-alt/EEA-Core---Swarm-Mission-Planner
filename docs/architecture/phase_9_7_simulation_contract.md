# Phase 9.7 — Simulation Layer Contract (SLC)

## Status: ACTIVE DESIGN CONSTRAINT

---

## Purpose

Defines the architectural contract for the Simulation Layer. The simulation environment exists exclusively for testing and validation — it must never influence runtime decision-making, modify system state, or bypass HAL boundaries.

---

## Core Principle

**Simulation = READ-ONLY Telemetry Mirror**

The simulation layer mirrors HAL schemas exactly. It produces telemetry data for testing purposes only and consumes commands without side effects on planning or orchestration layers.

---

## Contract Rules

### 1. Schema Mirroring

The simulation layer MUST use the exact HAL schemas:

| HAL Schema | Simulation Usage | Constraint |
|-----------|-----------------|------------|
| `CommandSchema` | Input — receives commands | MIRROR ONLY — no extensions |
| `CommandType` | Enum — 10 command types | EXACT MATCH — no additions |
| `TelemetrySchema` | Output — produces telemetry | MIRROR ONLY — no extensions |
| `FlightState` | Enum — 9 flight states | EXACT MATCH — no additions |
| `ExecutionResult` | Output — command results | MIRROR ONLY — no extensions |
| `ExecutionStatus` | Enum — 5 statuses | EXACT MATCH — no additions |

Implementation reference: `SimulationAdapter` in `core/hal_adapters.py` already satisfies this contract by importing all schemas from `core/hal_interfaces.py`.

### 2. Read-Only Telemetry

| Rule | Description |
|------|-------------|
| SLC-R1 | Simulation telemetry is read-only to all consuming layers |
| SLC-R2 | No simulation output may modify Hive mission state |
| SLC-R3 | No simulation output may trigger planning recalculation |
| SLC-R4 | No simulation output may alter resource allocation |

### 3. Forbidden Behaviors

| ID | Forbidden Behavior | Reason |
|----|-------------------|--------|
| SLC-F1 | Decision-making logic | Simulation must not decide |
| SLC-F2 | Hive state modification | Simulation is isolated from orchestration |
| SLC-F3 | Planning influence | Simulation must not affect route/swarm planning |
| SLC-F4 | Runtime state mutation | Simulation operates in its own state space |
| SLC-F5 | Direct UI writes | UI reads from Digital Twin, not simulation directly |

### 4. Import Boundaries

| Simulation May Import | Simulation Must NOT Import |
|----------------------|--------------------------|
| `core.hal_interfaces` | `core.hive` |
| stdlib modules | `core.hive_integration` |
| | `core.mission_orchestrator` |
| | `core.fleet_manager` |
| | `core.resource_system` |
| | `core.swarm_planner` |
| | `core.route_planner` |
| | `core.decision_engine` |
| | Any Phase 0–8 module |

### 5. Current Implementation Status

The `SimulationAdapter` in `core/hal_adapters.py` satisfies SLC by:

- Implementing `BaseDroneInterface` (schema mirroring)
- Importing only from `core.hal_interfaces` (import isolation)
- Maintaining in-memory state only (no persistence)
- Applying commands mechanically (no decision logic)
- Producing `TelemetrySchema` output (read-only telemetry)

---

## Verification

SLC compliance is verified by:

1. `HALStaticAnalyzer` — forbidden import detection
2. `BoundaryViolationDetector` — domain-specific boundary checks
3. `TestAdapterCompliance` — AST-based compliance tests
4. `TestAdapterLock` — boundary lock verification

---

## SLC Freeze

This contract is frozen as of Phase 9.7. Any future simulation extensions (Phase 10+) must comply with all SLC rules without modification to the contract itself.
