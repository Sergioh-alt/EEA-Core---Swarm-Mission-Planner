# Phase 9.7 — IoV Communication Contract (IoV-C)

## Status: ACTIVE DESIGN CONSTRAINT

---

## Purpose

Defines all allowed communication paths between system layers. Prevents cross-layer bypass, direct function calls across boundaries, and unauthorized data flow. Establishes the transport layer requirements for real-world deployment.

---

## Core Principle

**All inter-layer communication flows through validated contracts only.**

No layer may bypass the defined communication paths. No direct function calls across architectural boundaries are permitted except through the established contract interfaces.

---

## Allowed Communication Paths

### Path 1: Hive → HAL (Command Flow)

```
Hive System (Phase 8)
  → CommandSchema (validated contract)
    → BaseDroneInterface.send_command()
      → Hardware Adapter
        → Drone Hardware / Simulation
```

| Rule | Constraint |
|------|-----------|
| IoV-C1 | All commands flow through `CommandSchema` |
| IoV-C2 | No direct Hive → Adapter calls bypassing interface |
| IoV-C3 | `CommandSchema` is the only command transport format |
| IoV-C4 | Adapters receive commands, never request them |

### Path 2: HAL → Hive (Telemetry Flow)

```
Drone Hardware / Simulation
  → Hardware Adapter
    → TelemetrySchema (validated contract)
      → TelemetryStreamProcessor
        → DroneTelemetryFrame
          → Hive System (read-only)
```

| Rule | Constraint |
|------|-----------|
| IoV-C5 | All telemetry flows through `TelemetrySchema` |
| IoV-C6 | Telemetry is normalized by `TelemetryStreamProcessor` |
| IoV-C7 | Hive receives telemetry as read-only data |
| IoV-C8 | No telemetry path may modify Hive state directly |

### Path 3: Hive → HAL (Safety Flow)

```
Hive System (decision)
  → FailSafeState (decision output)
    → SafetyCommandRelay
      → FailSafeStateMapper
        → CommandSchema
          → Hardware Adapter
            → Drone Hardware
```

| Rule | Constraint |
|------|-----------|
| IoV-C9 | Safety decisions originate from Hive only |
| IoV-C10 | `SafetyCommandRelay` is a pass-through pipe |
| IoV-C11 | `FailSafeStateMapper` performs 1:1 deterministic mapping |
| IoV-C12 | No safety path makes autonomous decisions |

### Path 4: HAL → Hive (Emergency Signal Flow)

```
Drone Hardware / Simulation
  → Hardware Adapter
    → TelemetrySchema
      → EmergencySignalHandler.check_telemetry()
        → EmergencySignal (detection only)
          → Hive System (decides response)
```

| Rule | Constraint |
|------|-----------|
| IoV-C13 | Emergency signals are detection-only |
| IoV-C14 | `EmergencySignalHandler` does not decide responses |
| IoV-C15 | Hive receives signals and decides all emergency actions |

### Path 5: Simulation ↔ IoV (Mirror Only)

```
Simulation Adapter
  → TelemetrySchema (same format as real hardware)
  → Read by same TelemetryStreamProcessor
  → Produces same DroneTelemetryFrame
```

| Rule | Constraint |
|------|-----------|
| IoV-C16 | Simulation uses identical schemas as real hardware |
| IoV-C17 | Simulation telemetry flows through same normalization path |
| IoV-C18 | No special simulation bypass exists |

---

## Forbidden Communication Paths

| ID | Forbidden Path | Reason |
|----|---------------|--------|
| IoV-X1 | Simulation → Hive (direct) | Simulation must not influence decisions |
| IoV-X2 | Adapter → Planning modules | HAL must not access planning |
| IoV-X3 | UI → HAL (direct calls) | UI reads via Digital Twin only |
| IoV-X4 | Safety → Mission abort (direct) | Safety relays, Hive decides |
| IoV-X5 | Telemetry → Route modification | Telemetry is read-only |
| IoV-X6 | Any layer → Global mutable state | No shared mutable state |

---

## Transport Layer Requirements (Phase 10+)

When transitioning to real hardware, the following transport layers are required:

### MAVLink 2

- PX4Adapter: translates `CommandSchema` → MAVLink 2 messages
- ArduPilotAdapter: translates `CommandSchema` → MAVLink 2 messages
- Transport is adapter-internal; contract interface unchanged

### ROS2 Topics (Future)

- If ROS2 integration is added, topics must comply with IoV-C rules
- ROS2 nodes must not contain decision logic
- ROS2 topics are transport only — no processing in transport layer

### MQTT Broker (Future)

- If MQTT is used for telemetry streaming, messages must carry `TelemetrySchema`-compatible payloads
- MQTT subscribers must not modify system state
- Broker is transport only

---

## Current Implementation Compliance

| Path | Implementation | Status |
|------|---------------|--------|
| Hive → HAL | `CommandSchema` → `BaseDroneInterface.send_command()` | COMPLIANT |
| HAL → Hive | `TelemetrySchema` → `TelemetryStreamProcessor` → `DroneTelemetryFrame` | COMPLIANT |
| Safety | `SafetyCommandRelay` → `FailSafeStateMapper` → `CommandSchema` | COMPLIANT |
| Emergency | `EmergencySignalHandler` → `EmergencySignal` | COMPLIANT |
| Simulation | `SimulationAdapter` via `BaseDroneInterface` | COMPLIANT |
| Forbidden paths | No violations detected by static analysis | COMPLIANT |

---

## Verification

IoV-C compliance is verified by:

1. Import isolation tests — no cross-layer imports
2. `HALStaticAnalyzer` — forbidden import detection
3. Contract consistency tests — schema identity checks
4. Architecture validation tests — data flow verification

---

## IoV-C Freeze

This contract is frozen as of Phase 9.7. Phase 10 may add real transport implementations (MAVLink, ROS2, MQTT) inside existing adapter methods without modifying the contract interfaces.
