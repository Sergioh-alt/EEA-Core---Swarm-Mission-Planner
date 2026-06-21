# ADR-010: Swarm State Manager (Phase 7.1)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 7.1 — Intelligence Layer (State Tracking)

## Context

Phase 7 introduces adaptive swarm behavior. Before any adaptation logic can work (reallocation, optimization, mission adaptation), there must be a central registry tracking:
- Individual drone states (position, battery, liquid, passes completed, status)
- Overall mission progress (sectors completed, coverage %, elapsed time)
- Failure events (which drone, when, what was left uncompleted)

Design options considered:
- **Distributed state**: Each drone tracks its own state independently
- **Event-sourced log**: All state changes stored as an append-only event log
- **Centralized mutable registry**: Single `SwarmStateManager` holds the current state snapshot

## Decision

Adopt a **centralized mutable state registry** (`SwarmStateManager`) with typed dataclasses:

```python
SwarmStateManager.__init__(profile, swarm, routes)
    → initializes DroneState for each sector (IDLE, full battery/liquid, 0 passes)

SwarmStateManager.get_state() → MissionState
    → computed snapshot: coverage_pct, sectors_completed/remaining, alerts

SwarmStateManager.update_drone(drone_id, **kwargs) → None
    → field-level updates with validation

SwarmStateManager.mark_drone_failed(drone_id, reason) → FailureEvent
    → sets status=FAILED, logs event, generates alert
```

### Key design decisions

1. **Initialized from existing pipeline outputs** — constructor takes `MissionProfile`, `SwarmPlan`, `RoutePlan` (all existing types). No new pipeline dependencies.

2. **Read-only view of plan data** — the state manager reads sector assignments and route passes from the plan but never modifies them. Plan modification is the responsibility of Phase 7.2+ modules.

3. **Typed enums for lifecycle states**:
   - `DroneStatus`: IDLE → LAUNCHING → ACTIVE → {REFILLING, SWAPPING_BATTERY} → RETURNING → COMPLETED | FAILED
   - `MissionStatus`: PLANNING → ACTIVE → {PAUSED} → COMPLETING → DONE | ABORTED

4. **FailureEvent as return value** — `mark_drone_failed()` returns a `FailureEvent` dataclass that downstream modules (ReallocationEngine) can consume directly.

5. **Coverage computed dynamically** — `coverage_pct = sum(passes_completed) / sum(passes_total) * 100`. Not cached; recomputed on each `get_state()` call for consistency.

6. **No persistence** — state lives in memory only. Future phases may add persistence if needed.

## Consequences

**Positive**:
- Zero modifications to existing pipeline modules
- Purely additive — importing `swarm_state` is opt-in
- Lightweight dataclasses with no external dependencies
- `FailureEvent` provides structured input for Phase 7.2 ReallocationEngine
- Alert system provides foundation for Phase 7.3 MissionAdapter triggers

**Negative**:
- Mutable state breaks the pure-function pattern of Phases 1–6
- No persistence means state is lost if the process restarts
- `update_drone()` uses `setattr` — less type-safe than explicit setters

**Mitigations**:
- State manager is isolated from the pipeline — pipeline remains pure functions
- `update_drone()` validates field names against `DroneState.__dataclass_fields__` before calling `setattr`
- Future Phase 9 (hardware layer) will add persistence if needed
