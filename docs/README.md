# ORIÓN — EEA Core Swarm Mission Planner Documentation

Master index for all project documentation. Documentation is organized by type.

## Directory Map

| Directory | Contents | Index |
|-----------|----------|-------|
| [`architecture/`](architecture/README.md) | System architecture, boundary specs, contracts, design proposals, UI blueprint | [index](architecture/README.md) |
| [`adr/`](adr/README.md) | Architecture Decision Records (ADR-001 … ADR-020) | [index](adr/README.md) |
| [`audits/`](audits/README.md) | Architecture consistency / compliance audits | [index](audits/README.md) |
| [`roadmap/`](roadmap/README.md) | Master roadmaps and per-phase protocols | [index](roadmap/README.md) |
| [`validation/`](validation/README.md) | Phase validation, boundary, replay, regression reports + raw logs | [index](validation/README.md) |
| `research/` | Experiments and investigations (placeholder) | — |

## Root Documents

| File | Purpose |
|------|---------|
| [`system_overview.md`](system_overview.md) | High-level system overview |
| [`simulation_vs_reality.md`](simulation_vs_reality.md) | Simulation vs. real-hardware boundary discussion |
| [`DOCUMENTATION_STRUCTURE_AUDIT.md`](DOCUMENTATION_STRUCTURE_AUDIT.md) | Documentation audit & migration proposal (2026-06-29) |

## Conventions

- **Architecture** describes *how the system is built*; **ADRs** record *why* a
  decision was made; **validation** records *evidence that a phase works*.
- Historical/superseded documents are preserved, never deleted.
- Raw captured test output lives under `validation/logs/`.
