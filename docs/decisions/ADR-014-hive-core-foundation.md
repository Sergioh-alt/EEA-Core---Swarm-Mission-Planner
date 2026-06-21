# ADR-014: Hive Core Foundation (Phase 8.1)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 8.1 — Hive System (Multi-Mission Orchestration Foundation)

## Context

With the Intelligence Layer (Phase 7) complete, the system needs a multi-mission orchestration layer to manage multiple missions, drone fleets, and shared resources. Phase 8.1 establishes the structural backbone — state primitives only, no scheduling or optimization logic.

The Hive system follows the core principle: **Hive orchestrates, it does not replace.** All Phase 0–7 systems remain unchanged and serve as the execution engine.

## Decision

Implement three structural primitives in `core/hive.py`:

### 1. FleetRegistry
- Global registry of all drones with availability states (idle/active/charging/maintenance)
- State queries: `get_available()`, `get_by_availability()`, `fleet_health_snapshot()`
- No allocation logic, no scheduling logic

### 2. MissionQueue
- Priority-based mission container (LOW → NORMAL → HIGH → CRITICAL)
- Deterministic ordering: highest priority first, FIFO within same priority
- Mission lifecycle: QUEUED → EXECUTING → COMPLETED | FAILED | CANCELLED
- No execution logic, no optimization logic

### 3. HiveState
- Central immutable system snapshot built from FleetRegistry + MissionQueue
- System status: `no_fleet` | `idle` | `ready` | `active`
- Read-heavy, deterministic, versioned

### Key design decisions

1. **Orchestration only** — these primitives store and expose state. They make no decisions about scheduling, allocation, or optimization.

2. **Hive-specific enums** — `DroneAvailability` and `MissionStatus` in `core/hive.py` are distinct from Phase 7.1's `DroneStatus` and `MissionStatus`. Phase 7 enums track per-mission drone lifecycle; Phase 8 enums track fleet-level availability and queue status.

3. **No Phase 0–7 imports** — `core/hive.py` only imports from `utils/logger.py`. It does not import from any existing pipeline module. This ensures complete separation of orchestration and execution layers.

4. **Deterministic snapshots** — `build_hive_state()` produces identical output given identical FleetRegistry + MissionQueue state. No timestamps, no randomness.

5. **Priority sorting** — uses Python's stable sort on `MissionPriority.value` (int), ensuring FIFO within same priority level.

## Consequences

**Positive**:
- Zero modifications to Phase 0–7 modules
- Complete separation of concerns (orchestration vs execution)
- Deterministic and testable
- Opt-in: system unchanged unless Hive components are explicitly used
- Foundation for Phase 8.2+ (orchestrator, fleet manager, resource system)

**Negative**:
- FleetRegistry and MissionQueue are in-memory only (no persistence)
- No cross-reference between Hive drone IDs and Phase 7 drone IDs yet

**Mitigations**:
- Persistence is a future concern (Phase 8.5 integration)
- Phase 8.2 (Mission Orchestrator) will bridge Hive and pipeline drone identifiers
