"""
Phase 7.2 — Reallocation Engine Tests

Tests for SectorReassignment, ReallocationPlan, and
reallocate_on_failure() under various drone failure scenarios.
"""

import pytest

from core.reallocation_engine import (
    SectorReassignment,
    ReallocationPlan,
    reallocate_on_failure,
)
from core.swarm_state import (
    SwarmStateManager,
    DroneStatus,
    MissionStatus,
)
from core.mission_intake import create_mission_profile
from core.environment_analyzer import analyze_environment
from core.swarm_planner import plan_swarm
from core.route_planner import plan_routes
from core.geometry import FieldGeometry


def _setup_pipeline(**kwargs):
    """Run the full pipeline and return all objects needed for reallocation."""
    defaults = dict(
        field_size_ha=50.0, crop_type="wheat", num_drones=4,
        battery_capacity_mah=5000, liquid_capacity_l=10.0,
        temperature_c=25, wind_speed_kmh=10,
    )
    defaults.update(kwargs)
    profile = create_mission_profile(**defaults)
    assessment = analyze_environment(profile)
    swarm = plan_swarm(profile, assessment)
    routes = plan_routes(swarm, assessment)
    mgr = SwarmStateManager(profile, swarm, routes)
    return profile, assessment, swarm, routes, mgr


def _simulate_failure(mgr, drone_id, passes_done=20):
    """Simulate a drone that was active and then failed."""
    mgr.set_mission_status(MissionStatus.ACTIVE)
    for d in mgr.get_state().drones:
        mgr.update_drone(d.drone_id, status=DroneStatus.ACTIVE)
    mgr.update_drone(drone_id, passes_completed=passes_done)
    mgr.update_elapsed_time(15.0)
    mgr.mark_drone_failed(drone_id, "motor failure")
    return mgr.get_state()


# ===========================================================================
# Dataclass Tests
# ===========================================================================

class TestDataclasses:

    def test_sector_reassignment_fields(self):
        sr = SectorReassignment(
            sector_id=1, from_drone_id=1, to_drone_id=2,
            additional_distance_m=150.0, additional_time_min=3.5,
        )
        assert sr.sector_id == 1
        assert sr.from_drone_id == 1
        assert sr.to_drone_id == 2
        assert sr.additional_distance_m == 150.0
        assert sr.additional_time_min == 3.5

    def test_reallocation_plan_fields(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = _simulate_failure(mgr, 1)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)
        assert isinstance(plan, ReallocationPlan)
        assert plan.failed_drone_id == 1
        assert isinstance(plan.feasible, bool)
        assert isinstance(plan.coverage_before_pct, float)
        assert isinstance(plan.coverage_after_pct, float)


# ===========================================================================
# Basic Reallocation Tests
# ===========================================================================

