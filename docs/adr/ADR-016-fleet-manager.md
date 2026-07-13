# ADR-016: Fleet Manager (Phase 8.3)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 8.3 — Hive System (Fleet Manager)

## Context

With MissionQueue (8.1) and MissionOrchestrator (8.2) in place, the system needs drone-level fleet awareness and assignment tracking across missions. Phase 8.3 adds the Fleet Manager — a state tracking layer that manages drone-to-mission mappings and state transitions.

## Decision

Implement three components in `core/fleet_manager.py`:

### 1. DroneStatusTracker
- Wraps FleetRegistry to add state transition history
- Records every state change with `StateTransition` dataclass (from_state, to_state, reason)
- Provides filtered history queries per drone
- Same-state transitions are no-ops (no history entry)

### 2. DroneAllocationManager
- Maintains drone-to-mission assignment mapping
- `assign_drone()`: validates IDLE state, creates `DroneAssignment`, sets ACTIVE
- `release_drone()`: removes assignment, sets drone back to IDLE
- Query methods: `get_mission_drones()`, `get_drone_mission()`, `get_all_assignments()`
- No decision-making — caller explicitly chooses which drone to assign

### 3. FleetStateUpdater
- Batch state operations across the fleet
- `release_mission_drones()`: releases all drones from a completed mission
- `set_drones_maintenance()` / `set_drones_charging()`: only transitions IDLE drones
- `return_drones_idle()`: only transitions CHARGING/MAINTENANCE drones
- `fleet_assignment_summary()`: read-only snapshot of assignment distribution

### Key design decisions

1. **State tracking only** — no scheduling, optimization, or decision-making. The caller decides which drone to assign to which mission.

2. **Wraps FleetRegistry** — DroneStatusTracker and DroneAllocationManager operate on an existing FleetRegistry instance. They add behavior (history, assignments) without modifying the FleetRegistry class.

3. **Validated transitions** — `assign_drone()` only accepts IDLE drones. `set_drones_maintenance/charging()` only transition IDLE drones. `return_drones_idle()` only transitions CHARGING/MAINTENANCE drones. Active drones are never silently overwritten.

4. **Direct attribute access for None assignment** — FleetRegistry's `update_drone()` uses `if value is not None` guards, so setting `assigned_mission_id=None` via `update_drone()` doesn't work. `release_drone()` directly sets the attribute on the FleetDrone dataclass instead. This avoids modifying Phase 8.1's FleetRegistry.

5. **No Phase 0–7 imports** — `core/fleet_manager.py` only imports from `core/hive.py` and `utils/logger.py`. Complete orchestration/execution layer separation maintained.

## Consequences

**Positive**:
- Zero modifications to Phase 0–8.2 modules
- Full drone lifecycle tracking with history
- Assignment isolation — releasing one mission's drones doesn't affect another
- Deterministic state management
- Foundation for Phase 8.4 (Resource System) and 8.5 (Integration)

**Negative**:
- In-memory only (no persistence)
- No validation that assigned drone count matches mission requirements

**Mitigations**:
- Persistence is deferred to Phase 8.5 (Integration)
- Phase 8.5 will bridge allocation and orchestration
