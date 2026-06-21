# ADR-009: Intelligence Layer Design (Phase 7)

**Status**: Proposed (awaiting approval)
**Date**: 2026-06-21
**Phase**: 7 — Intelligence Layer (Multi-Agent Optimization)

## Context

The system can plan and simulate missions but cannot adapt to changes during execution. Phase 7 introduces adaptive swarm behavior while preserving the deterministic planning core.

Key requirements:
- Drone failure recovery without mission abort
- Multi-objective optimization (time vs battery vs coverage)
- Mid-mission adaptation to changing conditions
- Centralized state tracking for all drones

Constraint: Phase 7 modules must **consume** existing pipeline functions, not duplicate them.

## Decision

Introduce four new modules that form an intelligence layer above the existing pipeline:

### 1. `core/swarm_state.py` — Swarm State Manager
- `DroneState` dataclass: status, position, battery, liquid, progress
- `DroneStatus` enum: IDLE, ACTIVE, REFILLING, SWAPPING_BATTERY, RETURNING, COMPLETED, FAILED
- `MissionState` dataclass: overall mission progress, active alerts
- `SwarmStateManager` class: state queries, updates, failure detection

### 2. `core/reallocation_engine.py` — Dynamic Drone Reallocation
- On drone failure: identify uncompleted work, find nearest available drone
- Greedy assignment strategy (coverage-first, time-secondary)
- Calls `plan_routes()` and `generate_timeline()` for recomputation
- Outputs: `ReallocationPlan` with reassignments and coverage impact

### 3. `core/swarm_optimizer.py` — Swarm Optimization
- Hill-climbing optimization over strip boundary positions
- Multi-objective scoring: time (0.3), battery (0.3), coverage (0.2), balance (0.2)
- Bounded iterations (max 50), deterministic convergence
- Uses existing `plan_swarm()` + `plan_routes()` as evaluation function

### 4. `core/mission_adapter.py` — Mission Adaptation
- Triggers: wind change, resource depletion, partial completion
- Re-evaluates conditions using `analyze_environment()`
- Produces recommendations (continue / modify / abort) — not autonomous decisions
- Calls existing pipeline for replanning

### Integration architecture
```
Existing Pipeline → SwarmStateManager.init()
                         ↓
                    MissionState
                         ↓
              ┌──────────┼──────────┐
         [Failure]   [Condition]  [Optimize]
              ↓          ↓           ↓
         reallocate  adapt_mission  optimize_swarm
              ↓          ↓           ↓
         Modified Plan (via existing pipeline calls)
```

All Phase 7 modules are **opt-in** — the pipeline produces identical output when they are not invoked.

## Consequences

**Positive**:
- No modification to existing 7-module pipeline
- State manager provides foundation for future real-time features (Phase 9+)
- Optimizer uses deterministic hill-climbing — no ML or randomness
- Adaptation produces recommendations, not autonomous actions

**Negative**:
- Reallocation adds planning latency (re-runs partial pipeline)
- Hill-climbing may not find global optimum for complex field shapes
- State manager introduces mutable state (unlike the pure-function pipeline)

**Mitigations**:
- Reallocation only processes remaining uncovered area (bounded cost)
- Optimizer has iteration limit + early convergence detection
- State manager is isolated from the pipeline — read-only view of plan outputs
- All 44+ existing tests must continue to pass as a regression gate
