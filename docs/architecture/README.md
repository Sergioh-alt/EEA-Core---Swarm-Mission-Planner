# Architecture Documentation

Describes *how* the ORIÓN system is built: technical architecture, system
boundaries, formal contracts, and per-phase design proposals.

> Two Phase 9.7 documents that were previously here — the architecture isolation
> report and the cross-layer leak scan — are **validation reports** and now live
> under [`../validation/`](../validation/README.md).

## Technical Architecture

| File | Purpose |
|------|---------|
| [`architecture.md`](architecture.md) | Canonical current system architecture (layered modular) |
| [`v1_hardware_ready_architecture.md`](v1_hardware_ready_architecture.md) | Future production / hardware-ready architecture |
| [`001_architecture_v1.md`](001_architecture_v1.md) | Historical architecture snapshot (v1) |
| [`002_architecture_v0.5.md`](002_architecture_v0.5.md) | Historical architecture snapshot (v0.5) |

## System Boundaries & Enforcement

| File | Purpose |
|------|---------|
| [`SYSTEM BOUNDARY SPEC — ORIÓN PHASE 10.md`](SYSTEM%20BOUNDARY%20SPEC%20—%20ORIÓN%20PHASE%2010.md) | Phase 10 system boundary specification |
| [`PHASE-9.7-SEPARATION.md`](PHASE-9.7-SEPARATION.md) | Phase 9.7 contract separation & isolation spec |
| [`hal_boundary_lock_spec_phase9.md`](hal_boundary_lock_spec_phase9.md) | HAL boundary lock specification |
| [`decision_boundary_map_phase8.md`](decision_boundary_map_phase8.md) | Decision boundary map (Phase 8) |
| [`decision_boundary_map_phase9.md`](decision_boundary_map_phase9.md) | Decision boundary map (Phase 9) |
| [`Hardware Abstraction Layer (HAL).md`](Hardware%20Abstraction%20Layer%20(HAL).md) | HAL overview |

## Contracts (Phase 9.7)

| File | Purpose |
|------|---------|
| [`phase_9_7_simulation_contract.md`](phase_9_7_simulation_contract.md) | Simulation Layer Contract (SLC) |
| [`phase_9_7_iov_contract.md`](phase_9_7_iov_contract.md) | IoV Communication Contract (IoV-C) |
| [`phase_9_7_digital_twin_contract.md`](phase_9_7_digital_twin_contract.md) | Digital Twin Contract (DTC) |

## Design Proposals

| File | Purpose |
|------|---------|
| [`phase7_design_proposal.md`](phase7_design_proposal.md) | Phase 7 Intelligence Layer design |
| [`phase8_design.md`](phase8_design.md) | Phase 8 Hive System design |
| [`phase9_design.md`](phase9_design.md) | Phase 9 HAL design |

## UI Architecture (Phase 10C.1 blueprint)

See [`ui/`](ui/) — 7 documents defining the Next.js Mission Control UI
architecture (component hierarchy, data flow, navigation map, interaction model,
UI contracts, scalability strategy).
