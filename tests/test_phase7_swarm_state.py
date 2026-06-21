"""
Phase 7.1 — Swarm State Manager Tests

Tests for DroneStatus, DroneState, MissionStatus, MissionState,
FailureEvent, and SwarmStateManager lifecycle operations.
"""

import pytest

from core.swarm_state import (
    DroneStatus,
    MissionStatus,
    FailureEvent,
    SwarmStateManager,
)
from core.mission_intake import create_mission_profile
from core.environment_analyzer import analyze_environment
from core.swarm_planner import plan_swarm
from core.route_planner import plan_routes
from core.geometry import FieldGeometry


def _make_state_manager(**kwargs):
    """Create a SwarmStateManager from default pipeline."""
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
    return SwarmStateManager(profile, swarm, routes), profile, swarm, routes


# ===========================================================================
# Enum Tests
# ===========================================================================

class TestDroneStatus:

    def test_all_statuses_exist(self):
        expected = {"idle", "launching", "active", "refilling",
                    "swapping_battery", "returning", "completed", "failed"}
        actual = {s.value for s in DroneStatus}
        assert actual == expected

    def test_status_values_are_strings(self):
        for status in DroneStatus:
            assert isinstance(status.value, str)


class TestMissionStatus:

    def test_all_statuses_exist(self):
        expected = {"planning", "active", "paused", "completing", "done", "aborted"}
        actual = {s.value for s in MissionStatus}
        assert actual == expected


# ===========================================================================
# Initialization Tests
# ===========================================================================

class TestSwarmStateManagerInit:

    def test_initializes_with_correct_drone_count(self):
        mgr, _, _, _ = _make_state_manager(num_drones=4)
        assert mgr.drone_count == 4

    def test_all_drones_start_idle(self):
        mgr, _, _, _ = _make_state_manager(num_drones=4)
        state = mgr.get_state()
        for drone in state.drones:
            assert drone.status == DroneStatus.IDLE

    def test_initial_mission_status_is_planning(self):
        mgr, _, _, _ = _make_state_manager()
        state = mgr.get_state()
        assert state.status == MissionStatus.PLANNING

    def test_initial_battery_is_full(self):
        mgr, _, _, _ = _make_state_manager()
        state = mgr.get_state()
        for drone in state.drones:
            assert drone.battery_remaining_pct == 100.0

    def test_initial_liquid_matches_profile(self):
        mgr, profile, _, _ = _make_state_manager(liquid_capacity_l=10.0)
        state = mgr.get_state()
        for drone in state.drones:
            assert drone.liquid_remaining_l == 10.0

    def test_initial_passes_are_zero(self):
        mgr, _, _, _ = _make_state_manager()
        state = mgr.get_state()
        for drone in state.drones:
            assert drone.passes_completed == 0
            assert drone.passes_total > 0

    def test_initial_coverage_is_zero(self):
        mgr, _, _, _ = _make_state_manager()
        state = mgr.get_state()
        assert state.coverage_pct == 0.0

    def test_all_sectors_remaining_initially(self):
        mgr, _, swarm, _ = _make_state_manager()
        state = mgr.get_state()
        assert len(state.sectors_remaining) == len(swarm.sectors)
        assert len(state.sectors_completed) == 0

    def test_no_initial_alerts(self):
        mgr, _, _, _ = _make_state_manager()
        state = mgr.get_state()
        assert len(state.active_alerts) == 0

    def test_no_initial_failures(self):
        mgr, _, _, _ = _make_state_manager()
        state = mgr.get_state()
        assert len(state.failure_log) == 0

    def test_single_drone_init(self):
        mgr, _, _, _ = _make_state_manager(num_drones=1)
        assert mgr.drone_count == 1
        state = mgr.get_state()
        assert len(state.drones) == 1

    def test_many_drones_init(self):
        mgr, _, _, _ = _make_state_manager(num_drones=10, field_size_ha=500.0)
        assert mgr.drone_count == 10


# ===========================================================================
# Drone State Query Tests
# ===========================================================================

class TestDroneStateQuery:

    def test_get_drone_by_id(self):
        mgr, _, _, _ = _make_state_manager()
        drone = mgr.get_drone(1)
        assert drone.drone_id == 1

    def test_get_drone_invalid_id_raises(self):
        mgr, _, _, _ = _make_state_manager()
        with pytest.raises(ValueError, match="not found"):
            mgr.get_drone(999)

    def test_get_available_drones_initially_all(self):
        mgr, _, _, _ = _make_state_manager(num_drones=4)
        available = mgr.get_available_drones()
        assert len(available) == 4

    def test_get_failed_drones_initially_empty(self):
        mgr, _, _, _ = _make_state_manager()
        failed = mgr.get_failed_drones()
        assert len(failed) == 0


# ===========================================================================
# Drone State Update Tests
# ===========================================================================

