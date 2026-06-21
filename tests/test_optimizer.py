"""
Phase 7.4 — Swarm Optimizer Tests

Tests for OptimizationObjective, OptimizationResult, and optimize_swarm()
with deterministic hill-climbing optimization.
"""

import pytest

from core.swarm_optimizer import (
    OptimizationObjective,
    OptimizationResult,
    optimize_swarm,
    _default_objectives,
    _extract_metrics,
    _compute_score,
)
from core.mission_intake import create_mission_profile
from core.environment_analyzer import analyze_environment
from core.swarm_planner import plan_swarm
from core.route_planner import plan_routes
from core.resource_planner import plan_resources
from core.geometry import FieldGeometry


def _setup_pipeline(**kwargs):
    """Run the full pipeline and return all objects."""
    defaults = dict(
        field_size_ha=50.0, crop_type="wheat", num_drones=4,
        battery_capacity_mah=5000, liquid_capacity_l=10.0,
        temperature_c=25, wind_speed_kmh=10,
    )
    defaults.update(kwargs)
    profile = create_mission_profile(**defaults)
    assessment = analyze_environment(profile)
    return profile, assessment


# ===========================================================================
# Dataclass Tests
# ===========================================================================

class TestDataclasses:

    def test_optimization_objective_fields(self):
        obj = OptimizationObjective(name="time", weight=0.3, direction="minimize")
        assert obj.name == "time"
        assert obj.weight == 0.3
        assert obj.direction == "minimize"

    def test_default_objectives(self):
        objs = _default_objectives()
        assert len(objs) == 4
        names = {o.name for o in objs}
        assert names == {"time", "battery", "coverage", "balance"}
        total_weight = sum(o.weight for o in objs)
        assert abs(total_weight - 1.0) < 0.01

    def test_optimization_result_fields(self):
        profile, assessment = _setup_pipeline()
        result = optimize_swarm(profile, assessment, max_iterations=1)

        assert isinstance(result, OptimizationResult)
        assert result.original_plan is not None
        assert result.optimized_plan is not None
        assert isinstance(result.improvements, dict)
        assert isinstance(result.iterations, int)
        assert isinstance(result.converged, bool)
        assert isinstance(result.original_score, float)
        assert isinstance(result.optimized_score, float)


# ===========================================================================
# Scoring Tests
# ===========================================================================

class TestScoring:

    def test_extract_metrics(self):
        profile, assessment = _setup_pipeline()
        swarm = plan_swarm(profile, assessment)
        routes = plan_routes(swarm, assessment)
        resources = plan_resources(profile, routes)
        metrics = _extract_metrics(swarm, routes, resources)

        assert "time" in metrics
        assert "battery" in metrics
        assert "coverage" in metrics
        assert "balance" in metrics
        assert metrics["time"] > 0
        assert metrics["coverage"] > 0

    def test_baseline_score_is_one(self):
        """When metrics == baseline, normalized score should be sum(weights) ≈ 1.0."""
        profile, assessment = _setup_pipeline()
        swarm = plan_swarm(profile, assessment)
        routes = plan_routes(swarm, assessment)
        resources = plan_resources(profile, routes)
        metrics = _extract_metrics(swarm, routes, resources)
        objs = _default_objectives()
        score = _compute_score(metrics, objs, metrics)

        assert abs(score - 1.0) < 0.01

    def test_improved_minimize_increases_score(self):
        """Better (lower) minimize metric → higher score."""
        objs = [OptimizationObjective("time", 1.0, "minimize")]
        baseline = {"time": 100.0}
        improved = {"time": 80.0}  # 20% better
        score = _compute_score(improved, objs, baseline)
        assert score > 1.0  # 100/80 = 1.25

    def test_improved_maximize_increases_score(self):
        """Better (higher) maximize metric → higher score."""
        objs = [OptimizationObjective("coverage", 1.0, "maximize")]
        baseline = {"coverage": 90.0}
        improved = {"coverage": 95.0}
        score = _compute_score(improved, objs, baseline)
        assert score > 1.0  # 95/90 ≈ 1.056

    def test_degraded_minimize_decreases_score(self):
        """Worse (higher) minimize metric → lower score."""
        objs = [OptimizationObjective("time", 1.0, "minimize")]
        baseline = {"time": 100.0}
        degraded = {"time": 120.0}
        score = _compute_score(degraded, objs, baseline)
        assert score < 1.0  # 100/120 ≈ 0.833


# ===========================================================================
# Optimization Tests
# ===========================================================================

class TestOptimization:

    def test_optimize_returns_valid_result(self):
        profile, assessment = _setup_pipeline()
        result = optimize_swarm(profile, assessment)

        assert result.optimized_score >= result.original_score
        assert result.iterations >= 1
        assert isinstance(result.explanation, str)

    def test_optimized_plan_is_valid_swarm_plan(self):
        profile, assessment = _setup_pipeline()
        result = optimize_swarm(profile, assessment)

        plan = result.optimized_plan
        assert len(plan.sectors) > 0
        assert plan.balance_score >= 0

    def test_optimized_routes_are_valid(self):
        profile, assessment = _setup_pipeline()
        result = optimize_swarm(profile, assessment)

        routes = result.optimized_routes
        assert len(routes.routes) > 0
        assert routes.total_distance_m > 0

    def test_improvements_dict_has_all_objectives(self):
        profile, assessment = _setup_pipeline()
        result = optimize_swarm(profile, assessment)

        for obj_name in ["time", "battery", "coverage", "balance"]:
            assert obj_name in result.improvements

    def test_original_plan_preserved(self):
        """Original plan is returned unchanged in the result."""
        profile, assessment = _setup_pipeline()
        swarm_before = plan_swarm(profile, assessment)
        result = optimize_swarm(profile, assessment)

        # Original plan sectors should match
        assert len(result.original_plan.sectors) == len(swarm_before.sectors)
        assert result.original_plan.balance_score == swarm_before.balance_score


