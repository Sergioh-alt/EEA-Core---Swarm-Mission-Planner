# Decision Boundary Map -- Phase 8 (Hive System)

## Purpose

This document defines strict decision-making boundaries across the Phase 8 architecture.

Its goal is to prevent unintended optimization, implicit scheduling, or emergent decision-making behavior inside orchestration components.

---

# CORE PRINCIPLE

> Only one layer in the system is allowed to make decisions:
> the Mission Orchestrator (Phase 8.2).

All other components are strictly stateful or structural.

---

# DECISION RESPONSIBILITY MATRIX

## Phase 0-7 (Execution Engine)

### Decision-making: NOT ALLOWED

These modules only execute deterministic logic:
- plan_swarm()
- plan_routes()
- generate_timeline()
- evaluate_risks()

They compute outputs.
They do NOT decide assignments or priorities.

---

## Phase 8.1 -- Hive Core Foundation [COMPLETED]

### Decision-making: NOT ALLOWED

Components:
- HiveState (`build_hive_state()`)
- MissionQueue (priority ordering only -- FIFO within same priority)
- FleetRegistry (state registry only)

### Role:
- state representation only
- storage and retrieval only

Verified: No logic inference, no prioritization decisions, no allocation decisions.

Implementation: `core/hive.py` | 47 tests | ADR-014

---

## Phase 8.2 -- Mission Orchestrator [COMPLETED]

### LIMITED DECISION AUTHORITY

Allowed decisions:
- mission execution order (based on queue priority only)
- which mission runs next (dequeue from MissionQueue)
- execution flow control (sequential pipeline stages)

NOT allowed:
- drone selection optimization
- resource balancing
- performance-based assignment
- adaptive planning

Implementation: `core/mission_orchestrator.py` | 29 tests | ADR-015

---

## Phase 8.3 -- Fleet Manager [COMPLETED]

### DECISION MAKING STRICTLY FORBIDDEN

Fleet Manager MUST NOT decide:

- which drone is better
- which mission gets which drone
- any form of ranking or scoring

### Allowed ONLY:
- register assignment (external decision input)
- track drone state transitions
- report availability
- batch state updates (release, maintenance, charging)

> Fleet Manager = Passive registry, NOT allocator

Verified: DroneAllocationManager requires caller to specify drone_id and mission_id explicitly.
No ranking, scoring, or selection logic exists.

Implementation: `core/fleet_manager.py` | 37 tests | ADR-016

---

## Phase 8.4 -- Resource System [COMPLETED]

### Decision-making: NOT ALLOWED

Resource System MUST NOT decide:

- which drone receives which battery
- which mission receives resources
- how resources should be distributed
- charging or refill priority

### Allowed ONLY:
- track battery state (available / in_use / charging / depleted)
- track liquid state (full / partial / empty / refilling)
- record consumption events per drone/mission
- report resource availability via snapshots

> Resource System = Passive state layer, NOT allocator

Verified: BatteryInventoryManager and LiquidInventoryManager require caller to
specify all assignments. No ranking, scoring, optimization, or allocation logic.

Implementation: `core/resource_system.py` | 50 tests | ADR-017

---

## Phase 8.5 -- Integration Layer [COMPLETED]

### Decision-making: NOT ALLOWED

Components:
- HiveRuntime (component lifecycle container)
- HiveController (unified entry point -- delegates only)
- HiveSystemSnapshot (read-only state aggregation)

Verified: No select_drone, allocate_resources, optimize, schedule, balance, rank, or recommend methods exist. AST inspection + attribute checks passed.

Implementation: `core/hive_integration.py` | 36 tests | ADR-018

---

## Phase 8.6 -- Validation Layer [COMPLETED]

### Decision-making: NOT ALLOWED

- evaluates system correctness only
- no runtime influence
- 33 validation tests including code-level decision boundary compliance
- Full decision boundary compliance report generated

---

# FORBIDDEN PATTERNS (SYSTEM-WIDE)

Any of the following indicates architecture violation:

- "best drone selection"
- "optimal assignment"
- "load balancing"
- "efficiency scoring"
- "automatic reallocation"
- "smart scheduling"
- "resource prioritization"
- "charging optimization"
- "refill optimization"

---

# SAFE PATTERN (CORRECT DESIGN)

Decisions happen ONLY in Phase 8.2.

Example flow:

```
Mission Orchestrator (8.2) decides:
  -> assign Drone A to Mission 1

Fleet Manager (8.3) records:
  -> Drone A = Mission 1 (IDLE -> ACTIVE)

Resource System (8.4) records:
  -> Battery 101 assigned to Drone A
  -> Liquid reservoir 201 assigned to Drone A

After mission completion:
Fleet Manager (8.3) records:
  -> Drone A released (ACTIVE -> IDLE)

Resource System (8.4) records:
  -> Battery 101 consumed 40%, released
  -> Reservoir 201 consumed 6L, released
```

---

# COMPLIANCE STATUS

| Phase | Decision Authority | Status | Verified |
|---|---|---|---|
| 0-7 | NOT ALLOWED | N/A (execution engine) | Yes |
| 8.1 | NOT ALLOWED | COMPLETED | Yes (47 tests) |
| 8.2 | LIMITED (queue priority only) | COMPLETED | Yes (29 tests) |
| 8.3 | STRICTLY FORBIDDEN | COMPLETED | Yes (37 tests) |
| 8.4 | NOT ALLOWED | COMPLETED | Yes (50 tests) |
| 8.5 | NOT ALLOWED | COMPLETED | Yes (36 tests) |
| 8.6 | NOT ALLOWED | COMPLETED | Yes (33 tests) |

---

# SUMMARY

Phase 8 architecture follows a strict rule:

> Decision-making is centralized.
> Everything else is deterministic state handling.

This prevents:
- hidden optimizers
- emergent scheduling logic
- architecture drift
