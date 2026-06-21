"""
Phase 6 — Realism Layer Tests

Comprehensive tests for drone physics, battery model, liquid model,
and mission timeline. Supplements the existing test_realism.py with
additional edge cases and integration scenarios.
"""

from core.drone_physics import (
    compute_effective_speed,
    compute_payload_power_factor,
    compute_wind_power_factor,
    compute_climb_time_s,
    compute_descend_time_s,
    analyze_drone_physics,
    physics_config,
)
from core.battery_model import estimate_battery, compute_battery_wh
from core.liquid_model import estimate_liquid
from core.mission_timeline import generate_timeline
from core.mission_intake import create_mission_profile
from core.environment_analyzer import analyze_environment
from core.swarm_planner import plan_swarm
from core.route_planner import plan_routes
from core.resource_planner import plan_resources
from config.settings import REFILL_TIME_MIN, BATTERY_SWAP_TIME_MIN


def _run_full_pipeline(**kwargs):
    profile = create_mission_profile(**kwargs)
    assessment = analyze_environment(profile)
    swarm = plan_swarm(profile, assessment)
    routes = plan_routes(swarm, assessment)
    resources = plan_resources(profile, routes)
    return profile, assessment, swarm, routes, resources


# ===========================================================================
# Drone Physics Edge Cases
# ===========================================================================

class TestDronePhysicsEdgeCases:

    def test_zero_wind_zero_payload(self):
        eff, wr, pr = compute_effective_speed(25.0, 0.0, 0.0)
        assert wr == 0.0
        assert pr == 0.0
        assert eff > 0

    def test_extreme_wind_clamps_to_min(self):
        eff, _, _ = compute_effective_speed(25.0, 200.0, 15.0)
        assert eff >= physics_config.min_speed_ms

    def test_climb_time_proportional_to_altitude(self):
        t1 = compute_climb_time_s(10.0)
        t2 = compute_climb_time_s(20.0)
        assert abs(t2 - 2 * t1) < 0.01

    def test_descend_slower_than_climb(self):
        climb = compute_climb_time_s(50.0)
        descend = compute_descend_time_s(50.0)
        assert descend > climb

    def test_wind_power_factor_monotonic(self):
        f0 = compute_wind_power_factor(0.0)
        f10 = compute_wind_power_factor(10.0)
        f30 = compute_wind_power_factor(30.0)
        assert f0 <= f10 <= f30

    def test_payload_power_factor_monotonic(self):
        f0 = compute_payload_power_factor(0.0)
        f5 = compute_payload_power_factor(5.0)
        f15 = compute_payload_power_factor(15.0)
        assert f0 <= f5 <= f15

    def test_analyze_physics_full_result(self):
        result = analyze_drone_physics(25.0, 15.0, 10.0, 100)
        assert result.effective_speed_kmh > 0
        assert result.effective_speed_ms > 0
        assert result.payload_weight_kg == 10.0
        assert result.total_turn_time_s > 0
        assert result.wind_power_factor >= 1.0
        assert result.payload_power_factor >= 1.0
        assert result.turn_penalty_s > 0


# ===========================================================================
# Battery Model Edge Cases
# ===========================================================================

class TestBatteryModelEdgeCases:

    def test_compute_battery_wh_helper(self):
        total, usable = compute_battery_wh(5000)
        assert total > 0
        assert usable < total
        assert usable > 0

    def test_zero_distance_minimal_consumption(self):
        est = estimate_battery(1, 0.0, 0.0, 0.0, 0.0, 5000)
        assert est.base_consumption_wh == 0.0
        assert est.total_consumption_wh >= 0.0

    def test_short_flight_no_swap(self):
        est = estimate_battery(1, 1000, 5.0, 0.0, 5.0, 5000)
        assert est.battery_swaps_needed == 0
        assert est.swap_time_min == 0.0

    def test_battery_swap_time_uses_config(self):
        est = estimate_battery(1, 200000, 300.0, 20.0, 10.0, 5000)
        if est.battery_swaps_needed > 0:
            expected_swap_time = est.battery_swaps_needed * BATTERY_SWAP_TIME_MIN
            assert est.swap_time_min == expected_swap_time


# ===========================================================================
# Liquid Model Edge Cases
# ===========================================================================

class TestLiquidModelEdgeCases:

    def test_exact_one_load(self):
        est = estimate_liquid(1, 1.25, 8.0, 10.0, "wheat")
        assert est.total_liquid_needed_l == 10.0
        assert est.loads_needed == 1
        assert len(est.refill_events) == 0

    def test_just_over_one_load(self):
        est = estimate_liquid(1, 1.3, 8.0, 10.0, "wheat")
        assert est.loads_needed == 2
        assert len(est.refill_events) == 1

    def test_refill_duration_uses_config(self):
        est = estimate_liquid(1, 10.0, 8.0, 10.0, "wheat")
        for ev in est.refill_events:
            assert ev.refill_duration_min == REFILL_TIME_MIN

    def test_large_area_many_refills(self):
        est = estimate_liquid(1, 100.0, 8.0, 10.0, "wheat")
        assert est.loads_needed > 10
        assert len(est.refill_events) == est.loads_needed - 1

    def test_assumptions_populated(self):
        est = estimate_liquid(1, 10.0, 8.0, 10.0, "wheat")
        assert len(est.assumptions) > 0
        assert any("Spray rate" in a for a in est.assumptions)


# ===========================================================================
# Mission Timeline Integration
# ===========================================================================

class TestTimelineIntegration:

    def test_timeline_matches_drone_count(self):
        profile, _, _, routes, resources = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        timeline = generate_timeline(profile, routes, resources)
        assert len(timeline.drone_timelines) == 4

    def test_timeline_events_have_timestamps(self):
        profile, _, _, routes, resources = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        timeline = generate_timeline(profile, routes, resources)
        for dt in timeline.drone_timelines:
            for event in dt.events:
                assert event.timestamp_formatted != ""
                assert event.timestamp_min >= 0

    def test_timeline_has_summary(self):
        profile, _, _, routes, resources = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        timeline = generate_timeline(profile, routes, resources)
        assert "Mission Duration" in timeline.summary
        assert "Drones" in timeline.summary

    def test_timeline_duration_formatted(self):
        profile, _, _, routes, resources = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        timeline = generate_timeline(profile, routes, resources)
        assert "h" in timeline.mission_duration_formatted or "m" in timeline.mission_duration_formatted

    def test_drone_timeline_has_physics_battery_liquid(self):
        profile, _, _, routes, resources = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        timeline = generate_timeline(profile, routes, resources)
        for dt in timeline.drone_timelines:
            assert dt.physics is not None
            assert dt.battery is not None
            assert dt.liquid is not None
            assert dt.spray_time_min > 0

    def test_wind_affects_timeline_duration(self):
        profile_calm, _, _, routes_calm, res_calm = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=0,
        )
        profile_windy, _, _, routes_windy, res_windy = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=25,
        )
        tl_calm = generate_timeline(profile_calm, routes_calm, res_calm)
        tl_windy = generate_timeline(profile_windy, routes_windy, res_windy)
        # Wind should increase mission duration
        assert tl_windy.mission_duration_min >= tl_calm.mission_duration_min
