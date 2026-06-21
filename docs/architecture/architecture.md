# Architecture — EEA Swarm Mission Planner

## System Architecture Overview

The system follows a **layered modular architecture** designed for scalability, testability, and future hardware integration.

---

## Architectural Layers

### 1. Input Layer (Mission Definition)

Responsible for defining mission parameters:

- Field geometry or estimated hectares
- Crop type
- Drone fleet size
- Environmental constraints

Module:
- `core/mission_intake.py`

---

### 2. Analysis Layer (Environment Intelligence)

Processes environmental conditions:

- Wind conditions
- Risk estimation
- Operational feasibility

Module:
- `core/environment_analyzer.py`

---

### 3. Planning Layer (Swarm Logic)

Determines swarm behavior:

- Drone allocation per sector
- Load balancing
- Coverage distribution

Module:
- `core/swarm_planner.py`

---

### 4. Geometry Layer (Field Representation)

Handles spatial modeling:

- Polygon construction
- Field area computation
- Validation of geometry

Module:
- `core/geometry.py`

---

### 5. Partition Layer (Field Decomposition)

Splits field into operational sectors:

- Grid partition (legacy mode)
- Strip partition (polygon-aware mode)

Inside:
- `core/swarm_planner.py`

---

### 6. Routing Layer (Path Generation)

Generates drone flight paths:

- Boustrophedon routes (grid mode)
- Sweep-line polygon routes (strip mode)

Module:
- `core/route_planner.py`

---

### 7. Resource Layer (Operational Constraints)

Estimates mission resources:

- Battery consumption
- Flight time
- Coverage efficiency

Module:
- `core/resource_planner.py`

---

### 8. Risk Layer (Safety Evaluation)

Evaluates mission safety:

- Wind risk
- Coverage risk
- Execution feasibility

Module:
- `core/risk_engine.py`

---

### 9. Decision Layer (Final Output)

Aggregates all system outputs:

- Final recommendation
- Confidence score
- Operational summary

Module:
- `core/decision_engine.py`

---

## UI Layer

Provides visualization and interaction:

- Field input (hectares or polygon)
- Mission configuration
- Swarm visualization
- Route preview

Modules:
- `ui/mission_config.py`
- `ui/swarm_view.py`
- `app.py`

---

## Data Flow

```
Mission Intake
    |
    v
Environment Analyzer
    |
    v
Swarm Planner
    |
    v
Geometry Engine
    |
    v
Route Planner
    |
    v
Resource Planner
    |
    v
Risk Engine
    |
    v
Decision Engine
    |
    v
Final Recommendation
```

---

## Design Principles

### 1. Modularity
Each module is independent and testable.

### 2. Determinism
Same input produces same output always.

### 3. Replaceability
Each module can be upgraded without breaking the system.

### 4. Hardware Readiness
Designed to map directly to real drone systems via HAL layer.

---

## Testing Strategy

- Regression tests ensure v0.1 compatibility
- Geometry tests validate polygon correctness
- End-to-end pipeline tests validate full mission flow

---

## Current Version

- v0.5.0 stabilized system
- Full pipeline operational
- Polygon-aware routing enabled
- UI interactive mode implemented

---

## Future Evolution

The architecture is designed to evolve into:

- Hardware-integrated swarm system
- Multi-mission coordination engine
- Real-time telemetry system
- Autonomous agricultural OS

---

## Summary

This is a **modular autonomous planning architecture for drone swarm operations with future hardware integration capability.**
