# ADR-012: Mission Adapter (Phase 7.3)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 7.3 — Intelligence Layer (Mission Adaptation)

## Context

With SwarmStateManager (7.1) and ReallocationEngine (7.2) in place, the system needs a mechanism to respond to mid-mission condition changes — wind shifts, resource depletion, and partial completion events.

Design options considered:
- **Autonomous adaptation**: system applies changes automatically
- **Recommendation-based**: system recommends actions for operator approval
- **Hybrid**: auto-apply safe changes, escalate risky ones

## Decision

Adopt a **strictly recommendation-based** adapter — no autonomous execution decisions:

```python
def adapt_mission(state, trigger, profile, assessment) → AdaptationResult

AdaptationResult.action ∈ {"continue", "modify", "abort"}
```

### Supported triggers

1. **wind_change** — `details: {new_wind_kmh: float}`
   - ≥ `max_wind_kmh` (35.0) → **abort**
   - Risk assessment non-viable → **abort**
   - Δ < 5 km/h and same flight conditions → **continue**
   - Otherwise → **modify** (full pipeline recomputation)

2. **resource_depletion** — `details: {battery_threshold_pct, liquid_threshold_l}`
   - No critical drones → **continue**
   - Some critical, others available → **modify** (return critical drones)
   - All critical → **abort**

3. **partial_completion** — `details: {}`
   - All sectors done → **continue** (wrapping up)
   - Remaining sectors + available drones → **modify** (replan with fewer drones)
   - Remaining sectors + no drones → **abort**

### Key design decisions

1. **No autonomous decisions** — every `AdaptationResult` is a recommendation. The operator must approve before changes take effect.

2. **Full pipeline recomputation** — wind changes and partial completions delegate to `create_mission_profile()` → `analyze_environment()` → `plan_swarm()` → `plan_routes()` → `plan_resources()` → `evaluate_risks()` → `generate_timeline()`. No duplicate logic.

3. **Weather thresholds from config** — uses `weather_thresholds.max_wind_kmh` from `config/settings.py`, not hard-coded values.

4. **Tolerance band for wind** — changes < 5 km/h that don't alter flight conditions are classified as "continue" to avoid unnecessary replanning.

5. **Resource depletion is state-based** — evaluates current `DroneState` values from the `MissionState`, not predicted future values.

## Consequences

**Positive**:
- Zero modifications to existing pipeline modules
- Purely additive — importing `mission_adapter` is opt-in
- All recomputation reuses existing pipeline functions
- Recommendation-based: operator retains full control
- Deterministic: same trigger produces identical recommendation

**Negative**:
- Resource depletion handler doesn't recompute routes (returns modify recommendation without modified plan)
- Partial completion replans the full field, not just remaining sectors
- No trigger chaining (can't handle wind + depletion simultaneously)

**Mitigations**:
- Resource depletion modify action provides explanation for operator to act on
- Phase 7.4 SwarmOptimizer can post-process partial completion plans
- Multiple triggers can be evaluated sequentially
