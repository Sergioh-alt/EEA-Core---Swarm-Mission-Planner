"""
Phase 7.3 — Mission Adapter Tests

Tests for AdaptationTrigger, AdaptationResult, and adapt_mission()
under various mid-mission condition changes.
"""

import pytest

from core.mission_adapter import (
    AdaptationTrigger,
    AdaptationResult,
    adapt_mission,
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
from config.settings import weather_thresholds


def _setup_pipeline(**kwargs):
    """Run the full pipeline and return all objects needed for adaptation."""
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


def _activate_mission(mgr, passes_done=20):
    """Simulate an active mission with some progress."""
    mgr.set_mission_status(MissionStatus.ACTIVE)
    for d in mgr.get_state().drones:
        mgr.update_drone(d.drone_id, status=DroneStatus.ACTIVE,
                         passes_completed=passes_done,
                         battery_remaining_pct=70.0,
                         liquid_remaining_l=6.0)
    mgr.update_elapsed_time(15.0)
    return mgr.get_state()


# ===========================================================================
# Dataclass Tests
# ===========================================================================

class TestDataclasses:

    def test_adaptation_trigger_fields(self):
        trigger = AdaptationTrigger(
            trigger_type="wind_change",
            timestamp_min=15.0,
            details={"new_wind_kmh": 25.0},
        )
        assert trigger.trigger_type == "wind_change"
        assert trigger.timestamp_min == 15.0
        assert trigger.details["new_wind_kmh"] == 25.0

    def test_adaptation_result_fields(self):
        profile, assessment, _, _, mgr = _setup_pipeline()
        state = _activate_mission(mgr)
        trigger = AdaptationTrigger("wind_change", 15.0, {"new_wind_kmh": 12.0})
        result = adapt_mission(state, trigger, profile, assessment)

        assert isinstance(result, AdaptationResult)
        assert result.trigger is trigger
        assert result.action in ("continue", "modify", "abort")
        assert isinstance(result.explanation, str)


# ===========================================================================
# Wind Change Tests
# ===========================================================================

class TestWindChange:

    def test_small_wind_increase_continues(self):
        """Small wind change within same flight conditions → continue."""
        profile, assessment, _, _, mgr = _setup_pipeline(wind_speed_kmh=15)
        state = _activate_mission(mgr)
        trigger = AdaptationTrigger("wind_change", 15.0, {"new_wind_kmh": 18.0})
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "continue"
        assert result.modified_plan is None
        assert result.modified_routes is None

    def test_significant_wind_increase_modifies(self):
        """Significant wind increase → modify plan."""
        profile, assessment, _, _, mgr = _setup_pipeline(wind_speed_kmh=10)
        state = _activate_mission(mgr)
        trigger = AdaptationTrigger("wind_change", 15.0, {"new_wind_kmh": 25.0})
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "modify"
        assert result.modified_plan is not None
        assert result.modified_routes is not None
        assert result.modified_timeline is not None
        assert "modify" in result.explanation.lower() or "modification" in result.explanation.lower()

    def test_extreme_wind_aborts(self):
        """Wind exceeds no-fly threshold → abort."""
        profile, assessment, _, _, mgr = _setup_pipeline(wind_speed_kmh=10)
        state = _activate_mission(mgr)
        no_fly_wind = weather_thresholds.max_wind_kmh + 5
        trigger = AdaptationTrigger("wind_change", 15.0, {"new_wind_kmh": no_fly_wind})
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "abort"
        assert "abort" in result.explanation.lower()
        assert result.modified_plan is None

    def test_wind_at_exact_threshold_aborts(self):
        """Wind exactly at no-fly threshold → abort."""
        profile, assessment, _, _, mgr = _setup_pipeline(wind_speed_kmh=10)
        state = _activate_mission(mgr)
        trigger = AdaptationTrigger("wind_change", 15.0,
                                    {"new_wind_kmh": weather_thresholds.max_wind_kmh})
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "abort"

    def test_wind_decrease_continues(self):
        """Wind decreases → continue (within tolerance)."""
        profile, assessment, _, _, mgr = _setup_pipeline(wind_speed_kmh=15)
        state = _activate_mission(mgr)
        trigger = AdaptationTrigger("wind_change", 15.0, {"new_wind_kmh": 14.0})
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "continue"

    def test_wind_change_explanation_includes_values(self):
        """Explanation includes old and new wind values."""
        profile, assessment, _, _, mgr = _setup_pipeline(wind_speed_kmh=10)
        state = _activate_mission(mgr)
        trigger = AdaptationTrigger("wind_change", 15.0, {"new_wind_kmh": 25.0})
        result = adapt_mission(state, trigger, profile, assessment)

        assert "10.0" in result.explanation
        assert "25.0" in result.explanation


# ===========================================================================
# Resource Depletion Tests
# ===========================================================================

class TestResourceDepletion:

    def test_no_depletion_continues(self):
        """All drones within thresholds → continue."""
        profile, assessment, _, _, mgr = _setup_pipeline()
        state = _activate_mission(mgr)
        trigger = AdaptationTrigger("resource_depletion", 15.0, {
            "battery_threshold_pct": 15.0,
            "liquid_threshold_l": 1.0,
        })
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "continue"

    def test_battery_critical_modifies(self):
        """Some drones battery critical → modify."""
        profile, assessment, _, _, mgr = _setup_pipeline()
        mgr.set_mission_status(MissionStatus.ACTIVE)
        for d in mgr.get_state().drones:
            mgr.update_drone(d.drone_id, status=DroneStatus.ACTIVE)
        # Set drone 1 critically low
        mgr.update_drone(1, battery_remaining_pct=10.0, liquid_remaining_l=5.0)
        mgr.update_drone(2, battery_remaining_pct=50.0, liquid_remaining_l=5.0)
        mgr.update_drone(3, battery_remaining_pct=50.0, liquid_remaining_l=5.0)
        mgr.update_drone(4, battery_remaining_pct=50.0, liquid_remaining_l=5.0)
        mgr.update_elapsed_time(30.0)

        state = mgr.get_state()
        trigger = AdaptationTrigger("resource_depletion", 30.0, {
            "battery_threshold_pct": 15.0,
            "liquid_threshold_l": 1.0,
        })
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "modify"
        assert "Drone 1" in result.explanation

    def test_liquid_critical_modifies(self):
        """Some drones liquid critical → modify."""
        profile, assessment, _, _, mgr = _setup_pipeline()
        mgr.set_mission_status(MissionStatus.ACTIVE)
        for d in mgr.get_state().drones:
            mgr.update_drone(d.drone_id, status=DroneStatus.ACTIVE,
                             battery_remaining_pct=50.0, liquid_remaining_l=5.0)
        mgr.update_drone(2, liquid_remaining_l=0.5)
        mgr.update_elapsed_time(25.0)

        state = mgr.get_state()
        trigger = AdaptationTrigger("resource_depletion", 25.0, {
            "battery_threshold_pct": 15.0,
            "liquid_threshold_l": 1.0,
        })
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "modify"
        assert "Drone 2" in result.explanation

    def test_all_drones_depleted_aborts(self):
        """All drones critically depleted → abort."""
        profile, assessment, _, _, mgr = _setup_pipeline()
        mgr.set_mission_status(MissionStatus.ACTIVE)
        for d in mgr.get_state().drones:
            mgr.update_drone(d.drone_id, status=DroneStatus.ACTIVE,
                             battery_remaining_pct=5.0, liquid_remaining_l=0.2)
        mgr.update_elapsed_time(50.0)

        state = mgr.get_state()
        trigger = AdaptationTrigger("resource_depletion", 50.0, {
            "battery_threshold_pct": 15.0,
            "liquid_threshold_l": 1.0,
        })
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "abort"
        assert "abort" in result.explanation.lower()


# ===========================================================================
# Partial Completion Tests
# ===========================================================================

class TestPartialCompletion:

    def test_all_sectors_done_continues(self):
        """All sectors completed → continue to mission end."""
        profile, assessment, _, _, mgr = _setup_pipeline()
        mgr.set_mission_status(MissionStatus.ACTIVE)
        for d in mgr.get_state().drones:
            mgr.update_drone(d.drone_id, status=DroneStatus.COMPLETED,
                             passes_completed=d.passes_total)
        mgr.update_elapsed_time(60.0)

        state = mgr.get_state()
        trigger = AdaptationTrigger("partial_completion", 60.0, {})
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "continue"
        assert "100.0%" in result.explanation or "completed" in result.explanation.lower()

    def test_some_sectors_remaining_modifies(self):
        """Some sectors remaining → modify with replan."""
        profile, assessment, _, _, mgr = _setup_pipeline()
        mgr.set_mission_status(MissionStatus.ACTIVE)
        # Complete drones 1 and 2, leave 3 and 4 active
        mgr.update_drone(1, status=DroneStatus.COMPLETED,
                         passes_completed=mgr.get_drone(1).passes_total)
        mgr.update_drone(2, status=DroneStatus.COMPLETED,
                         passes_completed=mgr.get_drone(2).passes_total)
        mgr.update_drone(3, status=DroneStatus.ACTIVE, passes_completed=10)
        mgr.update_drone(4, status=DroneStatus.ACTIVE, passes_completed=10)
        mgr.update_elapsed_time(40.0)

        state = mgr.get_state()
        trigger = AdaptationTrigger("partial_completion", 40.0, {})
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "modify"
        assert result.modified_plan is not None
        assert result.modified_routes is not None
        assert result.modified_timeline is not None

    def test_no_drones_available_aborts(self):
        """Remaining sectors but no available drones → abort."""
        profile, assessment, _, _, mgr = _setup_pipeline()
        mgr.set_mission_status(MissionStatus.ACTIVE)
        for d in mgr.get_state().drones:
            mgr.update_drone(d.drone_id, status=DroneStatus.ACTIVE)
            mgr.mark_drone_failed(d.drone_id, "total failure")
        mgr.update_elapsed_time(20.0)

        state = mgr.get_state()
        trigger = AdaptationTrigger("partial_completion", 20.0, {})
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "abort"
        assert "no drones" in result.explanation.lower()

    def test_partial_completion_replans_with_fewer_drones(self):
        """Replan uses remaining available drones, not original count."""
        profile, assessment, _, _, mgr = _setup_pipeline(num_drones=4)
        mgr.set_mission_status(MissionStatus.ACTIVE)
        # Drone 1 completed, drones 2-3 failed, drone 4 active
        mgr.update_drone(1, status=DroneStatus.COMPLETED,
                         passes_completed=mgr.get_drone(1).passes_total)
        mgr.update_drone(2, status=DroneStatus.ACTIVE)
        mgr.mark_drone_failed(2, "motor failure")
        mgr.update_drone(3, status=DroneStatus.ACTIVE)
        mgr.mark_drone_failed(3, "battery critical")
        mgr.update_drone(4, status=DroneStatus.ACTIVE, passes_completed=10)
        mgr.update_elapsed_time(35.0)

        state = mgr.get_state()
        trigger = AdaptationTrigger("partial_completion", 35.0, {})
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action == "modify"
        assert result.modified_profile is not None
        # Only drone 1 (completed) and drone 4 (active) are available
        # for 3 remaining sectors → min(2, 3) = 2
        assert result.modified_profile.num_drones <= 2


# ===========================================================================
# Invalid Trigger Tests
# ===========================================================================

class TestInvalidTrigger:

    def test_unknown_trigger_raises(self):
        profile, assessment, _, _, mgr = _setup_pipeline()
        state = mgr.get_state()
        trigger = AdaptationTrigger("earthquake", 0.0, {})
        with pytest.raises(ValueError, match="Unknown trigger type"):
            adapt_mission(state, trigger, profile, assessment)


# ===========================================================================
# Polygon Pipeline Integration
# ===========================================================================

class TestPolygonPipelineAdaptation:

    def test_polygon_field_wind_change(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        profile, assessment, _, _, mgr = _setup_pipeline(
            field_size_ha=fg.area_ha, field_geometry=fg, num_drones=4,
        )
        state = _activate_mission(mgr)
        trigger = AdaptationTrigger("wind_change", 15.0, {"new_wind_kmh": 25.0})
        result = adapt_mission(state, trigger, profile, assessment)

        assert result.action in ("continue", "modify")
        assert isinstance(result.explanation, str)


# ===========================================================================
# Determinism Tests
# ===========================================================================

class TestDeterminism:

    def test_same_trigger_produces_identical_result(self):
        results = []
        for _ in range(3):
            profile, assessment, _, _, mgr = _setup_pipeline()
            state = _activate_mission(mgr)
            trigger = AdaptationTrigger("wind_change", 15.0, {"new_wind_kmh": 25.0})
            result = adapt_mission(state, trigger, profile, assessment)
            results.append(result)

        for r in results[1:]:
            assert r.action == results[0].action
            assert r.explanation == results[0].explanation


# ===========================================================================
# v0.1 Backward Compatibility
# ===========================================================================

class TestBackwardCompatibility:

    def test_pipeline_unchanged_without_adaptation(self):
        """Existing pipeline produces identical output when adapter is not invoked."""
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
