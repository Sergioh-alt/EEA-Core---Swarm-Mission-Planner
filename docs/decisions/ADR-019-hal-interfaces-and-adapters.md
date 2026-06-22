# ADR-019: HAL Core Interfaces and Hardware Adapters (Phase 9.1 + 9.2)

## Status

Accepted

## Context

Phase 8 (Hive System) provides multi-mission orchestration but has no connection to hardware. Phase 9 introduces the Hardware Abstraction Layer (HAL) to bridge Hive outputs to real-world drone systems. The HAL must be a pure translation + safety + execution layer with zero decision-making.

## Decisions

### 1. Hardware-Agnostic Interface Contract

`BaseDroneInterface` (ABC) defines 7 methods that every adapter must implement:
- `send_command(CommandSchema) -> ExecutionResult`
- `get_telemetry(drone_id) -> TelemetrySchema`
- `arm(drone_id) -> ExecutionResult`
- `disarm(drone_id) -> ExecutionResult`
- `return_to_home(drone_id) -> ExecutionResult`
- `is_connected(drone_id) -> bool`
- `get_adapter_name() -> str`

**Rationale:** Single interface contract ensures all adapters are swappable. Hive never knows which hardware is underneath.

### 2. Standardized Command Schema

`CommandSchema` uses an enum-based `CommandType` (10 types: ARM, DISARM, TAKEOFF, LAND, GOTO, RETURN_TO_HOME, SET_SPEED, SPRAY_START, SPRAY_STOP, EMERGENCY_STOP) with a `params` dict for type-specific parameters.

**Rationale:** Enum-based types prevent invalid commands at construction time. Params dict allows hardware-specific parameters without changing the schema. Validation at construction (non-empty command_id, non-negative drone_id).

### 3. Standardized Telemetry Schema

`TelemetrySchema` normalizes hardware telemetry into a common format: flight_state, GPS position, battery, speed, heading, connectivity. A `raw_data` dict preserves adapter-specific data.

**Rationale:** Hive only needs to understand the common schema. Raw data is preserved for debugging and future hardware-specific features without schema changes.

### 4. Three Adapter Types

- **SimulationAdapter:** Full state simulation for testing. Maintains in-memory drone state, validates state transitions, produces telemetry. Mandatory for all HAL testing.
- **PX4Adapter:** Translates HAL commands to PX4 MAVLink format. Structural adapter — actual MAVLink communication deferred to Phase 10.
- **ArduPilotAdapter:** Translates HAL commands to ArduPilot format. Uses ArduPilot-specific modes (GUIDED, RTL, etc.) and servo-based spray control.

**Rationale:** SimulationAdapter enables full integration testing without hardware. PX4/ArduPilot adapters validate command translation correctness and establish the protocol mapping for Phase 10.

### 5. Adapters Import Only from hal_interfaces

Adapters import ONLY from `core.hal_interfaces`. No imports from Phase 0-8 modules. This ensures complete decoupling — HAL is a standalone translation layer.

### 6. No Decision-Making in HAL

All adapters mechanically translate commands. They do not:
- Choose between command alternatives
- Evaluate mission success
- Plan routes or trajectories
- Allocate resources or drones
- Schedule or prioritize operations

Safety overrides (emergency stop, geofence) are structural responses, not decisions.

## Consequences

- Hive remains completely hardware-agnostic
- New hardware platforms require only a new adapter implementing BaseDroneInterface
- Full integration testing possible without hardware via SimulationAdapter
- Phase 10 can add real MAVLink communication to PX4/ArduPilot adapters without changing the interface
