# ADR-015: Mission Orchestrator (Phase 8.2)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 8.2 — Hive System (Mission Orchestrator)

## Context

With the Hive Core Foundation (Phase 8.1) providing FleetRegistry, MissionQueue, and HiveState, the system needs the ability to execute missions from the queue through the existing Phase 0–7 pipeline. Phase 8.2 introduces the Mission Orchestrator — an execution coordinator, not a scheduler or optimizer.

## Decision

Implement three components in `core/mission_orchestrator.py`:

### 1. MissionExecutionContext
- Isolated container for a single mission's pipeline outputs
- Each mission gets its own independent context
- No mutable state shared between contexts
- Tracks execution phase: PENDING → PROFILING → ... → COMPLETED | FAILED

### 2. MissionLifecycleManager
- Registry of MissionExecutionContexts
- Provides queries on execution status (by phase, completed count, failed count)
- No scheduling or allocation decisions

### 3. run_mission() / run_queue()
- `run_mission()`: executes a single QueuedMission through the full Phase 0–7 pipeline
- `run_queue()`: dequeues all missions and runs each sequentially
- Each stage calls existing pipeline functions directly
- Failed missions do not prevent subsequent missions from executing

### Key design decisions

1. **Full pipeline reuse** — every stage delegates to existing functions: `create_mission_profile()`, `analyze_environment()`, `plan_swarm()`, `plan_routes()`, `plan_resources()`, `evaluate_risks()`, `generate_recommendation()`, `generate_timeline()`. Zero duplicate planning logic.

2. **Mission isolation** — each mission gets its own `MissionExecutionContext` with independent pipeline outputs. Contexts are never shared or reused. This guarantees no cross-mission interference.

3. **Sequential execution** — `run_queue()` processes missions one at a time. No concurrency, no parallelism. This keeps the execution model simple and deterministic.

4. **Error containment** — if a pipeline stage fails, the context is marked FAILED with the error message. The queue continues processing remaining missions.

5. **No scheduling** — `run_queue()` respects MissionQueue priority ordering but adds no scheduling logic. It simply dequeues and executes.

6. **No fleet allocation** — `run_mission()` uses the drone count from QueuedMission directly. Fleet assignment is deferred to Phase 8.3.

## Consequences

**Positive**:
- Zero modifications to Phase 0–7 modules or Phase 8.1 components
- Complete mission isolation — each mission's outputs are independent
- Deterministic — same inputs produce identical results
- Error resilient — failed missions don't block the queue
- Foundation for Phase 8.3 (Fleet Manager) and 8.5 (Integration)

**Negative**:
- Sequential execution means no parallel mission processing
- No fleet awareness — each mission specifies its own drone count
- No resource checking before execution

**Mitigations**:
- Parallel execution is a future concern (Phase 8.5 integration)
- Fleet allocation (Phase 8.3) will bridge fleet availability and mission drone counts
- Resource checking (Phase 8.4) will validate resources before execution
