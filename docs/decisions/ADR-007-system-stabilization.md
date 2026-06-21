# ADR-007: System Stabilization Strategy (Phase 5)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 5 — System Stabilization & Consolidation

## Context

After Phases 2-4 added geometry, routing, and UI features, the codebase needed architectural consolidation before further evolution. Known issues:
- `compute_polygon_orientation()` was duplicated in `swarm_planner.py` and `route_planner.py`
- No formal regression test suite existed (only manual verification)
- Architecture documentation was outdated
- Version numbering was inconsistent

Phase 5 objectives:
- Unify architecture across all modules
- Remove duplicated logic
- Create formal regression test suite
- Document the architecture
- Establish a version baseline

## Decision

### Consolidation
- Moved `compute_polygon_orientation()` to `core/geometry.py` as the single canonical implementation
- Both `swarm_planner.py` and `route_planner.py` import from `core/geometry.py`
- Removed unused imports identified by static analysis

### Regression test suite
Created `tests/test_regression.py` with 16 test cases:
- 5 v0.1 regression tests (exact output matching for default scenario)
- 5 polygon pipeline tests (strip partition, boundaries, routing)
- 6 geometry validation tests (coverage gaps, consistency, error handling)

### Documentation
- Architecture diagram: `docs/architecture/002_architecture_v0.5.md`
- Professional README with progressive architecture layers
- Version stabilized at 0.5.0

### Testing protocol
All phases after this must pass:
1. `pytest tests/ -v` — all tests PASS
2. Default scenario regression: GO WITH CAUTION, 67.7%, 2h 03m, 4 sectors, 1.0 balance
3. No behavioral changes to v0.1 outputs

## Consequences

**Positive**:
- Single source of truth for geometry operations (no duplication)
- Formal regression suite catches regressions automatically
- Version 0.5.0 is a documented, stable baseline
- Testing protocol prevents silent breakage in future phases

**Negative**:
- Regression tests are tied to specific output values (fragile if constants change)
- Architecture documentation must be maintained alongside code

**Mitigations**:
- Test values derived from deterministic pipeline — they only change if the algorithm changes
- Roadmap status file (`docs/roadmap_status.md`) tracks documentation updates per phase
