# Decision Boundary Map — Phase 8 (Hive System)

## Purpose

This document defines strict decision-making boundaries across the Phase 8 architecture.

Its goal is to prevent unintended optimization, implicit scheduling, or emergent decision-making behavior inside orchestration components.

---

# CORE PRINCIPLE

> Only one layer in the system is allowed to make decisions:
> the Mission Orchestrator (Phase 8.2).

All other components are strictly stateful or structural.

---

# DECISION RESPONSIBILITY MATRIX

## Phase 0–7 (Execution Engine)

### ❌ Decision-making: NOT ALLOWED

These modules only execute deterministic logic:
- plan_swarm()
- plan_routes()
- generate_timeline()
- evaluate_risks()

✔ They compute outputs  
❌ They do NOT decide assignments or priorities

---

## Phase 8.1 — Hive Core Foundation

### ❌ Decision-making: NOT ALLOWED

Components:
- HiveState
- MissionQueue
- FleetRegistry

### Role:
- state representation only
- storage and retrieval only

✔ No logic inference  
✔ No prioritization decisions  
✔ No allocation decisions  

---

## Phase 8.2 — Mission Orchestrator

### ✅ LIMITED DECISION AUTHORITY

Allowed decisions:
- mission execution order (based on queue priority only)
- which mission runs next
- execution flow control

❌ NOT allowed:
- drone selection optimization
- resource balancing
- performance-based assignment
- adaptive planning

---

## Phase 8.3 — Fleet Manager

### ❌ DECISION MAKING STRICTLY FORBIDDEN

Fleet Manager MUST NOT decide:

- which drone is better
- which mission gets which drone
- any form of ranking or scoring

### Allowed ONLY:
- register assignment (external decision input)
- track drone state
- report availability

> Fleet Manager = Passive registry, NOT allocator

---

## Phase 8.4 — Resource System (Future)

### ❌ Decision-making: NOT ALLOWED

- only tracks resources
- no allocation strategy

---

## Phase 8.5 — Integration Layer

### ❌ Decision-making: NOT ALLOWED

- only connects systems
- no logic changes

---

## Phase 8.6 — Validation Layer

### ❌ Decision-making: NOT ALLOWED

- only evaluates system correctness
- no runtime influence

---

# FORBIDDEN PATTERNS (SYSTEM-WIDE)

Any of the following indicates architecture violation:

- “best drone selection”
- “optimal assignment”
- “load balancing”
- “efficiency scoring”
- “automatic reallocation”
- “smart scheduling”

---

# SAFE PATTERN (CORRECT DESIGN)

✔ Decisions happen ONLY in Phase 8.2

Example:

Mission Orchestrator decides:
→ assign Drone A to Mission 1

Fleet Manager does:
→ record Drone A = Mission 1

---

# SUMMARY

Phase 8 architecture follows a strict rule:

> Decision-making is centralized.  
> Everything else is deterministic state handling.

This prevents:
- hidden optimizers
- emergent scheduling logic
- architecture drift