class TestDroneStateUpdate:

    def test_update_status(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.update_drone(1, status=DroneStatus.ACTIVE)
        drone = mgr.get_drone(1)
        assert drone.status == DroneStatus.ACTIVE

    def test_update_battery(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.update_drone(1, battery_remaining_pct=75.5)
        drone = mgr.get_drone(1)
        assert drone.battery_remaining_pct == 75.5

    def test_update_liquid(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.update_drone(1, liquid_remaining_l=5.0)
        drone = mgr.get_drone(1)
        assert drone.liquid_remaining_l == 5.0

    def test_update_position(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.update_drone(1, position=(100.0, 200.0))
        drone = mgr.get_drone(1)
        assert drone.position == (100.0, 200.0)

    def test_update_passes(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.update_drone(1, passes_completed=42)
        drone = mgr.get_drone(1)
        assert drone.passes_completed == 42

    def test_update_flight_time(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.update_drone(1, flight_time_elapsed_min=15.5)
        drone = mgr.get_drone(1)
        assert drone.flight_time_elapsed_min == 15.5

    def test_update_multiple_fields(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.update_drone(1,
            status=DroneStatus.ACTIVE,
            battery_remaining_pct=80.0,
            passes_completed=10,
        )
        drone = mgr.get_drone(1)
        assert drone.status == DroneStatus.ACTIVE
        assert drone.battery_remaining_pct == 80.0
        assert drone.passes_completed == 10

    def test_update_invalid_field_raises(self):
        mgr, _, _, _ = _make_state_manager()
        with pytest.raises(ValueError, match="Invalid DroneState field"):
            mgr.update_drone(1, nonexistent_field=42)

    def test_update_invalid_drone_raises(self):
        mgr, _, _, _ = _make_state_manager()
        with pytest.raises(ValueError, match="not found"):
            mgr.update_drone(999, status=DroneStatus.ACTIVE)


# ===========================================================================
# Failure Handling Tests
# ===========================================================================

class TestFailureHandling:

    def test_mark_drone_failed(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.update_drone(1, status=DroneStatus.ACTIVE, passes_completed=20)
        event = mgr.mark_drone_failed(1, "motor failure")

        assert isinstance(event, FailureEvent)
        assert event.drone_id == 1
        assert event.reason == "motor failure"
        assert event.passes_completed == 20
        assert event.passes_remaining > 0

    def test_failed_drone_status_is_failed(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.mark_drone_failed(1, "battery critical")
        drone = mgr.get_drone(1)
        assert drone.status == DroneStatus.FAILED

    def test_failed_drone_not_available(self):
        mgr, _, _, _ = _make_state_manager(num_drones=4)
        mgr.mark_drone_failed(1, "signal lost")
        available = mgr.get_available_drones()
        assert len(available) == 3
        assert all(d.drone_id != 1 for d in available)

    def test_failed_drone_in_failed_list(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.mark_drone_failed(1, "collision")
        failed = mgr.get_failed_drones()
        assert len(failed) == 1
        assert failed[0].drone_id == 1

    def test_failure_logged_in_state(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.mark_drone_failed(1, "GPS failure")
        state = mgr.get_state()
        assert len(state.failure_log) == 1
        assert state.failure_log[0].reason == "GPS failure"

    def test_failure_generates_alert(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.mark_drone_failed(1, "overheating")
        state = mgr.get_state()
        assert len(state.active_alerts) == 1
        assert "Drone 1 FAILED" in state.active_alerts[0]

    def test_multiple_failures(self):
        mgr, _, _, _ = _make_state_manager(num_drones=4)
        mgr.mark_drone_failed(1, "motor")
        mgr.mark_drone_failed(3, "battery")

        assert mgr.failed_drone_count == 2
        available = mgr.get_available_drones()
        assert len(available) == 2

        state = mgr.get_state()
        assert len(state.failure_log) == 2
        assert len(state.active_alerts) == 2


# ===========================================================================
# Mission State Transition Tests
# ===========================================================================

class TestMissionStateTransitions:

    def test_planning_to_active(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.set_mission_status(MissionStatus.ACTIVE)
        state = mgr.get_state()
        assert state.status == MissionStatus.ACTIVE

    def test_active_to_paused(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.set_mission_status(MissionStatus.ACTIVE)
        mgr.set_mission_status(MissionStatus.PAUSED)
        state = mgr.get_state()
        assert state.status == MissionStatus.PAUSED

    def test_active_to_done(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.set_mission_status(MissionStatus.ACTIVE)
        mgr.set_mission_status(MissionStatus.DONE)
        state = mgr.get_state()
        assert state.status == MissionStatus.DONE

    def test_active_to_aborted(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.set_mission_status(MissionStatus.ACTIVE)
        mgr.set_mission_status(MissionStatus.ABORTED)
        state = mgr.get_state()
        assert state.status == MissionStatus.ABORTED

    def test_elapsed_time_update(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.update_elapsed_time(30.5)
        state = mgr.get_state()
        assert state.elapsed_min == 30.5


# ===========================================================================
# Coverage Tracking Tests
# ===========================================================================

class TestCoverageTracking:

    def test_coverage_increases_with_passes(self):
        mgr, _, _, _ = _make_state_manager(num_drones=4)
        drone = mgr.get_drone(1)
        total = drone.passes_total
        mgr.update_drone(1, passes_completed=total)
        state = mgr.get_state()
        assert state.coverage_pct > 0

    def test_full_coverage(self):
        mgr, _, _, _ = _make_state_manager(num_drones=4)
        for drone_id in range(1, 5):
            drone = mgr.get_drone(drone_id)
            mgr.update_drone(drone_id,
                status=DroneStatus.COMPLETED,
                passes_completed=drone.passes_total,
            )
        state = mgr.get_state()
        assert state.coverage_pct == 100.0

    def test_sectors_completed_tracking(self):
        mgr, _, _, _ = _make_state_manager(num_drones=4)
        mgr.update_drone(1, status=DroneStatus.COMPLETED)
        state = mgr.get_state()
        assert 1 in state.sectors_completed
        assert len(state.sectors_remaining) == 3


# ===========================================================================
# Alert Management Tests
# ===========================================================================

class TestAlertManagement:

    def test_add_alert(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.add_alert("Wind speed increasing")
        state = mgr.get_state()
        assert "Wind speed increasing" in state.active_alerts

    def test_clear_alerts(self):
        mgr, _, _, _ = _make_state_manager()
        mgr.add_alert("Test alert 1")
        mgr.add_alert("Test alert 2")
        mgr.clear_alerts()
        state = mgr.get_state()
        assert len(state.active_alerts) == 0


# ===========================================================================
# Property Tests
# ===========================================================================

class TestProperties:

    def test_active_drone_count(self):
        mgr, _, _, _ = _make_state_manager(num_drones=4)
        assert mgr.active_drone_count == 0
        mgr.update_drone(1, status=DroneStatus.ACTIVE)
        mgr.update_drone(2, status=DroneStatus.ACTIVE)
        assert mgr.active_drone_count == 2

    def test_failed_drone_count(self):
        mgr, _, _, _ = _make_state_manager(num_drones=4)
        assert mgr.failed_drone_count == 0
        mgr.mark_drone_failed(1, "test")
        assert mgr.failed_drone_count == 1


# ===========================================================================
# Polygon Pipeline Integration
# ===========================================================================

class TestPolygonPipelineIntegration:

    def test_polygon_field_state_manager(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        mgr, _, swarm, _ = _make_state_manager(
            field_size_ha=fg.area_ha, field_geometry=fg, num_drones=4,
        )
        assert mgr.drone_count == 4
        state = mgr.get_state()
        assert len(state.sectors_remaining) == len(swarm.sectors)
        assert state.status == MissionStatus.PLANNING


# ===========================================================================
# Full Lifecycle Simulation
# ===========================================================================

class TestFullLifecycle:

    def test_mission_lifecycle(self):
        """Simulate a complete mission lifecycle."""
        mgr, _, _, _ = _make_state_manager(num_drones=4)

        # 1. Start mission
        mgr.set_mission_status(MissionStatus.ACTIVE)
        for i in range(1, 5):
            mgr.update_drone(i, status=DroneStatus.LAUNCHING)
        for i in range(1, 5):
            mgr.update_drone(i, status=DroneStatus.ACTIVE)

        assert mgr.active_drone_count == 4

        # 2. Simulate progress
        mgr.update_elapsed_time(15.0)
        for i in range(1, 5):
            drone = mgr.get_drone(i)
            half = drone.passes_total // 2
            mgr.update_drone(i, passes_completed=half, battery_remaining_pct=60.0)

        state = mgr.get_state()
        assert state.coverage_pct > 0
        assert state.elapsed_min == 15.0

        # 3. Drone 2 fails
        event = mgr.mark_drone_failed(2, "motor malfunction")
        assert event.passes_remaining > 0
        assert mgr.failed_drone_count == 1
        assert mgr.active_drone_count == 3

        # 4. Remaining drones complete
        for i in [1, 3, 4]:
            drone = mgr.get_drone(i)
            mgr.update_drone(i,
                status=DroneStatus.COMPLETED,
                passes_completed=drone.passes_total,
            )

        mgr.update_elapsed_time(65.0)
        mgr.set_mission_status(MissionStatus.COMPLETING)

        state = mgr.get_state()
        assert state.status == MissionStatus.COMPLETING
        assert len(state.sectors_completed) == 3
        assert len(state.failure_log) == 1

        # 5. Mission done
        mgr.set_mission_status(MissionStatus.DONE)
        state = mgr.get_state()
        assert state.status == MissionStatus.DONE
