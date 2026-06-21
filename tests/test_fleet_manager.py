"""
Phase 8.3 — Fleet Manager Tests

Tests for DroneStatusTracker, DroneAllocationManager, and FleetStateUpdater.
Validates assignment tracking, state transitions, and fleet-wide operations.
No scheduling, optimization, or decision-making logic.
"""

import pytest

from core.hive import FleetRegistry, DroneAvailability
from core.fleet_manager import (
    StateTransition,
    DroneStatusTracker,
    DroneAssignment,
    DroneAllocationManager,
    FleetStateUpdater,
)


def _make_fleet(*drone_ids):
    """Create a FleetRegistry with the given drone IDs."""
    fleet = FleetRegistry()
    for did in drone_ids:
        fleet.register_drone(did)
    return fleet


# ===========================================================================
# DroneStatusTracker Tests
# ===========================================================================

class TestDroneStatusTracker:

    def test_transition_state(self):
        fleet = _make_fleet(1)
        tracker = DroneStatusTracker(fleet)
        drone = tracker.transition(1, DroneAvailability.ACTIVE, "mission start")

        assert drone.availability == DroneAvailability.ACTIVE
        assert tracker.transition_count == 1

    def test_transition_records_history(self):
        fleet = _make_fleet(1)
        tracker = DroneStatusTracker(fleet)
        tracker.transition(1, DroneAvailability.ACTIVE, "start")
        tracker.transition(1, DroneAvailability.IDLE, "end")

        history = tracker.get_history(drone_id=1)
        assert len(history) == 2
        assert history[0].from_state == DroneAvailability.IDLE
        assert history[0].to_state == DroneAvailability.ACTIVE
        assert history[1].from_state == DroneAvailability.ACTIVE
        assert history[1].to_state == DroneAvailability.IDLE

    def test_transition_same_state_noop(self):
        fleet = _make_fleet(1)
        tracker = DroneStatusTracker(fleet)
        tracker.transition(1, DroneAvailability.IDLE, "no change")

        assert tracker.transition_count == 0

    def test_get_history_all(self):
        fleet = _make_fleet(1, 2)
        tracker = DroneStatusTracker(fleet)
        tracker.transition(1, DroneAvailability.ACTIVE, "a")
        tracker.transition(2, DroneAvailability.CHARGING, "b")

        all_history = tracker.get_history()
        assert len(all_history) == 2

    def test_get_history_filtered(self):
        fleet = _make_fleet(1, 2)
        tracker = DroneStatusTracker(fleet)
        tracker.transition(1, DroneAvailability.ACTIVE, "a")
        tracker.transition(2, DroneAvailability.CHARGING, "b")
        tracker.transition(1, DroneAvailability.IDLE, "c")

        history_1 = tracker.get_history(drone_id=1)
        history_2 = tracker.get_history(drone_id=2)
        assert len(history_1) == 2
        assert len(history_2) == 1

    def test_get_current_state(self):
        fleet = _make_fleet(1)
        tracker = DroneStatusTracker(fleet)
        assert tracker.get_current_state(1) == DroneAvailability.IDLE

        tracker.transition(1, DroneAvailability.MAINTENANCE, "check")
        assert tracker.get_current_state(1) == DroneAvailability.MAINTENANCE

    def test_transition_nonexistent_raises(self):
        fleet = _make_fleet(1)
        tracker = DroneStatusTracker(fleet)
        with pytest.raises(ValueError, match="not in fleet"):
            tracker.transition(99, DroneAvailability.ACTIVE, "fail")

    def test_state_transition_dataclass(self):
        t = StateTransition(
            drone_id=1,
            from_state=DroneAvailability.IDLE,
            to_state=DroneAvailability.ACTIVE,
            reason="test",
        )
        assert t.drone_id == 1
        assert t.reason == "test"


# ===========================================================================
# DroneAllocationManager Tests
# ===========================================================================

