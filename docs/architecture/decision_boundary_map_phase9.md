# DECISION BOUNDARY MAP — PHASE 9 (HAL)

## Purpose

This document defines strict boundaries for decision-making in Phase 9.

It ensures that no intelligence, optimization, or planning logic leaks into the Hardware Abstraction Layer.

---

## HARD BOUNDARY RULE

HAL IS NOT ALLOWED TO DECIDE ANYTHING.

---

## Allowed Responsibilities

HAL may ONLY:

- Translate commands
- Forward telemetry
- Enforce safety constraints
- Maintain communication adapters
- Normalize hardware data
- Execute received instructions

---

## Forbidden Responsibilities (CRITICAL)

HAL MUST NOT:

### Planning
- No mission planning
- No route generation
- No trajectory computation

### Intelligence
- No learning
- No inference
- No prediction

### Optimization
- No resource balancing
- No fleet optimization
- No efficiency improvement logic

### Allocation
- No drone assignment
- No mission distribution

### Scheduling
- No execution ordering
- No prioritization decisions

### Evaluation
- No mission success scoring
- No risk assessment decisions

---

## Decision Ownership Map

| Layer | Decision Authority |
|------|------------------|
| Phase 0–7 | Full mission planning |
| Phase 8 (Hive) | Fleet + orchestration coordination |
| Phase 9 (HAL) | NO decisions |
| Hardware | NO decisions |

---

## Critical Rule

If a function chooses between options, it does NOT belong in HAL.

HAL may only execute instructions, not interpret alternatives.

---

## Safety Exception Rule

HAL may override commands ONLY if:

- Geofence violation detected
- Hardware failure detected
- Emergency stop triggered
- Communication loss detected

These are safety overrides, not decisions.

---

## Verification Requirements

- AST scan for forbidden logic patterns
- Detection of conditional planning logic
- Detection of optimization heuristics
- Detection of implicit allocation logic

---

## Compliance Statement

Phase 9 is compliant only if:

- All decision-making remains in Hive (Phase 8)
- HAL acts purely as execution layer
- No autonomous behavior exists in HAL
