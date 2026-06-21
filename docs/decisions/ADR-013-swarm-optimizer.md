# ADR-013: Swarm Optimizer (Phase 7.4)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 7.4 — Intelligence Layer (Swarm Optimization)

## Context

With SwarmStateManager (7.1), ReallocationEngine (7.2), and MissionAdapter (7.3) implemented, the Intelligence Layer needs a multi-objective optimizer to explore plan alternatives and suggest improvements.

Design options considered:
- **Genetic algorithm**: population-based, stochastic — rejected (randomness, complexity)
- **Simulated annealing**: temperature-based acceptance — rejected (randomness)
- **Hill-climbing**: deterministic, greedy — selected (explainable, reproducible)
- **ML/RL**: learned policies — rejected (scope, reproducibility)

## Decision

Adopt **deterministic hill-climbing** with drone count perturbation:

```python
def optimize_swarm(profile, assessment, objectives?, max_iterations=50)
    → OptimizationResult

Algorithm:
1. Evaluate baseline score from plan_swarm() + plan_routes()
2. Each iteration: try ±1 drone from current best
3. Recompute full pipeline (no duplicate logic)
4. Accept if multi-objective score strictly improves
5. Converge after 5 iterations with no improvement
```

### Key design decisions

1. **Deterministic, no randomness** — same inputs always produce identical output. No random perturbation, no stochastic acceptance. Hill-climbing tries +1 then -1 drone in fixed order.

2. **Opt-in only** — existing pipeline behavior is completely unchanged unless `optimize_swarm()` is explicitly called. Zero impact on default behavior.

3. **Full pipeline reuse** — each candidate is evaluated via `plan_swarm()` → `plan_routes()` → `plan_resources()`. No duplicate planning logic.

4. **Multi-objective scoring** — weighted sum of normalized metrics:
   ```
   score = Σ(weight × normalize(metric))
   minimize: baseline/current  (lower is better → higher ratio)
   maximize: current/baseline  (higher is better → higher ratio)
   ```

5. **Configurable objectives** — weights and directions are user-controllable:
   - Default: time=0.3, battery=0.3, coverage=0.2, balance=0.2
   - Custom objectives override defaults entirely

6. **Convergence protection**:
   - Bounded iterations (default 50, configurable)
   - Patience: 5 consecutive no-improvement iterations → converge
   - Returns original plan if no improvement found

7. **Drone count perturbation** — the optimizer explores ±1 drone from baseline, not sector boundary shifts. This is the most impactful single variable and keeps the search space bounded. Sector geometry perturbation is deferred to a future phase.

## Consequences

**Positive**:
- Fully deterministic and reproducible
- Explainable: every improvement is logged with metrics
- Zero impact on existing pipeline when not invoked
- Configurable objectives allow different optimization priorities
- Convergence is guaranteed (bounded iterations + patience)

**Negative**:
- Hill-climbing can get stuck at local optima
- Only explores drone count axis — does not perturb sector boundaries
- Score normalization uses baseline as reference (not global optimum)

**Mitigations**:
- For the default 50ha/4-drone scenario, the optimizer finds 5 drones as optimal (+3.5% score, −30% time)
- Local optima risk is low given the small search space (drone count)
- Future phases can extend the perturbation space
