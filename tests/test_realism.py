"""
Realism Layer Test Suite — Phase 6

Tests for:
- Drone physics (speed constraints, turn penalties, payload/wind impact)
- Battery model (distance, payload, wind, duration factors)
- Liquid consumption model (area, crop, spray rate, refill events)
- Mission timeline engine (event sequence, ordering, completeness)
- Backward compatibility (v0.1 pipeline unchanged)
"""

from core.drone_physics import (
    compute_effective_speed,
    compute_turn_penalty,
    compute_payload_power_factor,
    compute_wind_power_factor,
    analyze_drone_physics,
)
from core.battery_model import estimate_battery
from core.liquid_model import estimate_liquid
from core.mission_timeline import generate_timeline
from core.mission_intake import create_mission_profile
from core.environment_analyzer import analyze_environment
from core.swarm_planner import plan_swarm
from core.route_planner import plan_routes
from core.resource_planner import plan_resources
from core.risk_engine import evaluate_risks
from core.decision_engine import generate_recommendation


def _run_full_pipeline(**kwargs):
    """Run complete pipeline including realism layer."""
    profile = create_mission_profile(**kwargs)
    assessment = analyze_environment(profile)
    swarm = plan_swarm(profile, assessment)
    routes = plan_routes(swarm, assessment)
    resources = plan_resources(profile, routes)
    risks = evaluate_risks(profile, assessment, resources, routes)
    rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)
    timeline = generate_timeline(profile, routes, resources)
    return profile, assessment, swarm, routes, resources, risks, rec, timeline


# ===========================================================================
# Drone Physics Tests
# ===========================================================================

class TestDronePhysics:
    """Drone physics layer validation."""

    def test_effective_speed_no_wind_no_payload(self):
        eff, wind_red, payload_red = compute_effective_speed(25.0, 0.0, 0.0)
        assert eff > 0
        assert wind_red == 0.0
        assert payload_red == 0.0

    def test_effective_speed_with_wind(self):
        eff_calm, _, _ = compute_effective_speed(25.0, 0.0, 0.0)
        eff_windy, wind_red, _ = compute_effective_speed(25.0, 20.0, 0.0)
        assert eff_windy < eff_calm
        assert wind_red > 0

    def test_effective_speed_with_payload(self):
        eff_empty, _, _ = compute_effective_speed(25.0, 0.0, 0.0)
        eff_loaded, _, payload_red = compute_effective_speed(25.0, 0.0, 10.0)
        assert eff_loaded < eff_empty
        assert payload_red > 0

    def test_effective_speed_bounds(self):
        eff, _, _ = compute_effective_speed(25.0, 100.0, 15.0)
        assert eff >= 3.0  # min speed

    def test_turn_penalty_zero_turns(self):
        per_turn, total = compute_turn_penalty(0, 7.0)
        assert per_turn == 0.0
        assert total == 0.0

    def test_turn_penalty_positive(self):
        per_turn, total = compute_turn_penalty(10, 7.0)
        assert per_turn > 0
        assert total > 0
        assert abs(total - per_turn * 10) < 0.1

    def test_wind_power_factor_increases(self):
        calm = compute_wind_power_factor(0.0)
        windy = compute_wind_power_factor(30.0)
        assert windy > calm
        assert calm == 1.0

    def test_payload_power_factor_increases(self):
        empty = compute_payload_power_factor(0.0)
        loaded = compute_payload_power_factor(10.0)
        assert loaded > empty
        assert empty == 1.0

    def test_analyze_physics_result(self):
        result = analyze_drone_physics(
            recommended_speed_kmh=25.0,
            wind_speed_kmh=10.0,
            liquid_capacity_l=10.0,
            num_passes=50,
        )
        assert result.effective_speed_kmh > 0
        assert result.payload_weight_kg == 10.0
        assert result.total_turn_time_s > 0
        assert result.wind_power_factor >= 1.0
        assert result.payload_power_factor >= 1.0


# ===========================================================================
# Battery Model Tests
# ===========================================================================

class TestBatteryModel:
    """Battery model validation."""

    def test_default_scenario_battery(self):
        est = estimate_battery(
            drone_id=1,
            distance_m=25000,
            flight_time_min=30.0,
            wind_speed_kmh=10.0,
            liquid_capacity_l=10.0,
            battery_capacity_mah=5000,
        )
        assert est.base_consumption_wh > 0
        assert est.total_consumption_wh > est.base_consumption_wh
        assert est.battery_capacity_wh > 0
        assert len(est.assumptions) > 0

    def test_wind_increases_consumption(self):
        calm = estimate_battery(1, 25000, 30, 0.0, 10.0, 5000)
        windy = estimate_battery(1, 25000, 30, 30.0, 10.0, 5000)
        assert windy.wind_penalty_wh > calm.wind_penalty_wh
        assert windy.total_consumption_wh > calm.total_consumption_wh

    def test_payload_increases_consumption(self):
        light = estimate_battery(1, 25000, 30, 10.0, 5.0, 5000)
        heavy = estimate_battery(1, 25000, 30, 10.0, 15.0, 5000)
        assert heavy.payload_penalty_wh > light.payload_penalty_wh
        assert heavy.total_consumption_wh > light.total_consumption_wh

    def test_battery_swap_detection(self):
        est = estimate_battery(
            drone_id=1,
            distance_m=200000,
            flight_time_min=300.0,
            wind_speed_kmh=20.0,
            liquid_capacity_l=10.0,
            battery_capacity_mah=5000,
        )
        assert est.consumption_pct > 100
        assert est.battery_swaps_needed > 0
        assert est.swap_time_min > 0

    def test_complexity_multiplier(self):
        low = estimate_battery(1, 25000, 30, 10.0, 10.0, 5000, complexity_multiplier=1.0)
        high = estimate_battery(1, 25000, 30, 10.0, 10.0, 5000, complexity_multiplier=1.5)
        assert high.total_consumption_wh > low.total_consumption_wh


