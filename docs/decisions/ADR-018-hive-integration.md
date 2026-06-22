# ADR-018: Hive Integration Layer (Phase 8.5)

## Status
Accepted

## Context
Phases 8.1-8.4 implemented four independent sub-systems (Hive Core, Mission Orchestrator, Fleet Manager, Resource System). Phase 8.5 must unify these into a single orchestration framework without introducing any new intelligence or decision-making.

## Decision

### 1. HiveRuntime as Component Container
`HiveRuntime` initializes and holds references to all sub-systems. All sub-systems share the same `FleetRegistry` instance to ensure consistent state. No logic is added -- it is a lifecycle manager only.

### 2. HiveController as Unified Entry Point
`HiveController` provides high-level operations (submit mission, execute, snapshot) that delegate to existing sub-systems. Every method is a thin wrapper -- no new behavior is introduced. Users can also access `runtime` directly for sub-system operations.

### 3. No Decision-Making
Per `decision_boundary_map_phase8.md`, the Integration Layer has NO decision authority. It may observe, aggregate, and expose state. It may NOT select drones, allocate resources, or optimize anything. All assignment operations remain on the caller.

### 4. HiveSystemSnapshot as Consolidated View
`HiveSystemSnapshot` aggregates HiveState, fleet assignment summary, resource snapshot, and lifecycle summary into a single immutable dataclass. Same pattern as HiveState (8.1) and ResourceSnapshot (8.4).

### 5. Composition Over Inheritance
HiveController wraps HiveRuntime. HiveRuntime wraps individual sub-systems. No inheritance chains. Clean separation preserved.

## Consequences
- Single entry point for the entire Hive system
- All Phase 8.1-8.4 sub-systems remain independently testable
- No existing module is modified
- Future phases can extend HiveController without modifying sub-systems
- Decision boundary compliance is verifiable via attribute inspection tests