class TestDroneAllocationManager:

    def test_assign_drone(self):
        fleet = _make_fleet(1)
        allocator = DroneAllocationManager(fleet)
        assignment = allocator.assign_drone(1, "mission-A")

        assert assignment.drone_id == 1
        assert assignment.mission_id == "mission-A"
        assert fleet.get_drone(1).availability == DroneAvailability.ACTIVE
        assert fleet.get_drone(1).assigned_mission_id == "mission-A"

    def test_assign_non_idle_raises(self):
        fleet = _make_fleet(1)
        fleet.update_drone(1, availability=DroneAvailability.CHARGING)
        allocator = DroneAllocationManager(fleet)

        with pytest.raises(ValueError, match="not available"):
            allocator.assign_drone(1, "mission-A")

    def test_assign_duplicate_raises(self):
        fleet = _make_fleet(1)
        allocator = DroneAllocationManager(fleet)
        allocator.assign_drone(1, "mission-A")

        with pytest.raises(ValueError, match="not available"):
            allocator.assign_drone(1, "mission-A")

    def test_release_drone(self):
        fleet = _make_fleet(1)
        allocator = DroneAllocationManager(fleet)
        allocator.assign_drone(1, "mission-A")
        allocator.release_drone(1, "mission-A")

        assert fleet.get_drone(1).availability == DroneAvailability.IDLE
        assert fleet.get_drone(1).assigned_mission_id is None
        assert allocator.active_assignment_count == 0

    def test_release_nonassigned_raises(self):
        fleet = _make_fleet(1)
        allocator = DroneAllocationManager(fleet)

        with pytest.raises(ValueError, match="not assigned"):
            allocator.release_drone(1, "mission-A")

    def test_get_mission_drones(self):
        fleet = _make_fleet(1, 2, 3)
        allocator = DroneAllocationManager(fleet)
        allocator.assign_drone(1, "mission-A")
        allocator.assign_drone(3, "mission-A")

        drones = allocator.get_mission_drones("mission-A")
        assert set(drones) == {1, 3}

    def test_get_mission_drones_empty(self):
        fleet = _make_fleet(1)
        allocator = DroneAllocationManager(fleet)
        assert allocator.get_mission_drones("nonexistent") == []

    def test_get_drone_mission(self):
        fleet = _make_fleet(1)
        allocator = DroneAllocationManager(fleet)
        allocator.assign_drone(1, "mission-A")

        assert allocator.get_drone_mission(1) == "mission-A"

    def test_get_drone_mission_unassigned(self):
        fleet = _make_fleet(1)
        allocator = DroneAllocationManager(fleet)
        assert allocator.get_drone_mission(1) is None

    def test_get_all_assignments(self):
        fleet = _make_fleet(1, 2)
        allocator = DroneAllocationManager(fleet)
        allocator.assign_drone(1, "mission-A")
        allocator.assign_drone(2, "mission-B")

        assignments = allocator.get_all_assignments()
        assert len(assignments) == 2

    def test_multiple_missions(self):
        fleet = _make_fleet(1, 2, 3, 4)
        allocator = DroneAllocationManager(fleet)
        allocator.assign_drone(1, "mission-A")
        allocator.assign_drone(2, "mission-A")
        allocator.assign_drone(3, "mission-B")
        allocator.assign_drone(4, "mission-B")

        assert set(allocator.get_mission_drones("mission-A")) == {1, 2}
        assert set(allocator.get_mission_drones("mission-B")) == {3, 4}
        assert allocator.active_assignment_count == 4

    def test_drone_assignment_dataclass(self):
        a = DroneAssignment(drone_id=1, mission_id="m1")
        assert a.drone_id == 1
        assert a.mission_id == "m1"


# ===========================================================================
# FleetStateUpdater Tests
# ===========================================================================