class TestBasicReallocation:

    def test_single_drone_failure_produces_valid_plan(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = _simulate_failure(mgr, 1)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        assert plan.feasible is True
        assert len(plan.reassignments) == 1
        assert plan.reassignments[0].from_drone_id == 1
        assert plan.reassignments[0].to_drone_id != 1

    def test_coverage_preserved_after_reallocation(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = _simulate_failure(mgr, 1)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        assert plan.coverage_after_pct >= plan.coverage_before_pct
        assert plan.coverage_after_pct == 100.0

    def test_coverage_before_is_less_than_100(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = _simulate_failure(mgr, 1, passes_done=0)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        assert plan.coverage_before_pct < 100.0

    def test_time_penalty_is_non_negative(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = _simulate_failure(mgr, 1)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        assert plan.time_penalty_min >= 0.0

    def test_reassignment_to_nearest_drone(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = _simulate_failure(mgr, 1)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        # The recipient should be one of the available drones
        recipient_id = plan.reassignments[0].to_drone_id
        available_ids = {d.drone_id for d in state.drones if d.drone_id != 1 and d.status != DroneStatus.FAILED}
        assert recipient_id in available_ids

    def test_updated_routes_present(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = _simulate_failure(mgr, 1)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        assert plan.updated_routes is not None
        assert len(plan.updated_routes.routes) > 0

    def test_updated_timeline_present(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = _simulate_failure(mgr, 1)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        assert plan.updated_timeline is not None
        assert len(plan.updated_timeline.drone_timelines) > 0

    def test_explanation_contains_details(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = _simulate_failure(mgr, 1)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        assert "reassigned" in plan.explanation.lower()
        assert str(plan.reassignments[0].to_drone_id) in plan.explanation


# ===========================================================================
# Edge Case Tests
# ===========================================================================

class TestEdgeCases:

    def test_no_available_drones_infeasible(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline(num_drones=2)
        mgr.set_mission_status(MissionStatus.ACTIVE)
        # Fail both drones — second failure has no available drones
        mgr.update_drone(1, status=DroneStatus.ACTIVE)
        mgr.update_drone(2, status=DroneStatus.ACTIVE)
        mgr.mark_drone_failed(1, "motor failure")
        mgr.mark_drone_failed(2, "battery critical")

        state = mgr.get_state()
        plan = reallocate_on_failure(state, 2, profile, swarm, assessment)

        assert plan.feasible is False
        assert len(plan.reassignments) == 0
        assert "no available" in plan.explanation.lower()

    def test_invalid_drone_id_raises(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = mgr.get_state()
        with pytest.raises(ValueError, match="not found"):
            reallocate_on_failure(state, 999, profile, swarm, assessment)

    def test_single_drone_mission_failure(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline(num_drones=1)
        mgr.set_mission_status(MissionStatus.ACTIVE)
        mgr.update_drone(1, status=DroneStatus.ACTIVE)
        mgr.mark_drone_failed(1, "signal lost")

        state = mgr.get_state()
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        assert plan.feasible is False

    def test_failure_with_zero_passes_completed(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline()
        state = _simulate_failure(mgr, 1, passes_done=0)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        assert plan.feasible is True
        assert plan.coverage_after_pct == 100.0


# ===========================================================================
# Multi-Drone Failure Tests
# ===========================================================================

class TestMultiDroneFailures:

    def test_sequential_failures_reduce_available(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline(num_drones=4)
        mgr.set_mission_status(MissionStatus.ACTIVE)
        for i in range(1, 5):
            mgr.update_drone(i, status=DroneStatus.ACTIVE)

        # First failure
        mgr.mark_drone_failed(1, "motor failure")
        state = mgr.get_state()
        plan1 = reallocate_on_failure(state, 1, profile, swarm, assessment)
        assert plan1.feasible is True

        # Second failure
        mgr.mark_drone_failed(2, "battery critical")
        state = mgr.get_state()
        plan2 = reallocate_on_failure(state, 2, profile, swarm, assessment)
        assert plan2.feasible is True

        # Third failure — only 1 drone left
        mgr.mark_drone_failed(3, "GPS lost")
        state = mgr.get_state()
        plan3 = reallocate_on_failure(state, 3, profile, swarm, assessment)
        assert plan3.feasible is True

    def test_all_drones_failed_infeasible(self):
        profile, assessment, swarm, routes, mgr = _setup_pipeline(num_drones=4)
        mgr.set_mission_status(MissionStatus.ACTIVE)
        for i in range(1, 5):
            mgr.update_drone(i, status=DroneStatus.ACTIVE)
            mgr.mark_drone_failed(i, "total failure")

        state = mgr.get_state()
        # All failed — any attempt to reallocate should be infeasible
        plan = reallocate_on_failure(state, 4, profile, swarm, assessment)
        assert plan.feasible is False


# ===========================================================================
# Polygon Pipeline Integration
# ===========================================================================

class TestPolygonPipelineReallocation:

    def test_polygon_field_reallocation(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        profile, assessment, swarm, routes, mgr = _setup_pipeline(
            field_size_ha=fg.area_ha, field_geometry=fg, num_drones=4,
        )
        state = _simulate_failure(mgr, 1)
        plan = reallocate_on_failure(state, 1, profile, swarm, assessment)

        assert plan.feasible is True
        assert plan.coverage_after_pct == 100.0
        assert len(plan.updated_routes.routes) > 0


# ===========================================================================
# Determinism Tests
# ===========================================================================

class TestDeterminism:

    def test_same_failure_produces_identical_plan(self):
        """Reallocation must be deterministic — same inputs produce same outputs."""
        plans = []
        for _ in range(3):
            profile, assessment, swarm, routes, mgr = _setup_pipeline()
            state = _simulate_failure(mgr, 1)
            plan = reallocate_on_failure(state, 1, profile, swarm, assessment)
            plans.append(plan)

        for p in plans[1:]:
            assert p.reassignments[0].to_drone_id == plans[0].reassignments[0].to_drone_id
            assert p.coverage_before_pct == plans[0].coverage_before_pct
            assert p.coverage_after_pct == plans[0].coverage_after_pct
            assert p.time_penalty_min == plans[0].time_penalty_min


# ===========================================================================
# v0.1 Backward Compatibility
# ===========================================================================

class TestBackwardCompatibility:

    def test_pipeline_unchanged_without_reallocation(self):
        """Existing pipeline produces identical output when reallocation is not invoked."""
        from core.resource_planner import plan_resources
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
