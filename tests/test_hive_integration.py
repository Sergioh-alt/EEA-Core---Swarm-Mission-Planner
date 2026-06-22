"""
Tests for Phase 8.5 — Hive Integration Layer.

Tests cover:
- HiveRuntime: initialization, sub-system access, state snapshots
- HiveController: fleet/resource setup, mission submission, execution, state visibility
- HiveSystemSnapshot: consolidated state aggregation
- Integration simulation: multi-mission lifecycle, component coordination
- Decision boundary compliance: no decision-making in integration layer
- Backward compatibility: existing pipeline unchanged
"""

import pytest

from core.hive import MissionPriority, MissionStatus
from core.mission_orchestrator import ExecutionPhase
from core.hive_integration import (
    HiveRuntime,
    HiveController,
    HiveSystemSnapshot,
)


# =========================================================================
# HiveRuntime Tests
# =========================================================================

class TestHiveRuntime:
    """Tests for HiveRuntime initialization and sub-system access."""

    def test_runtime_initializes_all_subsystems(self):
        rt = HiveRuntime()
        assert rt.fleet is not None
        assert rt.queue is not None
        assert rt.lifecycle is not None
        assert rt.status_tracker is not None
        assert rt.allocator is not None
        assert rt.fleet_updater is not None
        assert rt.batteries is not None
        assert rt.liquids is not None
        assert rt.resources is not None

    def test_runtime_starts_empty(self):
        rt = HiveRuntime()
        assert rt.fleet.fleet_size == 0
        assert rt.queue.pending_count == 0
        assert rt.lifecycle.total_count == 0

    def test_hive_state_snapshot(self):
        rt = HiveRuntime()
        rt.fleet.register_drone(1)
        state = rt.hive_state()
        assert state.fleet_size == 1
        assert state.system_status == "idle"

    def test_resource_snapshot(self):
        rt = HiveRuntime()
        rt.fleet.register_drone(1)
        rt.batteries.register_battery(101)
        rt.liquids.register_reservoir(201, capacity_l=10.0)
        snap = rt.resource_snapshot()
        assert snap.total_available_batteries == 1
        assert snap.total_available_reservoirs == 1

    def test_subsystems_share_fleet_registry(self):
        """All sub-systems reference the same FleetRegistry instance."""
        rt = HiveRuntime()
        rt.fleet.register_drone(1)
        assert rt.status_tracker._fleet is rt.fleet
        assert rt.allocator._fleet is rt.fleet
        assert rt.resources._fleet is rt.fleet


# =========================================================================
# HiveController Tests — Fleet & Resource Setup
# =========================================================================

class TestHiveControllerSetup:
    """Tests for fleet and resource registration via HiveController."""

    def test_register_drone(self):
        ctrl = HiveController()
        ctrl.register_drone(1)
        assert ctrl.runtime.fleet.fleet_size == 1

    def test_register_drones(self):
        ctrl = HiveController()
        ctrl.register_drones([1, 2, 3, 4])
        assert ctrl.runtime.fleet.fleet_size == 4

    def test_register_battery(self):
        ctrl = HiveController()
        ctrl.register_battery(101, charge_pct=90.0)
        b = ctrl.runtime.batteries.get_battery(101)
        assert b.charge_pct == 90.0

    def test_register_reservoir(self):
        ctrl = HiveController()
        ctrl.register_reservoir(201, capacity_l=15.0)
        r = ctrl.runtime.liquids.get_reservoir(201)
        assert r.capacity_l == 15.0

    def test_custom_runtime(self):
        rt = HiveRuntime()
        rt.fleet.register_drone(99)
        ctrl = HiveController(runtime=rt)
        assert ctrl.runtime.fleet.fleet_size == 1


# =========================================================================
# HiveController Tests — Mission Submission
# =========================================================================

