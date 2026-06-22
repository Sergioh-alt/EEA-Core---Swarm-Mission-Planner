# ADR-017: Resource System (Phase 8.4)

## Status
Accepted

## Context
Phase 8.3 introduced fleet-level drone assignment tracking. The next step is fleet-wide resource awareness — tracking battery and liquid state across missions. The system must remain a passive state layer with zero decision-making.

## Decision

### 1. Separate Battery and Liquid Managers
Battery and liquid resources have fundamentally different lifecycles (charge/depleted vs fill/empty), so they are tracked by separate managers (`BatteryInventoryManager`, `LiquidInventoryManager`) rather than a single generic resource manager.

### 2. Composition over Modification
Resource System wraps `FleetRegistry` via composition — it does not modify or extend it. One-way imports only: `resource_system` imports from `core.hive`, never vice versa.

### 3. No Decision-Making
Per `decision_boundary_map_phase8.md`, Phase 8.4 has NO decision authority. The Resource System:
- Does NOT decide which drone gets which battery
- Does NOT decide which mission receives resources
- Does NOT balance resources across missions
- Only tracks, updates, and reports resource state

### 4. Consumption Logging
Both managers maintain consumption logs (`BatteryConsumptionRecord`, `LiquidConsumptionRecord`) that record per-drone, per-mission consumption events. This provides mission-level resource visibility without requiring external logging infrastructure.

### 5. ResourceStateTracker as Unified View
`ResourceStateTracker` integrates both managers to provide a single view of per-drone resource state and fleet-wide snapshots. It accesses internal state of the battery/liquid managers for efficient drone-resource lookup.

### 6. Immutable Snapshots
`ResourceSnapshot` is an immutable dataclass providing a point-in-time view of all resource state. This follows the same pattern as `HiveState` (Phase 8.1).

## Consequences
- Resource state is always deterministic and reproducible
- No existing Phase 0–8.3 modules are modified
- Resource tracking is opt-in — existing pipeline behavior unchanged unless resource system is explicitly invoked
- Future phases (8.5+) can consume resource state without modifying the tracking layer