class TestFleetStateUpdater:

    def _make_updater(self, *drone_ids):
        fleet = _make_fleet(*drone_ids)
        tracker = DroneStatusTracker(fleet)
        allocator = DroneAllocationManager(fleet)
        updater = FleetStateUpdater(fleet, tracker, allocator)
        return fleet, tracker, allocator, updater

    def test_release_mission_drones(self):
        fleet, tracker, allocator, updater = self._make_updater(1, 2, 3)
        allocator.assign_drone(1, "m1")
        allocator.assign_drone(2, "m1")

        released = updater.release_mission_drones("m1")
        assert set(released) == {1, 2}
        assert fleet.get_drone(1).availability == DroneAvailability.IDLE
        assert fleet.get_drone(2).availability == DroneAvailability.IDLE
        assert allocator.active_assignment_count == 0

    def test_release_empty_mission(self):
        _, _, _, updater = self._make_updater(1)
        released = updater.release_mission_drones("nonexistent")
        assert released == []

    def test_set_drones_maintenance(self):
        fleet, _, _, updater = self._make_updater(1, 2, 3)
        transitioned = updater.set_drones_maintenance([1, 2])

        assert set(transitioned) == {1, 2}
        assert fleet.get_drone(1).availability == DroneAvailability.MAINTENANCE
        assert fleet.get_drone(2).availability == DroneAvailability.MAINTENANCE
        assert fleet.get_drone(3).availability == DroneAvailability.IDLE

    def test_set_maintenance_skips_non_idle(self):
        fleet, _, allocator, updater = self._make_updater(1, 2)
        allocator.assign_drone(1, "m1")  # now ACTIVE

        transitioned = updater.set_drones_maintenance([1, 2])
        assert transitioned == [2]
        assert fleet.get_drone(1).availability == DroneAvailability.ACTIVE

    def test_set_drones_charging(self):
        fleet, _, _, updater = self._make_updater(1, 2)
        transitioned = updater.set_drones_charging([1, 2])

        assert set(transitioned) == {1, 2}
        assert fleet.get_drone(1).availability == DroneAvailability.CHARGING

    def test_set_charging_skips_non_idle(self):
        fleet, _, allocator, updater = self._make_updater(1, 2)
        allocator.assign_drone(1, "m1")

        transitioned = updater.set_drones_charging([1, 2])
        assert transitioned == [2]

    def test_return_drones_idle_from_charging(self):
        fleet, _, _, updater = self._make_updater(1, 2)
        updater.set_drones_charging([1, 2])
        returned = updater.return_drones_idle([1, 2])

        assert set(returned) == {1, 2}
        assert fleet.get_drone(1).availability == DroneAvailability.IDLE

    def test_return_drones_idle_from_maintenance(self):
        fleet, _, _, updater = self._make_updater(1)
        updater.set_drones_maintenance([1])
        returned = updater.return_drones_idle([1])

        assert returned == [1]
        assert fleet.get_drone(1).availability == DroneAvailability.IDLE

    def test_return_idle_skips_active(self):
        fleet, _, allocator, updater = self._make_updater(1, 2)
        allocator.assign_drone(1, "m1")
        updater.set_drones_charging([2])
        returned = updater.return_drones_idle([1, 2])

        assert returned == [2]

    def test_fleet_assignment_summary(self):
        fleet, _, allocator, updater = self._make_updater(1, 2, 3, 4)
        allocator.assign_drone(1, "m1")
        allocator.assign_drone(2, "m1")
        allocator.assign_drone(3, "m2")

        summary = updater.fleet_assignment_summary()
        assert summary["total_drones"] == 4
        assert summary["idle"] == 1
        assert summary["active_assignments"] == 3
        assert summary["missions"]["m1"]["count"] == 2
        assert summary["missions"]["m2"]["count"] == 1
        assert summary["by_status"]["active"] == 3
        assert summary["by_status"]["idle"] == 1

    def test_full_lifecycle(self):
        """Test a complete mission lifecycle: assign → execute → release."""
        fleet, tracker, allocator, updater = self._make_updater(1, 2, 3, 4)

        # Assign drones to mission
        allocator.assign_drone(1, "mission-X")
        allocator.assign_drone(2, "mission-X")
        assert len(allocator.get_mission_drones("mission-X")) == 2
        assert fleet.get_drone(1).availability == DroneAvailability.ACTIVE

        # Mission completes → release drones
        released = updater.release_mission_drones("mission-X")
        assert set(released) == {1, 2}
        assert fleet.get_drone(1).availability == DroneAvailability.IDLE
        assert fleet.get_drone(2).availability == DroneAvailability.IDLE

        # Send drone 1 to charging
        updater.set_drones_charging([1], reason="post-mission charge")
        assert fleet.get_drone(1).availability == DroneAvailability.CHARGING

        # Return from charging
        updater.return_drones_idle([1], reason="fully charged")
        assert fleet.get_drone(1).availability == DroneAvailability.IDLE

        # Verify transition history (IDLE→CHARGING, CHARGING→IDLE = 2 transitions)
        history = tracker.get_history(drone_id=1)
        assert len(history) >= 2