class TestHiveControllerMissions:
    """Tests for mission submission and queue management."""

    def test_submit_mission(self):
        ctrl = HiveController()
        m = ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        assert m.mission_id == "m1"
        assert m.priority == MissionPriority.NORMAL
        assert ctrl.runtime.queue.pending_count == 1

    def test_submit_multiple_missions(self):
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        ctrl.submit_mission("m2", field_size_ha=30.0, crop_type="corn", num_drones=2,
                           priority=MissionPriority.HIGH)
        assert ctrl.runtime.queue.pending_count == 2

    def test_submit_mission_with_custom_params(self):
        ctrl = HiveController()
        m = ctrl.submit_mission(
            "m1", field_size_ha=100.0, crop_type="rice", num_drones=6,
            priority=MissionPriority.CRITICAL,
            wind_speed_kmh=15.0, temperature_c=30.0,
        )
        assert m.priority == MissionPriority.CRITICAL
        assert m.wind_speed_kmh == 15.0
        assert m.temperature_c == 30.0

    def test_submit_duplicate_mission_raises(self):
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        with pytest.raises(ValueError, match="already in queue"):
            ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)


# =========================================================================
# HiveController Tests — Mission Execution
# =========================================================================

class TestHiveControllerExecution:
    """Tests for mission execution through the unified controller."""

    def test_execute_next_single_mission(self):
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        result = ctrl.execute_next()
        assert result is not None
        assert result.success is True
        assert result.mission_id == "m1"

    def test_execute_next_empty_queue(self):
        ctrl = HiveController()
        result = ctrl.execute_next()
        assert result is None

    def test_execute_next_priority_ordering(self):
        ctrl = HiveController()
        ctrl.submit_mission("low", field_size_ha=50.0, crop_type="wheat", num_drones=4,
                           priority=MissionPriority.LOW)
        ctrl.submit_mission("high", field_size_ha=50.0, crop_type="wheat", num_drones=4,
                           priority=MissionPriority.HIGH)
        result = ctrl.execute_next()
        assert result.mission_id == "high"

    def test_execute_all(self):
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        ctrl.submit_mission("m2", field_size_ha=30.0, crop_type="corn", num_drones=2)
        results = ctrl.execute_all()
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_execute_updates_queue_status(self):
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        ctrl.execute_next()
        m = ctrl.runtime.queue.get_mission("m1")
        assert m.status == MissionStatus.COMPLETED

    def test_execute_creates_lifecycle_context(self):
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        ctrl.execute_next()
        ctx = ctrl.get_mission_context("m1")
        assert ctx.phase == ExecutionPhase.COMPLETED
        assert ctx.profile is not None
        assert ctx.recommendation is not None

    def test_failed_mission_does_not_block_queue(self):
        ctrl = HiveController()
        ctrl.submit_mission("bad", field_size_ha=50.0, crop_type="wheat", num_drones=4,
                           wind_speed_kmh=100.0)
        ctrl.submit_mission("good", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        results = ctrl.execute_all()
        assert len(results) == 2
        good_result = [r for r in results if r.mission_id == "good"][0]
        assert good_result.success is True


# =========================================================================
# HiveSystemSnapshot Tests
# =========================================================================

class TestHiveSystemSnapshot:
    """Tests for consolidated system-wide state visibility."""

    def test_system_snapshot_empty(self):
        ctrl = HiveController()
        snap = ctrl.system_snapshot()
        assert isinstance(snap, HiveSystemSnapshot)
        assert snap.hive_state.fleet_size == 0
        assert snap.hive_state.system_status == "no_fleet"
        assert snap.lifecycle_summary["total_contexts"] == 0

    def test_system_snapshot_with_fleet(self):
        ctrl = HiveController()
        ctrl.register_drones([1, 2, 3])
        ctrl.register_battery(101)
        ctrl.register_reservoir(201, capacity_l=10.0)
        snap = ctrl.system_snapshot()
        assert snap.hive_state.fleet_size == 3
        assert snap.hive_state.system_status == "idle"
        assert snap.resource_snapshot.total_available_batteries == 1
        assert snap.resource_snapshot.total_available_reservoirs == 1

    def test_system_snapshot_after_execution(self):
        ctrl = HiveController()
        ctrl.register_drones([1, 2])
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        ctrl.execute_next()
        snap = ctrl.system_snapshot()
        assert snap.lifecycle_summary["total_contexts"] == 1
        assert snap.lifecycle_summary["completed"] == 1
        assert snap.hive_state.missions_completed == 1

    def test_system_snapshot_deterministic(self):
        """Same operations produce identical snapshots."""
        def run_scenario():
            ctrl = HiveController()
            ctrl.register_drones([1, 2])
            ctrl.register_battery(101)
            ctrl.register_reservoir(201, capacity_l=10.0)
            ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
            ctrl.execute_next()
            return ctrl.system_snapshot()

        s1 = run_scenario()
        s2 = run_scenario()
        assert s1.hive_state.fleet_size == s2.hive_state.fleet_size
        assert s1.hive_state.missions_completed == s2.hive_state.missions_completed
        assert s1.lifecycle_summary == s2.lifecycle_summary


# =========================================================================
# Integration Simulation Tests
# =========================================================================

class TestIntegrationSimulation:
    """End-to-end integration tests across all Phase 8 sub-systems."""

    def test_full_multi_mission_lifecycle(self):
        """Complete lifecycle: setup -> submit -> execute -> inspect."""
        ctrl = HiveController()

        ctrl.register_drones([1, 2, 3, 4])
        ctrl.register_battery(101)
        ctrl.register_battery(102)
        ctrl.register_reservoir(201, capacity_l=10.0)
        ctrl.register_reservoir(202, capacity_l=10.0)

        ctrl.submit_mission("spray_north", field_size_ha=50.0, crop_type="wheat",
                           num_drones=4, priority=MissionPriority.HIGH)
        ctrl.submit_mission("spray_south", field_size_ha=30.0, crop_type="corn",
                           num_drones=2, priority=MissionPriority.NORMAL)

        results = ctrl.execute_all()
        assert len(results) == 2
        assert results[0].mission_id == "spray_north"
        assert results[1].mission_id == "spray_south"
        assert all(r.success for r in results)

        snap = ctrl.system_snapshot()
        assert snap.hive_state.missions_completed == 2
        assert snap.hive_state.missions_queued == 0
        assert snap.lifecycle_summary["completed"] == 2

    def test_resource_tracking_through_controller(self):
        """Verify resource sub-system is accessible through the controller."""
        ctrl = HiveController()
        ctrl.register_drones([1])
        ctrl.register_battery(101)
        ctrl.register_reservoir(201, capacity_l=10.0)

        ctrl.runtime.batteries.assign_to_drone(101, drone_id=1)
        ctrl.runtime.liquids.assign_to_drone(201, drone_id=1)
        ctrl.runtime.batteries.record_consumption(
            101, drone_id=1, mission_id="m1", consumed_pct=25.0,
        )
        ctrl.runtime.liquids.record_consumption(
            201, drone_id=1, mission_id="m1", consumed_l=4.0,
        )

        consumption = ctrl.get_mission_resources("m1")
        assert consumption["total_battery_consumed_pct"] == 25.0
        assert consumption["total_liquid_consumed_l"] == 4.0

    def test_fleet_manager_through_controller(self):
        """Verify fleet manager sub-system is accessible through the controller."""
        ctrl = HiveController()
        ctrl.register_drones([1, 2, 3])

        ctrl.runtime.allocator.assign_drone(1, "m1")
        ctrl.runtime.allocator.assign_drone(2, "m1")

        summary = ctrl.runtime.fleet_updater.fleet_assignment_summary()
        assert summary["active_assignments"] == 2
        assert summary["idle"] == 1

    def test_mission_isolation_through_integration(self):
        """Missions executed through controller remain isolated."""
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        ctrl.submit_mission("m2", field_size_ha=30.0, crop_type="corn", num_drones=2)

        ctrl.execute_all()
        ctx1 = ctrl.get_mission_context("m1")
        ctx2 = ctrl.get_mission_context("m2")

        assert ctx1.profile.field_size_ha == 50.0
        assert ctx2.profile.field_size_ha == 30.0
        assert ctx1.profile is not ctx2.profile
        assert ctx1.routes is not ctx2.routes

    def test_sequential_execution_maintains_state(self):
        """State is correctly maintained across sequential executions."""
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        r1 = ctrl.execute_next()
        assert r1.success

        ctrl.submit_mission("m2", field_size_ha=30.0, crop_type="corn", num_drones=2)
        r2 = ctrl.execute_next()
        assert r2.success

        snap = ctrl.system_snapshot()
        assert snap.lifecycle_summary["completed"] == 2
        assert snap.hive_state.missions_completed == 2


# =========================================================================
# Decision Boundary Compliance Tests
# =========================================================================

class TestDecisionBoundaryCompliance:
    """Verify integration layer contains NO decision-making logic."""

    def test_no_drone_selection(self):
        """HiveController does not select drones -- caller must assign explicitly."""
        ctrl = HiveController()
        ctrl.register_drones([1, 2, 3])
        # Controller provides no method to auto-select drones
        assert not hasattr(ctrl, "select_drone")
        assert not hasattr(ctrl, "best_drone")
        assert not hasattr(ctrl, "optimize_assignment")

    def test_no_resource_allocation(self):
        """HiveController does not allocate resources -- caller must assign explicitly."""
        ctrl = HiveController()
        assert not hasattr(ctrl, "allocate_battery")
        assert not hasattr(ctrl, "allocate_resources")
        assert not hasattr(ctrl, "balance_resources")

    def test_no_scheduling_logic(self):
        """HiveController does not schedule -- uses queue priority ordering only."""
        ctrl = HiveController()
        assert not hasattr(ctrl, "schedule")
        assert not hasattr(ctrl, "optimize_schedule")
        assert not hasattr(ctrl, "reorder_queue")

    def test_no_optimization(self):
        """HiveController does not optimize anything."""
        ctrl = HiveController()
        assert not hasattr(ctrl, "optimize")
        assert not hasattr(ctrl, "balance")
        assert not hasattr(ctrl, "rank")


# =========================================================================
# Backward Compatibility Tests
# =========================================================================

class TestBackwardCompatibility:
    """Verify Phase 0-8.4 behavior is unchanged."""

    def test_pipeline_unchanged_without_integration(self):
        """Existing v0.1 pipeline produces identical output."""
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
            temperature_c=25.0, wind_speed_kmh=10.0,
        )
        env = analyze_environment(profile)
        swarm = plan_swarm(profile, env)
        routes = plan_routes(swarm, env)
        resources = plan_resources(profile, routes)
        risks = evaluate_risks(profile, env, resources, routes)
        rec = generate_recommendation(profile, env, swarm, routes, resources, risks)

        assert rec.go_no_go == "GO WITH CAUTION"
        assert 60 <= rec.confidence_pct <= 80
        assert resources.mission_duration_formatted == "2h 03m"

    def test_integration_produces_same_pipeline_output(self):
        """Mission executed via HiveController produces same result as direct pipeline."""
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
            temperature_c=25.0, wind_speed_kmh=10.0,
        )
        env = analyze_environment(profile)
        swarm = plan_swarm(profile, env)
        routes = plan_routes(swarm, env)
        resources = plan_resources(profile, routes)
        risks = evaluate_risks(profile, env, resources, routes)
        direct_rec = generate_recommendation(profile, env, swarm, routes, resources, risks)

        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4,
                           wind_speed_kmh=10.0, temperature_c=25.0)
        result = ctrl.execute_next()
        hive_rec = result.context.recommendation

        assert hive_rec.go_no_go == direct_rec.go_no_go
        assert hive_rec.confidence_pct == direct_rec.confidence_pct
        assert result.context.resources.mission_duration_formatted == resources.mission_duration_formatted
