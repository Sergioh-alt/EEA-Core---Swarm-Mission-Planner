# Phase 8 Design Document -- HIVE SYSTEM

## Overview

Phase 8 introduces the **Hive System**, a multi-mission orchestration layer built on top of the existing Phase 0-7 swarm pipeline.

The purpose of this layer is NOT to modify existing swarm behavior, but to coordinate multiple missions, fleets, and resources at a global system level.

---

# CORE DESIGN PRINCIPLE

> Hive orchestrates, it does not replace.

All Phase 0-7 systems remain unchanged and are treated as the execution engine.

Hive only:
- coordinates
- assigns
- tracks state
- manages resources

---

# PHASE 8.1 -- HIVE CORE FOUNDATION [COMPLETED]

## Purpose

Create the global state backbone of the system.

## Implementation

Module: `core/hive.py` | Tests: `tests/test_hive.py` (47 tests) | ADR: ADR-014

---

## Core Components

### 1. HiveState

Central immutable system snapshot built via `build_hive_state(fleet, queue)`.

**Implemented fields:**
- fleet_size, fleet_health (from FleetRegistry)
- missions_queued, missions_executing, missions_completed, missions_failed, missions_cancelled
- system_status: no_fleet / idle / ready / active

**Nature:**
- read-heavy
- immutable dataclass
- deterministic snapshots

---

### 2. MissionQueue

Priority-based mission container.

**Implemented operations:**
- enqueue() -- add mission with priority level
- dequeue() -- return highest-priority QUEUED mission (CRITICAL > HIGH > NORMAL > LOW, FIFO within same)
- peek() -- view next without removing
- cancel() / complete() / fail() -- lifecycle transitions

**Properties:**
- deterministic ordering
- no execution logic
- no optimization logic

---

### 3. FleetRegistry

Global registry of all drones.

**Implemented operations:**
- register_drone() / remove_drone() / get_drone() / update_drone()
- get_available() -- all IDLE drones
- get_by_availability() -- filter by state
- fleet_health_snapshot() -- summary dict

**States:** idle / active / charging / maintenance (DroneAvailability enum)

**Constraints:**
- no allocation logic
- no scheduling logic

---

# PHASE 8.2 -- MISSION ORCHESTRATOR [COMPLETED]

## Purpose

Enable execution of multiple missions using the existing Phase 0-7 pipeline in isolation.

## Implementation

Module: `core/mission_orchestrator.py` | Tests: `tests/test_orchestrator.py` (29 tests) | ADR: ADR-015

## Core Components

### 1. MissionExecutionContext

Isolated container per mission. Holds all pipeline outputs (profile, assessment, swarm, routes, resources, risks, recommendation, timeline). No shared mutable state between contexts.

### 2. MissionLifecycleManager

Registry of execution contexts. Tracks phase transitions (PENDING -> PROFILING -> ... -> COMPLETED/FAILED).

### 3. run_mission()

Executes a single QueuedMission through all 8 pipeline stages:
1. create_mission_profile()
2. analyze_environment()
3. plan_swarm()
4. plan_routes()
5. plan_resources()
6. evaluate_risks()
7. generate_recommendation()
8. generate_timeline()

### 4. run_queue()

Sequential multi-mission execution. Dequeues by priority, runs each in isolation. Failed missions don't block subsequent ones.

---

# PHASE 8.3 -- FLEET MANAGER [COMPLETED]

## Purpose

Drone-level fleet awareness and assignment tracking across missions. State tracking only -- no decision-making.

## Implementation

Module: `core/fleet_manager.py` | Tests: `tests/test_fleet_manager.py` (37 tests) | ADR: ADR-016

## Core Components

### 1. DroneStatusTracker

Wraps FleetRegistry with transition history. Records every state change with reason. Same-state transitions are no-ops (no history entry).

### 2. DroneAllocationManager

Mission-to-drone assignment tracking. Validates IDLE before assignment. Caller decides assignments -- manager only records.

### 3. FleetStateUpdater

Batch operations:
- release_mission_drones() -- release all drones from completed mission
- set_drones_maintenance() / set_drones_charging() -- only from IDLE
- return_drones_idle() -- only from CHARGING/MAINTENANCE
- fleet_assignment_summary() -- read-only snapshot

---

# PHASE 8.4 -- RESOURCE SYSTEM [COMPLETED]

## Purpose

