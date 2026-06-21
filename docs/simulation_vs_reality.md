# Simulation vs Reality Model

## Purpose

This document defines the boundary between:

- Simulation logic (software environment)
- Real-world execution (hardware deployment)

The system is designed so both behave identically at the interface level.

---

## Core Philosophy

> "Simulation is not a mock. It is a deterministic mirror of reality."

Every simulated output must be:

- Predictable
- Measurable
- Reproducible
- Physically consistent

---

## What is Simulated Today

### 1. Flight Execution
- Waypoint navigation is simulated
- Time is modeled (not real-time flight)

### 2. Battery Usage
- Consumption is mathematical
- Based on hectares, speed, load

### 3. Spraying System
- Coverage is geometric estimation
- No real fluid dynamics

### 4. Environmental Conditions
- Wind, risk, and terrain are modeled
- Not sensor-driven

---

## What is Real in Design (Future Hardware Layer)

### 1. Drone Behavior
- Real motor thrust
- GPS navigation
- IMU stabilization

### 2. Battery System
- Voltage sensors
- Real discharge curves
- Thermal effects

### 3. Spraying System
- Pump pressure control
- Flow sensors
- Nozzle calibration

### 4. Communication
- Live telemetry streams
- Real-time control commands

---

## Mapping: Simulation to Reality

| Simulation | Real System |
|------------|------------|
| time.sleep() mission step | flight controller timing |
| geometric coverage model | actual spray footprint |
| battery decay function | battery sensor readings |
| route planner output | autopilot mission upload |

---

## Key Design Rule

The system must ensure:

> "If simulation works, real-world execution should behave within expected deviation bounds."

---

## Critical Constraint

The system is NOT:

- A game simulation
- A visual demo only

It is:

- A pre-deployment robotics system
- A deterministic planning engine
- A hardware-ready control architecture

---

## Future Expansion

This model will later integrate:

- Digital twin system
- Real telemetry ingestion
- Sensor fusion layer
- ROS2 bridge

---

## Summary

Simulation is not fake execution.

It is a controlled environment for validating real-world behavior before deployment.