# ===========================================================================
# Convergence Tests
# ===========================================================================

class TestConvergence:

    def test_converges_within_max_iterations(self):
        profile, assessment = _setup_pipeline()
        result = optimize_swarm(profile, assessment, max_iterations=50)

        assert result.iterations <= 50

    def test_converges_with_low_max_iterations(self):
        profile, assessment = _setup_pipeline()
        result = optimize_swarm(profile, assessment, max_iterations=2)

        assert result.iterations <= 2

    def test_single_iteration(self):
        profile, assessment = _setup_pipeline()
        result = optimize_swarm(profile, assessment, max_iterations=1)

        assert result.iterations == 1
        assert result.optimized_score >= result.original_score

    def test_returns_original_if_no_improvement(self):
        """If no improvement found, optimized plan equals original."""
        profile, assessment = _setup_pipeline()
        result = optimize_swarm(profile, assessment, max_iterations=50)

        if result.optimized_score == result.original_score:
            assert result.original_plan.balance_score == result.optimized_plan.balance_score
            assert "no improvement" in result.explanation.lower() or "optimal" in result.explanation.lower()


# ===========================================================================
# Custom Objectives Tests
# ===========================================================================

class TestCustomObjectives:

    def test_time_only_objective(self):
        profile, assessment = _setup_pipeline()
        objs = [OptimizationObjective("time", 1.0, "minimize")]
        result = optimize_swarm(profile, assessment, objectives=objs)

        assert isinstance(result, OptimizationResult)
        assert "time" in result.improvements

    def test_balance_only_objective(self):
        profile, assessment = _setup_pipeline()
        objs = [OptimizationObjective("balance", 1.0, "maximize")]
        result = optimize_swarm(profile, assessment, objectives=objs)

        assert "balance" in result.improvements

    def test_zero_weight_objective_ignored(self):
        profile, assessment = _setup_pipeline()
        objs = [
            OptimizationObjective("time", 0.0, "minimize"),
            OptimizationObjective("balance", 1.0, "maximize"),
        ]
        result = optimize_swarm(profile, assessment, objectives=objs)

        assert isinstance(result, OptimizationResult)

    def test_invalid_direction_raises(self):
        profile, assessment = _setup_pipeline()
        objs = [OptimizationObjective("time", 1.0, "invalid")]
        with pytest.raises(ValueError, match="Invalid direction"):
            optimize_swarm(profile, assessment, objectives=objs)

    def test_zero_total_weight_raises(self):
        profile, assessment = _setup_pipeline()
        objs = [OptimizationObjective("time", 0.0, "minimize")]
        with pytest.raises(ValueError, match="Total objective weight"):
            optimize_swarm(profile, assessment, objectives=objs)


# ===========================================================================
# Determinism Tests
# ===========================================================================

class TestDeterminism:

    def test_same_inputs_produce_identical_results(self):
        """Optimization must be fully deterministic."""
        results = []
        for _ in range(3):
            profile, assessment = _setup_pipeline()
            result = optimize_swarm(profile, assessment, max_iterations=10)
            results.append(result)

        for r in results[1:]:
            assert r.optimized_score == results[0].optimized_score
            assert r.iterations == results[0].iterations
            assert r.converged == results[0].converged
            assert r.improvements == results[0].improvements


# ===========================================================================
# Polygon Pipeline Integration
# ===========================================================================

class TestPolygonPipelineOptimization:

    def test_polygon_field_optimization(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        profile, assessment = _setup_pipeline(
            field_size_ha=fg.area_ha, field_geometry=fg, num_drones=4,
        )
        result = optimize_swarm(profile, assessment)

        assert isinstance(result, OptimizationResult)
        assert result.optimized_plan is not None
        assert result.optimized_routes is not None


# ===========================================================================
# v0.1 Backward Compatibility
# ===========================================================================

class TestBackwardCompatibility:

    def test_pipeline_unchanged_without_optimizer(self):
        """Existing pipeline produces identical output when optimizer is not invoked."""
        from core.risk_engine import evaluate_risks
        from core.decision_engine import generate_recommendation

        profile = create_mission_profile(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assessment = analyze_environment(profile)
        swarm = plan_swarm(profile, assessment)
        routes = plan_routes(swarm, assessment)
        resources = plan_resources(profile, routes)
        risks = evaluate_risks(profile, assessment, resources, routes)
        rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)

        assert rec.go_no_go == "GO WITH CAUTION"
        assert round(rec.confidence_pct, 1) == 67.7
        assert swarm.partition_method == "grid"
        assert len(swarm.sectors) == 4