# ===========================================================================
# Liquid Model Tests
# ===========================================================================

class TestLiquidModel:
    """Liquid consumption model validation."""

    def test_basic_consumption(self):
        est = estimate_liquid(1, 12.5, 8.0, 10.0, "wheat")
        assert est.total_liquid_needed_l == 100.0  # 12.5 * 8.0
        assert est.loads_needed == 10
        assert len(est.refill_events) == 9

    def test_no_refill_needed(self):
        est = estimate_liquid(1, 1.0, 8.0, 10.0, "wheat")
        assert est.total_liquid_needed_l == 8.0
        assert est.loads_needed == 1
        assert len(est.refill_events) == 0
        assert est.total_refill_time_min == 0.0

    def test_refill_events_correct(self):
        est = estimate_liquid(1, 5.0, 8.0, 10.0, "wheat")
        assert est.total_liquid_needed_l == 40.0
        assert est.loads_needed == 4
        assert len(est.refill_events) == 3
        for i, ev in enumerate(est.refill_events):
            assert ev.event_number == i + 1
            assert ev.refill_duration_min == 5.0

    def test_ha_per_load(self):
        est = estimate_liquid(1, 10.0, 8.0, 10.0, "wheat")
        assert est.ha_per_load == 1.25  # 10L / 8 L/ha

    def test_crop_spray_rate_rice(self):
        est = estimate_liquid(1, 10.0, 15.0, 10.0, "rice")
        assert est.total_liquid_needed_l == 150.0
        assert est.loads_needed == 15


# ===========================================================================
# Mission Timeline Tests
# ===========================================================================

class TestMissionTimeline:
    """Mission timeline engine validation."""

    def test_timeline_has_required_events(self):
        _, _, _, _, _, _, _, timeline = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert len(timeline.drone_timelines) == 4

        for dt in timeline.drone_timelines:
            event_types = [e.event_type for e in dt.events]
            assert "launch" in event_types
            assert "transit" in event_types
            assert "spraying" in event_types
            assert "return" in event_types
            assert "complete" in event_types

    def test_timeline_ordering(self):
        _, _, _, _, _, _, _, timeline = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        for dt in timeline.drone_timelines:
            timestamps = [e.timestamp_min for e in dt.events]
            assert timestamps == sorted(timestamps)

    def test_timeline_with_refills(self):
        _, _, _, _, _, _, _, timeline = _run_full_pipeline(
            field_size_ha=50.0, crop_type="rice", num_drones=2,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        for dt in timeline.drone_timelines:
            event_types = [e.event_type for e in dt.events]
            assert "refill" in event_types

    def test_timeline_total_events(self):
        _, _, _, _, _, _, _, timeline = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert timeline.total_events > 0
        assert timeline.total_events == sum(
            len(dt.events) for dt in timeline.drone_timelines
        )

    def test_timeline_duration_positive(self):
        _, _, _, _, _, _, _, timeline = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert timeline.mission_duration_min > 0
        for dt in timeline.drone_timelines:
            assert dt.total_duration_min > 0
            assert dt.spray_time_min > 0

    def test_timeline_first_and_last_events(self):
        _, _, _, _, _, _, _, timeline = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        for dt in timeline.drone_timelines:
            assert dt.events[0].event_type == "launch"
            assert dt.events[-1].event_type == "complete"


# ===========================================================================
# Backward Compatibility
# ===========================================================================

class TestBackwardCompatibility:
    """Ensure v0.1 pipeline outputs are unchanged."""

    def test_v01_pipeline_unchanged(self):
        """The original 7-module pipeline must produce identical outputs."""
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
        assert rec.confidence_pct == 67.7
        assert resources.mission_duration_formatted == "2h 03m"
        assert len(swarm.sectors) == 4
        assert swarm.balance_score == 1.0
        assert swarm.partition_method == "grid"

    def test_high_wind_unchanged(self):
        profile = create_mission_profile(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=40,
        )
        assessment = analyze_environment(profile)
        swarm = plan_swarm(profile, assessment)
        routes = plan_routes(swarm, assessment)
        resources = plan_resources(profile, routes)
        risks = evaluate_risks(profile, assessment, resources, routes)
        rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)

        assert rec.go_no_go == "NO-GO"
        assert not rec.feasible

    def test_realism_layer_does_not_affect_pipeline(self):
        """Timeline generation must not alter pipeline outputs."""
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

        # Generate timeline AFTER pipeline
        timeline = generate_timeline(profile, routes, resources)

        # Pipeline outputs must be unchanged
        assert rec.go_no_go == "GO WITH CAUTION"
        assert rec.confidence_pct == 67.7
        assert resources.mission_duration_formatted == "2h 03m"
        assert len(swarm.sectors) == 4
        assert timeline.mission_duration_min > 0
