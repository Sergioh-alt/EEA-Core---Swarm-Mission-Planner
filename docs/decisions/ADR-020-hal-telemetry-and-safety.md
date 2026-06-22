# ADR-020: HAL Telemetry Stream System and Safety Layer (Phase 9.3 + 9.4)

## Status

Accepted

## Context

Phase 9.1-9.2 established HAL interfaces and hardware adapters. Phase 9.3 adds standardized telemetry streaming, and Phase 9.4 adds a deterministic safety relay system. Both must remain pure execution/observation layers with zero decision-making.

## Decisions

### 1. DroneTelemetryFrame Contract

Each frame includes all mandatory fields per telemetry contract: drone_id, position (lat/lon/alt), velocity (vx/vy/vz), heading, battery_level, power_draw, mission_id (nullable), task_state, gps_fix_quality, signal_strength, timestamp.

`TaskState` enum maps operational states: IDLE, EN_ROUTE, WORKING, RETURNING, EMERGENCY, LANDED. A deterministic mapping (`FLIGHT_STATE_TO_TASK`) converts adapter FlightState to TaskState.

**Rationale:** Hive needs a consistent telemetry format regardless of hardware. The mapping is deterministic and complete (all 9 FlightStates mapped).

### 2. FleetTelemetrySnapshot

Aggregates drone counts by state (total, active, idle, charging, faulty) plus individual frames. Pure counting — no intelligence or inference.

**Rationale:** Fleet-level visibility without fleet-level reasoning. Hive interprets the counts; HAL only produces them.

### 3. TelemetryStreamProcessor

Reads from any `BaseDroneInterface` adapter and normalizes to `DroneTelemetryFrame`. No storage layer, no historical data, no prediction.

- GPS fix quality derived deterministically from satellite count: <4 = NO_FIX, 4-7 = 2D, 8+ = 3D
- Velocity decomposed from speed + heading using trigonometry
- Disconnected drones excluded from frame reads

**Rationale:** Simple deterministic normalization rules that any adapter's telemetry can pass through. No storage ensures no inference.

### 4. Emergency Signal Detection (Not Decision)

`EmergencySignalHandler` detects raw fault conditions from telemetry: communication loss, low battery, GPS loss. It packages them as `EmergencySignal` objects but does NOT decide responses. Thresholds are configurable.

**Rationale:** HAL can detect hardware-level faults but must not respond autonomously. All response decisions belong to Hive.

### 5. FailSafeStateMapper — Deterministic Mapping

Maps 5 fail-safe states to hardware commands: KILL → EMERGENCY_STOP, RETURN_TO_HOME → RETURN_TO_HOME, LAND_IN_PLACE → LAND, HOVER → SET_SPEED(0), DISARM → DISARM.

**Rationale:** Pure translation table. Hive decides which fail-safe to activate; the mapper only translates.

### 6. SafetyCommandRelay — Pass-Through Only

Takes Hive's fail-safe decision, maps it via FailSafeStateMapper, and sends to adapter. Logs all relays. Does not make autonomous safety decisions.

**Rationale:** Safety commands must reach hardware reliably. The relay is a pipe, not a brain.

## Consequences

- Telemetry flows: Adapter → TelemetryStreamProcessor → DroneTelemetryFrame → Hive
- Safety flows: Hive decision → SafetyCommandRelay → FailSafeStateMapper → Adapter → Hardware
- HAL never interprets telemetry or makes safety decisions
- All modules import only from hal_interfaces — no Phase 0-8 coupling