Fleet-wide resource awareness and tracking across missions. Passive state layer -- no allocation decisions.

## Implementation

Module: `core/resource_system.py` | Tests: `tests/test_resource_system.py` (50 tests) | ADR: ADR-017

## Core Components

### 1. BatteryInventoryManager

Battery pool tracking with lifecycle states: AVAILABLE -> IN_USE -> DEPLETED, CHARGING -> AVAILABLE.
- register_battery(), assign_to_drone(), record_consumption(), release_from_drone()
- set_charging(), complete_charging()
- Consumption log per drone/mission

### 2. LiquidInventoryManager

Reservoir tracking with lifecycle states: FULL -> PARTIAL -> EMPTY, REFILLING -> FULL/PARTIAL.
- register_reservoir(), assign_to_drone(), record_consumption(), release_from_drone()
- set_refilling(), complete_refill()
- Consumption log per drone/mission

### 3. ResourceStateTracker

Unified per-drone resource view integrating both managers.
- get_drone_resources() -- battery + liquid state for one drone
- get_fleet_resources() -- all drones
- build_snapshot() -- immutable ResourceSnapshot
- get_mission_consumption() -- per-mission consumption summary

---

# PHASE 8.5 -- HIVE INTEGRATION LAYER [PENDING]

## Purpose

Integrate all Hive components (8.1-8.4) into a unified system.

## Planned:
- system-level orchestration connecting all modules
- communication between Hive modules
- global state consistency

---

# PHASE 8.6 -- VALIDATION & STABILIZATION [PENDING]

## Purpose

Full system validation of the complete Hive layer.

## Planned:
- full regression suite execution
- multi-mission simulation tests
- architecture validation report
- performance sanity checks

---

# STRICT BOUNDARIES (DO NOT VIOLATE)

Phase 8 must NOT include:

- no scheduling algorithms (except queue priority ordering in 8.2)
- no optimization logic
- no planning logic changes
- no modification of Phase 0-7 modules
- no multi-threading / distributed systems complexity
- no hardware abstraction
- no performance tuning logic
- no ML / AI decision-making

---

# REUSE PRINCIPLE

Hive MUST reuse Phase 0-7 execution engine:

- plan_swarm()
- plan_routes()
- generate_timeline()
- evaluate_risks()

Hive does NOT implement alternatives to these systems.

---

# DATA DESIGN PRINCIPLES

## Determinism

All Hive components must produce deterministic outputs given identical inputs.

---

## Opt-in Architecture

Hive must NOT affect system behavior unless explicitly invoked.

---

## Separation of Concerns

- Phase 0-7 -> execution logic
- Phase 8 -> orchestration logic

---

# STATE FLOW (IMPLEMENTED)

Mission Input
-> MissionQueue (8.1) -- priority ordering
-> HiveState snapshot (8.1) -- system visibility
-> FleetRegistry check (8.1) -- drone availability
-> MissionOrchestrator (8.2) -- isolated execution through Phase 0-7 pipeline
-> Fleet Manager (8.3) -- drone assignment tracking
-> Resource System (8.4) -- battery/liquid tracking
-> (8.5: unified integration)

---

# CURRENT STATUS

| Sub-Phase | Status | Module | Tests | ADR |
|---|---|---|---|---|
| 8.1 Hive Core | COMPLETED | core/hive.py | 47 | ADR-014 |
| 8.2 Mission Orchestrator | COMPLETED | core/mission_orchestrator.py | 29 | ADR-015 |
| 8.3 Fleet Manager | COMPLETED | core/fleet_manager.py | 37 | ADR-016 |
| 8.4 Resource System | COMPLETED | core/resource_system.py | 50 | ADR-017 |
| 8.5 Integration Layer | PENDING | -- | -- | -- |
| 8.6 Validation | PENDING | -- | -- | -- |
| **Total** | **4/6 complete** | **4 modules** | **163 tests** | **4 ADRs** |

Total project tests: 403 (all passing). v0.1 backward compatibility: IDENTICAL.

---

# DESIGN INTENT SUMMARY

Phase 8 is a **multi-layer orchestration system**:

It defines:
- how system state is represented (8.1)
- how missions are executed in isolation (8.2)
- how drone assignments are tracked (8.3)
- how resources are monitored (8.4)

Decision-making is centralized in Phase 8.2 only.
Everything else is deterministic state handling.

---
