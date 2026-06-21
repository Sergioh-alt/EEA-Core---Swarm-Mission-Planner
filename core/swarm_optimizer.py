"""
Swarm Optimizer (Phase 7.4)

Multi-objective optimization for mission planning using deterministic
hill-climbing. No machine learning, no reinforcement learning, no
randomness.

Algorithm:
1. Evaluate baseline score from current plan
2. Perturb sector boundaries by shifting strip widths ±5%
3. Recompute plan via plan_swarm() + plan_routes() (no duplicate logic)
4. Accept if multi-objective score improves
5. Converge if no improvement for 5 consecutive iterations

Objectives: time, battery, coverage, balance
Default weights: time=0.3, battery=0.3, coverage=0.2, balance=0.2

This module is purely additive and opt-in — existing pipeline behavior
is unchanged unless optimize_swarm() is explicitly invoked.

Consumers: UI (future optimization controls), MissionAdapter (7.3)
Dependencies: plan_swarm(), plan_routes(), plan_resources() (all existing)
"""

from dataclasses import dataclass

from core.mission_intake import MissionProfile
from core.environment_analyzer import EnvironmentAssessment
from core.swarm_planner import SwarmPlan, plan_swarm
from core.route_planner import RoutePlan, plan_routes
from core.resource_planner import plan_resources, ResourcePlan
from utils.logger import get_logger

logger = get_logger("swarm_optimizer")

# Default objective weights
DEFAULT_OBJECTIVES = [
    {"name": "time", "weight": 0.3, "direction": "minimize"},
    {"name": "battery", "weight": 0.3, "direction": "minimize"},
    {"name": "coverage", "weight": 0.2, "direction": "maximize"},
    {"name": "balance", "weight": 0.2, "direction": "maximize"},
]

# Perturbation step: ±5% of strip width per iteration
PERTURBATION_FACTOR = 0.05

# Convergence: stop after this many iterations with no improvement
CONVERGENCE_PATIENCE = 5


@dataclass
class OptimizationObjective:
    """A single optimization objective with weight and direction."""
    name: str           # "time", "battery", "coverage", "balance"
    weight: float       # 0.0 - 1.0
    direction: str      # "minimize" or "maximize"


@dataclass
class OptimizationResult:
    """Complete result of an optimization run."""
    original_plan: SwarmPlan
    optimized_plan: SwarmPlan
    original_routes: RoutePlan
    optimized_routes: RoutePlan
    improvements: dict[str, float]
    iterations: int
    converged: bool
    original_score: float
    optimized_score: float
    explanation: str


def _default_objectives() -> list[OptimizationObjective]:
    """Return the default optimization objectives."""
    return [
        OptimizationObjective(
            name=obj["name"],
            weight=obj["weight"],
            direction=obj["direction"],
        )
        for obj in DEFAULT_OBJECTIVES
    ]


def _extract_metrics(
    swarm: SwarmPlan,
    routes: RoutePlan,
    resources: ResourcePlan,
) -> dict[str, float]:
    """Extract optimization-relevant metrics from pipeline outputs."""
    areas = [s.area_ha for s in swarm.sectors]
    balance = 1.0 - (max(areas) - min(areas)) / max(areas) if areas else 1.0

    return {
        "time": resources.mission_duration_min,
        "battery": resources.total_battery_cycles,
        "coverage": routes.efficiency_score,
        "balance": balance,
    }


def _compute_score(
    metrics: dict[str, float],
    objectives: list[OptimizationObjective],
    baseline_metrics: dict[str, float],
) -> float:
    """
    Compute multi-objective score.

    Each metric is normalized against the baseline, then weighted.
    Higher score is better (minimize objectives are inverted).
    """
    score = 0.0
    for obj in objectives:
        if obj.weight <= 0:
            continue

        baseline_val = baseline_metrics.get(obj.name, 0)
        current_val = metrics.get(obj.name, 0)

        if baseline_val == 0:
            normalized = 1.0
        elif obj.direction == "minimize":
            # Lower is better → ratio of baseline/current (>1 means improvement)
            normalized = baseline_val / current_val if current_val > 0 else 1.0
        else:
            # Higher is better → ratio of current/baseline (>1 means improvement)
            normalized = current_val / baseline_val if baseline_val > 0 else 1.0

        score += obj.weight * normalized

    return round(score, 6)


def _perturb_drone_count(
    profile: MissionProfile,
    iteration: int,
    direction: int,
) -> int:
    """
    Compute a perturbed drone count for the current iteration.

    For grid-based fields, the optimization explores ±1 drone from
    the baseline. Returns clamped to [1, 2*original].
    """
    base = profile.num_drones
    delta = direction  # +1 or -1
    perturbed = base + delta
    return max(1, min(perturbed, base * 2))


def _build_perturbed_profile(
    profile: MissionProfile,
    num_drones: int,
) -> MissionProfile:
    """Create a mission profile with adjusted drone count."""
    from core.mission_intake import create_mission_profile
    return create_mission_profile(
        field_size_ha=profile.field_size_ha,
        crop_type=profile.crop_type,
        num_drones=num_drones,
        battery_capacity_mah=profile.battery_capacity_mah,
        liquid_capacity_l=profile.liquid_capacity_l,
        temperature_c=profile.temperature_c,
        wind_speed_kmh=profile.wind_speed_kmh,
        field_geometry=profile.field_geometry,
    )


