# ADR-008: Realism Layer Architecture (Phase 6)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 6 — Realism Layer (Simulation Physics)

## Context

The planning pipeline produced mission plans without physical realism — battery consumption, liquid usage, and flight timing were simplified abstractions. Phase 6 needed to introduce operational simulation while:
- Keeping all models deterministic and explainable
- Not modifying the existing 7-module pipeline
- Preserving v0.1 backward compatibility

Design choice: **additive layer** vs. **pipeline modification**.

## Decision

Adopt an **additive realism layer** — four new modules that consume pipeline outputs without modifying them:

### New modules

1. **`core/drone_physics.py`** — Speed, turn, payload, wind calculations
   - `compute_effective_speed()`: wind drag + payload weight reduce ground speed
   - `compute_turn_penalty()`: deceleration + arc + acceleration per turn
   - `compute_payload_power_factor()`: power multiplier from payload weight
   - `compute_wind_power_factor()`: power multiplier from wind drag
   - `PhysicsConfig` dataclass: all constants in one place (no magic numbers)

2. **`core/battery_model.py`** — Physics-based battery consumption
   - Base: distance * Wh/km
   - Factors: payload weight, wind drag, hover drain
   - Outputs: consumption %, swaps needed, flights per charge
   - `compute_battery_wh()`: shared helper for mAh→Wh conversion

3. **`core/liquid_model.py`** — Area-based liquid consumption
   - Consumption: field area * spray rate (crop-specific)
   - Refill events: triggered when tank runs empty
   - Outputs: loads needed, refill count, refill timeline

4. **`core/mission_timeline.py`** — Sequential event generation
   - Events: Launch → Transit → Spraying → Refill → Battery Swap → Return → Complete
   - Integrates physics, battery, and liquid models per drone
   - Human-readable timestamps via `_format_time()`

### Integration pattern
```python
# Existing pipeline (unchanged)
profile → assessment → swarm → routes → resources → risks → recommendation

# Additive realism layer (new)
timeline = generate_timeline(profile, routes, resources)
```

### UI
New "Mission Timeline" tab in `app.py`:
- Gantt-style timeline chart
- Per-drone expandable detail panels (physics, battery, liquid breakdowns)

### Constants
- `REFILL_TIME_MIN = 5.0` — consolidated in `config/settings.py`
- `BATTERY_SWAP_TIME_MIN = 3.0` — consolidated in `config/settings.py`
- `TRANSIT_DURATION_MIN = 0.5` — in `mission_timeline.py` (timeline-specific)

## Consequences

**Positive**:
- Zero changes to existing pipeline — purely additive
- All models are deterministic: same inputs produce same outputs
- Each model can be tested in isolation
- 28 new tests added; 44/44 total pass
- v0.1 outputs remain identical

**Negative**:
- `resource_planner.py` (v0.1) and `battery_model.py` (Phase 6) compute overlapping metrics (battery Wh, liquid loads)
- Four new modules increase codebase size by ~40%

**Mitigations**:
- Duplicated constants consolidated to `config/settings.py` (audit finding)
- `compute_battery_wh()` extracted as shared helper
- `resource_planner` could delegate to realism modules in future consolidation
