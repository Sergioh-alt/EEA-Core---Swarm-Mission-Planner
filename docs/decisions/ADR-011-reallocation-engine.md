# ADR-011: Reallocation Engine (Phase 7.2)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 7.2 — Intelligence Layer (Drone Failure Recovery)

## Context

With the SwarmStateManager (Phase 7.1) tracking drone states and failures, the system now needs a mechanism to recover from drone failures mid-mission. When a drone fails, its uncompleted sector work must be reassigned to preserve coverage.

Design options considered:
- **Round-robin redistribution**: Split failed work equally among remaining drones
- **Greedy nearest-first**: Assign to the closest available drone
- **Optimization-based**: Use the SwarmOptimizer to find optimal reassignment (Phase 7.4 dependency)
- **Manual operator reassignment**: Present options to operator for decision

## Decision

Adopt a **deterministic greedy nearest-first** strategy:

```python
def reallocate_on_failure(state, failed_drone_id, profile, swarm, assessment)
    → ReallocationPlan

Strategy:
1. Find the failed drone's uncompleted sector
2. Sort available drones by Euclidean distance to sector centroid
3. Assign the entire sector to the nearest available drone
4. Recompute routes via plan_routes() (no duplicate logic)
5. Recompute timeline via generate_timeline()
6. Return ReallocationPlan with coverage/time comparison
```

### Key design decisions

1. **Greedy, not optimal** — nearest available drone receives the work. Simple, deterministic, and explainable. Phase 7.4 SwarmOptimizer can improve this later.

2. **Whole-sector reassignment** — the entire failed sector is reassigned, not individual passes. This simplifies recomputation since `plan_routes()` works at the sector level.

3. **No duplicate planning logic** — route recomputation delegates to existing `plan_routes()` and timeline to `generate_timeline()`. The reallocation engine only handles the assignment decision.

4. **Coverage-first objective** — coverage preservation (100% after reallocation) is the primary goal. Time penalty is tracked but not minimized.

5. **Infeasible plans** — when no drones are available, the engine returns a `ReallocationPlan` with `feasible=False` rather than raising an exception. This allows the caller to handle the failure gracefully.

6. **Modified SwarmPlan construction** — `_build_modified_swarm()` creates a new `SwarmPlan` with sector assignments updated. The original plan is never mutated.

## Consequences

**Positive**:
- Zero modifications to existing pipeline modules
- `plan_routes()` and `generate_timeline()` are reused — no duplicate planning logic
- Coverage is always preserved when drones are available
- Deterministic: same failure scenario produces identical reallocation plan
- `ReallocationPlan` provides structured data for UI display (future)

**Negative**:
- Greedy assignment may not be globally optimal (nearest drone might already be overloaded)
- Whole-sector reassignment means one drone takes on significant extra work
- No partial-completion credit — if the failed drone completed 80% of passes, the entire sector is still reassigned

**Mitigations**:
- Phase 7.4 SwarmOptimizer can post-process the reallocation for better balance
- `coverage_before_pct` and `coverage_after_pct` provide transparency
- `time_penalty_min` makes the cost of reallocation explicit