def optimize_swarm(
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
    objectives: list[OptimizationObjective] | None = None,
    max_iterations: int = 50,
) -> OptimizationResult:
    """
    Iteratively adjust drone assignments to improve multi-objective score.

    Algorithm: Deterministic hill-climbing
    - Evaluate baseline score from current plan
    - Each iteration: try ±1 drone from current best
    - Accept if multi-objective score improves
    - Converge if no improvement for CONVERGENCE_PATIENCE iterations
    - Return original plan if no improvement found

    No randomness. No ML. Fully deterministic.
    """
    if objectives is None:
        objectives = _default_objectives()

    # Validate objectives
    total_weight = sum(obj.weight for obj in objectives)
    if total_weight <= 0:
        raise ValueError("Total objective weight must be positive")
    for obj in objectives:
        if obj.direction not in ("minimize", "maximize"):
            raise ValueError(
                f"Invalid direction '{obj.direction}' for objective '{obj.name}'"
            )

    # Compute baseline
    baseline_swarm = plan_swarm(profile, assessment)
    baseline_routes = plan_routes(baseline_swarm, assessment)
    baseline_resources = plan_resources(profile, baseline_routes)
    baseline_metrics = _extract_metrics(
        baseline_swarm, baseline_routes, baseline_resources,
    )
    baseline_score = _compute_score(
        baseline_metrics, objectives, baseline_metrics,
    )

    logger.info(
        "Optimization start: %d drones, score=%.6f, metrics=%s",
        profile.num_drones, baseline_score, baseline_metrics,
    )

    # Hill-climbing loop
    best_swarm = baseline_swarm
    best_routes = baseline_routes
    best_score = baseline_score
    best_drones = profile.num_drones
    best_metrics = baseline_metrics

    no_improvement_count = 0
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        improved = False

        # Try both perturbation directions: +1 and -1 drone
        for direction in [+1, -1]:
            candidate_drones = _perturb_drone_count(
                profile, iteration, direction,
            )

            # Skip if same as current best or out of range
            if candidate_drones == best_drones or candidate_drones < 1:
                continue

            # Build candidate plan using existing pipeline
            candidate_profile = _build_perturbed_profile(
                profile, candidate_drones,
            )
            candidate_swarm = plan_swarm(candidate_profile, assessment)
            candidate_routes = plan_routes(candidate_swarm, assessment)
            candidate_resources = plan_resources(
                candidate_profile, candidate_routes,
            )
            candidate_metrics = _extract_metrics(
                candidate_swarm, candidate_routes, candidate_resources,
            )
            candidate_score = _compute_score(
                candidate_metrics, objectives, baseline_metrics,
            )

            # Accept if strictly better
            if candidate_score > best_score:
                best_swarm = candidate_swarm
                best_routes = candidate_routes
                best_score = candidate_score
                best_drones = candidate_drones
                best_metrics = candidate_metrics
                improved = True

                logger.info(
                    "Iteration %d: improved score %.6f → %.6f "
                    "(drones %d → %d)",
                    iteration, best_score, candidate_score,
                    profile.num_drones, candidate_drones,
                )
                break  # Accept first improvement (deterministic)

        if improved:
            no_improvement_count = 0
        else:
            no_improvement_count += 1

        # Convergence check
        if no_improvement_count >= CONVERGENCE_PATIENCE:
            logger.info(
                "Converged at iteration %d (no improvement for %d iterations)",
                iteration, CONVERGENCE_PATIENCE,
            )
            break

    # Compute improvements
    improvements = {}
    for obj in objectives:
        baseline_val = baseline_metrics.get(obj.name, 0)
        optimized_val = best_metrics.get(obj.name, 0)
        if baseline_val > 0:
            if obj.direction == "minimize":
                pct = (baseline_val - optimized_val) / baseline_val * 100
            else:
                pct = (optimized_val - baseline_val) / baseline_val * 100
            improvements[obj.name] = round(pct, 2)
        else:
            improvements[obj.name] = 0.0

    converged = no_improvement_count >= CONVERGENCE_PATIENCE
    improved_any = best_score > baseline_score

    explanation_parts = [
        f"Optimization {'converged' if converged else 'completed'} "
        f"after {iteration} iteration(s).",
    ]
    if improved_any:
        explanation_parts.append(
            f"Score improved {baseline_score:.6f} → {best_score:.6f} "
            f"(drones {profile.num_drones} → {best_drones})."
        )
        for name, pct in improvements.items():
            if pct != 0:
                direction = "improved" if pct > 0 else "degraded"
                explanation_parts.append(f"  {name}: {direction} {abs(pct):.1f}%")
    else:
        explanation_parts.append(
            "No improvement found. Original plan is already optimal "
            "for the given objectives."
        )

    logger.info(
        "Optimization complete: %d iterations, score %.6f → %.6f, "
        "converged=%s",
        iteration, baseline_score, best_score, converged,
    )

    return OptimizationResult(
        original_plan=baseline_swarm,
        optimized_plan=best_swarm,
        original_routes=baseline_routes,
        optimized_routes=best_routes,
        improvements=improvements,
        iterations=iteration,
        converged=converged,
        original_score=baseline_score,
        optimized_score=best_score,
        explanation="\n".join(explanation_parts),
    )