# ===========================================================================
# Fleet Assignment Simulation Tests
# ===========================================================================

class TestFleetAssignmentSimulation:

    def test_multi_mission_assignment(self):
        """Multiple missions with separate drone pools."""
        fleet = _make_fleet(1, 2, 3, 4, 5, 6)
        allocator = DroneAllocationManager(fleet)

        allocator.assign_drone(1, "alpha")
        allocator.assign_drone(2, "alpha")
        allocator.assign_drone(3, "alpha")

        allocator.assign_drone(4, "beta")
        allocator.assign_drone(5, "beta")

        assert len(allocator.get_mission_drones("alpha")) == 3
        assert len(allocator.get_mission_drones("beta")) == 2
        assert len(fleet.get_available()) == 1
        assert fleet.get_available()[0].drone_id == 6

    def test_sequential_mission_reuse(self):
        """Drones can be reused across sequential missions."""
        fleet = _make_fleet(1, 2)
        tracker = DroneStatusTracker(fleet)
        allocator = DroneAllocationManager(fleet)
        updater = FleetStateUpdater(fleet, tracker, allocator)

        # Mission A
        allocator.assign_drone(1, "A")
        allocator.assign_drone(2, "A")
        updater.release_mission_drones("A")

        # Mission B — same drones reused
        allocator.assign_drone(1, "B")
        allocator.assign_drone(2, "B")

        assert set(allocator.get_mission_drones("B")) == {1, 2}
        assert allocator.get_drone_mission(1) == "B"

    def test_no_cross_mission_interference(self):
        """Assignment operations on one mission don't affect another."""
        fleet = _make_fleet(1, 2, 3, 4)
        tracker = DroneStatusTracker(fleet)
        allocator = DroneAllocationManager(fleet)
        updater = FleetStateUpdater(fleet, tracker, allocator)

        allocator.assign_drone(1, "X")
        allocator.assign_drone(2, "X")
        allocator.assign_drone(3, "Y")
        allocator.assign_drone(4, "Y")

        # Release mission X
        updater.release_mission_drones("X")

        # Mission Y unaffected
        assert set(allocator.get_mission_drones("Y")) == {3, 4}
        assert fleet.get_drone(3).availability == DroneAvailability.ACTIVE
        assert fleet.get_drone(4).availability == DroneAvailability.ACTIVE

    def test_deterministic_assignment_state(self):
        """Same operations produce identical fleet state."""
        states = []
        for _ in range(3):
            fleet = _make_fleet(1, 2, 3)
            tracker = DroneStatusTracker(fleet)
            allocator = DroneAllocationManager(fleet)
            updater = FleetStateUpdater(fleet, tracker, allocator)

            allocator.assign_drone(1, "m1")
            allocator.assign_drone(2, "m1")
            summary = updater.fleet_assignment_summary()
            states.append(summary)

        for s in states[1:]:
            assert s["total_drones"] == states[0]["total_drones"]
            assert s["idle"] == states[0]["idle"]
            assert s["active_assignments"] == states[0]["active_assignments"]


# ===========================================================================
# Backward Compatibility
# ===========================================================================

class TestBackwardCompatibility:

    def test_pipeline_unchanged_without_fleet_manager(self):
        """Existing pipeline produces identical output when Fleet Manager is not invoked."""
        from core.mission_intake import create_mission_profile
        from core.environment_analyzer import analyze_environment
        from core.swarm_planner import plan_swarm
        from core.route_planner import plan_routes
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

    def test_fleet_registry_unchanged(self):
        """FleetRegistry from Phase 8.1 works identically when Fleet Manager wraps it."""
        fleet = _make_fleet(1, 2, 3)
        DroneStatusTracker(fleet)  # wrapping does not alter FleetRegistry

        # FleetRegistry API unchanged
        assert fleet.fleet_size == 3
        assert len(fleet.get_available()) == 3
        health = fleet.fleet_health_snapshot()
        assert health["total_drones"] == 3
        assert health["by_status"]["idle"] == 3
