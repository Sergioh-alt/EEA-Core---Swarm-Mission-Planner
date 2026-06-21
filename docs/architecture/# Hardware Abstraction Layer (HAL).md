# Hardware Abstraction Layer (HAL)

## Purpose

The Hardware Abstraction Layer (HAL) defines a **virtual interface between the Swarm Mission Planner software and real-world drone hardware systems**.

It allows the system to run in full simulation today while remaining fully compatible with future physical deployment.

This ensures zero redesign when transitioning from simulation → real drones.

---

## Core Principle

> “Everything physical is an interface. Everything simulated must behave like hardware.”

The system never depends directly on real hardware implementations.

Instead, it depends on abstract interfaces.

---

## Main Hardware Interfaces

### 1. DroneInterface

Defines a single drone unit.

Responsibilities:
- Takeoff / landing
- Execute waypoint routes
- Report telemetry
- Maintain flight state

Methods (conceptual):
- `arm()`
- `takeoff()`
- `execute_route(route)`
- `return_to_base()`
- `get_status()`

---

### 2. BatterySystem

Represents energy system of each drone.

Responsibilities:
- Track charge level
- Simulate consumption per hectare
- Trigger return-to-base logic

Methods:
- `get_level()`
- `consume(rate)`
- `needs_recharge()`

---

### 3. SprayerSystem

Represents agricultural payload system.

Responsibilities:
- Liquid spraying simulation
- Flow rate control
- Coverage estimation

Methods:
- `start_spray()`
- `stop_spray()`
- `set_flow_rate(rate)`

---

### 4. ChargingStation

Represents base recharge infrastructure.

Responsibilities:
- Drone docking simulation
- Battery recharge cycles
- Fleet coordination support

Methods:
- `dock(drone)`
- `recharge(drone)`
- `release(drone)`

---

## Simulation Mode vs Future Mode

| Component | Current State | Future State |
|-----------|--------------|--------------|
| DroneInterface | Simulated logic | Physical drone SDK |
| BatterySystem | Mathematical model | Real battery telemetry |
| SprayerSystem | Coverage simulation | Pump hardware control |
| ChargingStation | Time-based model | Physical docking station |

---

## Design Rule

The core system MUST NEVER know:

- Whether the drone is real or simulated
- Whether telemetry is fake or real
- Whether battery is modeled or measured

It only interacts with interfaces.

---

## Future Extension

This layer will later support:

- ROS2 integration
- MQTT telemetry streams
- Real drone SDKs
- Edge computing controllers

---

## Summary

HAL is what makes this system:

✔ Simulation-ready today  
✔ Hardware-ready tomorrow  
✔ Industrial-grade architecture by design