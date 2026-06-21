"""
Phase 8.1 — Hive Core Foundation Tests

Tests for FleetRegistry, MissionQueue, and HiveState.
Validates structural primitives only — no scheduling, optimization,
or planning logic.
"""

import pytest

from core.hive import (
    DroneAvailability,
    FleetDrone,
    FleetRegistry,
    MissionPriority,
    MissionStatus,
    QueuedMission,
    MissionQueue,
    build_hive_state,
)


# ===========================================================================
# FleetRegistry Tests
# ===========================================================================

class TestFleetRegistry:

    def test_register_drone(self):
        fleet = FleetRegistry()
        drone = fleet.register_drone(1)
        assert drone.drone_id == 1
        assert drone.availability == DroneAvailability.IDLE
        assert fleet.fleet_size == 1

    def test_register_multiple_drones(self):
        fleet = FleetRegistry()
        for i in range(1, 5):
            fleet.register_drone(i)
        assert fleet.fleet_size == 4

    def test_register_duplicate_raises(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        with pytest.raises(ValueError, match="already registered"):
            fleet.register_drone(1)

    def test_remove_drone(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.remove_drone(1)
        assert fleet.fleet_size == 0

    def test_remove_nonexistent_raises(self):
        fleet = FleetRegistry()
        with pytest.raises(ValueError, match="not in fleet"):
            fleet.remove_drone(99)

    def test_get_drone(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        drone = fleet.get_drone(1)
        assert drone.drone_id == 1

    def test_get_nonexistent_raises(self):
        fleet = FleetRegistry()
        with pytest.raises(ValueError, match="not in fleet"):
            fleet.get_drone(99)

    def test_update_drone_availability(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.update_drone(1, availability=DroneAvailability.ACTIVE)
        assert fleet.get_drone(1).availability == DroneAvailability.ACTIVE

    def test_update_drone_mission(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.update_drone(1, assigned_mission_id="mission-A")
        assert fleet.get_drone(1).assigned_mission_id == "mission-A"

    def test_update_drone_battery(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.update_drone(1, battery_pct=75.0)
        assert fleet.get_drone(1).battery_pct == 75.0

    def test_get_available_drones(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        fleet.register_drone(3)
        fleet.update_drone(2, availability=DroneAvailability.ACTIVE)
        available = fleet.get_available()
        assert len(available) == 2
        ids = {d.drone_id for d in available}
        assert ids == {1, 3}

    def test_get_by_availability(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        fleet.update_drone(1, availability=DroneAvailability.CHARGING)
        fleet.update_drone(2, availability=DroneAvailability.CHARGING)
        charging = fleet.get_by_availability(DroneAvailability.CHARGING)
        assert len(charging) == 2

    def test_get_all(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        all_drones = fleet.get_all()
        assert len(all_drones) == 2

    def test_fleet_health_snapshot(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        fleet.update_drone(1, availability=DroneAvailability.ACTIVE, battery_pct=80.0)
        fleet.update_drone(2, battery_pct=60.0)
        health = fleet.fleet_health_snapshot()
        assert health["total_drones"] == 2
        assert health["by_status"]["active"] == 1
        assert health["by_status"]["idle"] == 1
        assert health["avg_battery_pct"] == 70.0

    def test_empty_fleet_health(self):
        fleet = FleetRegistry()
        health = fleet.fleet_health_snapshot()
        assert health["total_drones"] == 0
        assert health["avg_battery_pct"] == 0.0


# ===========================================================================
# MissionQueue Tests
# ===========================================================================

class TestMissionQueue:

    def _make_mission(self, mission_id, priority=MissionPriority.NORMAL):
        return QueuedMission(
            mission_id=mission_id,
            field_size_ha=50.0,
            crop_type="wheat",
            num_drones=4,
            priority=priority,
        )

    def test_enqueue_mission(self):
        queue = MissionQueue()
        m = self._make_mission("m1")
        queue.enqueue(m)
        assert queue.total_count == 1
        assert queue.pending_count == 1

    def test_enqueue_duplicate_raises(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("m1"))
        with pytest.raises(ValueError, match="already in queue"):
            queue.enqueue(self._make_mission("m1"))

    def test_dequeue_returns_highest_priority(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("low", MissionPriority.LOW))
        queue.enqueue(self._make_mission("high", MissionPriority.HIGH))
        queue.enqueue(self._make_mission("normal", MissionPriority.NORMAL))
        result = queue.dequeue()
        assert result.mission_id == "high"
        assert result.status == MissionStatus.EXECUTING

    def test_dequeue_fifo_same_priority(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("first"))
        queue.enqueue(self._make_mission("second"))
        result = queue.dequeue()
        assert result.mission_id == "first"

    def test_dequeue_empty_returns_none(self):
        queue = MissionQueue()
        assert queue.dequeue() is None

    def test_peek_does_not_remove(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("m1"))
        peeked = queue.peek()
        assert peeked.mission_id == "m1"
        assert peeked.status == MissionStatus.QUEUED
        assert queue.pending_count == 1

    def test_peek_empty_returns_none(self):
        queue = MissionQueue()
        assert queue.peek() is None

    def test_cancel_queued_mission(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("m1"))
        cancelled = queue.cancel("m1")
        assert cancelled.status == MissionStatus.CANCELLED
        assert queue.pending_count == 0

    def test_cancel_nonqueued_raises(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("m1"))
        queue.dequeue()  # now EXECUTING
        with pytest.raises(ValueError, match="Cannot cancel"):
            queue.cancel("m1")

    def test_cancel_nonexistent_raises(self):
        queue = MissionQueue()
        with pytest.raises(ValueError, match="not found"):
            queue.cancel("nope")

    def test_complete_executing_mission(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("m1"))
        queue.dequeue()
        completed = queue.complete("m1")
        assert completed.status == MissionStatus.COMPLETED

    def test_complete_non_executing_raises(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("m1"))
        with pytest.raises(ValueError, match="Cannot complete"):
            queue.complete("m1")

    def test_fail_executing_mission(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("m1"))
        queue.dequeue()
        failed = queue.fail("m1")
        assert failed.status == MissionStatus.FAILED

    def test_fail_non_executing_raises(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("m1"))
        with pytest.raises(ValueError, match="Cannot fail"):
            queue.fail("m1")

    def test_get_mission(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("m1"))
        m = queue.get_mission("m1")
        assert m.mission_id == "m1"

    def test_get_nonexistent_raises(self):
        queue = MissionQueue()
        with pytest.raises(ValueError, match="not found"):
            queue.get_mission("nope")

    def test_get_by_status(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("m1"))
        queue.enqueue(self._make_mission("m2"))
        queue.dequeue()  # m1 → EXECUTING
        queued = queue.get_by_status(MissionStatus.QUEUED)
        executing = queue.get_by_status(MissionStatus.EXECUTING)
        assert len(queued) == 1
        assert len(executing) == 1

    def test_priority_ordering_critical(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("normal", MissionPriority.NORMAL))
        queue.enqueue(self._make_mission("critical", MissionPriority.CRITICAL))
        result = queue.dequeue()
        assert result.mission_id == "critical"

    def test_multiple_dequeue_sequence(self):
        queue = MissionQueue()
        queue.enqueue(self._make_mission("a", MissionPriority.LOW))
        queue.enqueue(self._make_mission("b", MissionPriority.HIGH))
        queue.enqueue(self._make_mission("c", MissionPriority.NORMAL))

        first = queue.dequeue()
        assert first.mission_id == "b"
        second = queue.dequeue()
        assert second.mission_id == "c"
        third = queue.dequeue()
        assert third.mission_id == "a"
        assert queue.dequeue() is None


# ===========================================================================
# HiveState Tests
# ===========================================================================

class TestHiveState:

    def test_build_empty_state(self):
        fleet = FleetRegistry()
        queue = MissionQueue()
        state = build_hive_state(fleet, queue)

        assert state.fleet_size == 0
        assert state.total_missions == 0
        assert state.system_status == "no_fleet"

    def test_build_idle_state(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        queue = MissionQueue()
        state = build_hive_state(fleet, queue)

        assert state.fleet_size == 2
        assert state.system_status == "idle"

    def test_build_ready_state(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        queue = MissionQueue()
        queue.enqueue(QueuedMission(
            mission_id="m1", field_size_ha=50, crop_type="wheat", num_drones=1,
        ))
        state = build_hive_state(fleet, queue)

        assert state.missions_queued == 1
        assert state.system_status == "ready"

    def test_build_active_state(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        queue = MissionQueue()
        queue.enqueue(QueuedMission(
            mission_id="m1", field_size_ha=50, crop_type="wheat", num_drones=1,
        ))
        queue.dequeue()
        state = build_hive_state(fleet, queue)

        assert state.missions_executing == 1
        assert state.system_status == "active"

    def test_state_counts_all_statuses(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        queue = MissionQueue()

        queue.enqueue(QueuedMission(
            mission_id="m1", field_size_ha=50, crop_type="wheat", num_drones=1,
        ))
        queue.enqueue(QueuedMission(
            mission_id="m2", field_size_ha=30, crop_type="corn", num_drones=2,
        ))
        queue.enqueue(QueuedMission(
            mission_id="m3", field_size_ha=20, crop_type="wheat", num_drones=1,
        ))
        queue.dequeue()  # m1 → EXECUTING
        queue.complete("m1")
        queue.dequeue()  # m2 → EXECUTING
        queue.fail("m2")
        queue.cancel("m3")

        state = build_hive_state(fleet, queue)
        assert state.missions_completed == 1
        assert state.missions_failed == 1
        assert state.missions_cancelled == 1
        assert state.missions_queued == 0
        assert state.missions_executing == 0
        assert state.total_missions == 3

    def test_fleet_health_in_state(self):
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        fleet.update_drone(1, battery_pct=80.0)
        fleet.update_drone(2, battery_pct=60.0)
        queue = MissionQueue()
        state = build_hive_state(fleet, queue)

        assert state.fleet_health["total_drones"] == 2
        assert state.fleet_health["avg_battery_pct"] == 70.0

    def test_state_is_deterministic(self):
        """Same inputs produce identical state."""
        states = []
        for _ in range(3):
            fleet = FleetRegistry()
            fleet.register_drone(1)
            fleet.register_drone(2)
            queue = MissionQueue()
            queue.enqueue(QueuedMission(
                mission_id="m1", field_size_ha=50, crop_type="wheat", num_drones=2,
            ))
            state = build_hive_state(fleet, queue)
            states.append(state)

        for s in states[1:]:
            assert s.fleet_size == states[0].fleet_size
            assert s.missions_queued == states[0].missions_queued
            assert s.system_status == states[0].system_status


# ===========================================================================
# Dataclass Tests
# ===========================================================================

class TestDataclasses:

    def test_fleet_drone_defaults(self):
        drone = FleetDrone(drone_id=1)
        assert drone.availability == DroneAvailability.IDLE
        assert drone.assigned_mission_id is None
        assert drone.battery_pct == 100.0

    def test_queued_mission_defaults(self):
        m = QueuedMission(
            mission_id="m1", field_size_ha=50, crop_type="wheat", num_drones=4,
        )
        assert m.priority == MissionPriority.NORMAL
        assert m.status == MissionStatus.QUEUED
        assert m.wind_speed_kmh == 10.0
        assert m.temperature_c == 25.0

    def test_drone_availability_values(self):
        assert len(DroneAvailability) == 4
        values = {s.value for s in DroneAvailability}
        assert values == {"idle", "active", "charging", "maintenance"}

    def test_mission_priority_ordering(self):
        assert MissionPriority.CRITICAL.value > MissionPriority.HIGH.value
        assert MissionPriority.HIGH.value > MissionPriority.NORMAL.value
        assert MissionPriority.NORMAL.value > MissionPriority.LOW.value

    def test_mission_status_values(self):
        assert len(MissionStatus) == 5
        values = {s.value for s in MissionStatus}
        assert values == {"queued", "executing", "completed", "failed", "cancelled"}


# ===========================================================================
# v0.1 Backward Compatibility
# ===========================================================================

class TestBackwardCompatibility:

    def test_pipeline_unchanged_without_hive(self):
        """Existing pipeline produces identical output when Hive is not invoked."""
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
