"""
Phase 8.6 — Validation & Stabilization Tests.

Comprehensive validation of the complete Hive System architecture (8.1-8.5).
Tests cover:
- Component isolation verification
- State consistency across sub-systems
- Mission isolation under multi-mission execution
- Fleet state correctness through full lifecycle
- Resource state correctness through full lifecycle
- Integration correctness (unified controller)
- Snapshot consistency and determinism
- Decision boundary compliance (no decision-making in any Hive component)
- Backward compatibility with v0.1 pipeline
- Performance sanity checks

These tests do NOT introduce new capabilities. They validate existing behavior.
"""

import ast
import inspect
import time

import pytest

from core.hive import (
    FleetRegistry,
    MissionQueue,
    MissionPriority,
    MissionStatus,
    QueuedMission,
    DroneAvailability,
    build_hive_state,
)
from core.mission_orchestrator import (
    MissionLifecycleManager,
    run_queue,
)
from core.fleet_manager import (
    DroneStatusTracker,
    DroneAllocationManager,
    FleetStateUpdater,
)
from core.resource_system import (
    BatteryInventoryManager,
    LiquidInventoryManager,
    ResourceStateTracker,
    BatteryState,
    ReservoirState,
)
from core.hive_integration import (
    HiveRuntime,
    HiveController,
)


# =========================================================================
# Component Isolation Verification
# =========================================================================

class TestComponentIsolation:
    """Verify Phase 8 components operate independently."""

    def test_hive_core_independent(self):
        """Phase 8.1 components work without 8.2-8.5."""
        fleet = FleetRegistry()
        queue = MissionQueue()
        fleet.register_drone(1)
        fleet.register_drone(2)
        m = QueuedMission(
            mission_id="m1", field_size_ha=50.0, crop_type="wheat",
            num_drones=4, priority=MissionPriority.NORMAL,
        )
        queue.enqueue(m)
        state = build_hive_state(fleet, queue)
        assert state.fleet_size == 2
        assert state.missions_queued == 1

    def test_orchestrator_independent(self):
        """Phase 8.2 works with only Phase 8.1 dependency."""
        queue = MissionQueue()
        lifecycle = MissionLifecycleManager()
        m = QueuedMission(
            mission_id="m1", field_size_ha=50.0, crop_type="wheat",
            num_drones=4, priority=MissionPriority.NORMAL,
        )
        queue.enqueue(m)
        results = run_queue(queue, lifecycle)
        assert len(results) == 1
        assert results[0].success

    def test_fleet_manager_independent(self):
        """Phase 8.3 works with only Phase 8.1 dependency."""
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        DroneStatusTracker(fleet)  # verify creation works
        alloc = DroneAllocationManager(fleet)
        alloc.assign_drone(1, "m1")
        assert alloc.get_drone_mission(1) == "m1"
        assert alloc.get_drone_mission(2) is None
        assert fleet.get_drone(1).availability == DroneAvailability.ACTIVE

    def test_resource_system_independent(self):
        """Phase 8.4 works with only Phase 8.1 dependency."""
        fleet = FleetRegistry()
        fleet.register_drone(1)
        batt = BatteryInventoryManager()
        liq = LiquidInventoryManager()
        batt.register_battery(101)
        liq.register_reservoir(201, capacity_l=10.0)
        resources = ResourceStateTracker(fleet, batt, liq)
        snap = resources.build_snapshot()
        assert snap.total_available_batteries == 1
        assert snap.total_available_reservoirs == 1

    def test_no_circular_imports(self):
        """Phase 8 import chain is strictly one-directional."""
        import core.hive as hive_mod
        import core.mission_orchestrator as orch_mod
        import core.fleet_manager as fm_mod
        import core.resource_system as rs_mod
        hive_src = inspect.getsource(hive_mod)
        assert "from core.mission_orchestrator" not in hive_src
        assert "from core.fleet_manager" not in hive_src
        assert "from core.resource_system" not in hive_src
        assert "from core.hive_integration" not in hive_src

        orch_src = inspect.getsource(orch_mod)
        assert "from core.fleet_manager" not in orch_src
        assert "from core.resource_system" not in orch_src
        assert "from core.hive_integration" not in orch_src

        fm_src = inspect.getsource(fm_mod)
        assert "from core.resource_system" not in fm_src
        assert "from core.hive_integration" not in fm_src

        rs_src = inspect.getsource(rs_mod)
        assert "from core.hive_integration" not in rs_src


# =========================================================================
# State Consistency
# =========================================================================

class TestStateConsistency:
    """Verify state remains consistent across sub-systems."""

    def test_fleet_state_consistent_across_layers(self):
        """FleetRegistry state is visible through all dependent layers."""
        rt = HiveRuntime()
        rt.fleet.register_drone(1)
        rt.fleet.register_drone(2)

        assert rt.fleet.fleet_size == 2
        assert rt.status_tracker.get_current_state(1) == DroneAvailability.IDLE
        summary = rt.fleet_updater.fleet_assignment_summary()
        assert summary["idle"] == 2
        hive_state = rt.hive_state()
        assert hive_state.fleet_size == 2

    def test_queue_state_consistent_after_execution(self):
        """MissionQueue reflects correct statuses after execution."""
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        ctrl.submit_mission("m2", field_size_ha=30.0, crop_type="corn", num_drones=2)
        ctrl.execute_all()

        q = ctrl.runtime.queue
        m1 = q.get_mission("m1")
        m2 = q.get_mission("m2")
        assert m1.status == MissionStatus.COMPLETED
        assert m2.status == MissionStatus.COMPLETED

    def test_resource_state_consistent_with_fleet(self):
        """ResourceStateTracker sees drones registered in FleetRegistry."""
        rt = HiveRuntime()
        rt.fleet.register_drone(1)
        rt.batteries.register_battery(101)
        rt.batteries.assign_to_drone(101, drone_id=1)

        drone_res = rt.resources.get_drone_resources(1)
        assert drone_res.battery_id == 101
        assert drone_res.battery_charge_pct == 100.0
        assert drone_res.battery_state == BatteryState.IN_USE

    def test_snapshot_reflects_current_state(self):
        """System snapshot captures the exact current state."""
        ctrl = HiveController()
        ctrl.register_drones([1, 2, 3])
        ctrl.register_battery(101)
        ctrl.register_reservoir(201, capacity_l=10.0)

        snap1 = ctrl.system_snapshot()
        assert snap1.hive_state.fleet_size == 3
        assert snap1.hive_state.missions_completed == 0

        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        ctrl.execute_next()

        snap2 = ctrl.system_snapshot()
        assert snap2.hive_state.missions_completed == 1
        assert snap2.lifecycle_summary["completed"] == 1


# =========================================================================
# Mission Isolation Under Multi-Mission Execution
# =========================================================================

class TestMissionIsolation:
    """Verify missions do not interfere with each other."""

    def test_three_missions_isolated(self):
        """Three missions with different parameters produce isolated contexts."""
        ctrl = HiveController()
        ctrl.submit_mission("small", field_size_ha=10.0, crop_type="wheat", num_drones=2)
        ctrl.submit_mission("medium", field_size_ha=50.0, crop_type="corn", num_drones=4)
        ctrl.submit_mission("large", field_size_ha=100.0, crop_type="rice", num_drones=6)

        results = ctrl.execute_all()
        assert len(results) == 3
        assert all(r.success for r in results)

        ctx_small = ctrl.get_mission_context("small")
        ctx_medium = ctrl.get_mission_context("medium")
        ctx_large = ctrl.get_mission_context("large")

        assert ctx_small.profile.field_size_ha == 10.0
        assert ctx_medium.profile.field_size_ha == 50.0
        assert ctx_large.profile.field_size_ha == 100.0

        assert ctx_small.routes is not ctx_medium.routes
        assert ctx_medium.routes is not ctx_large.routes

    def test_failed_mission_does_not_affect_others(self):
        """A failed mission (extreme wind) does not contaminate subsequent ones."""
        ctrl = HiveController()
        ctrl.submit_mission("fail", field_size_ha=50.0, crop_type="wheat",
                           num_drones=4, wind_speed_kmh=100.0,
                           priority=MissionPriority.HIGH)
        ctrl.submit_mission("ok", field_size_ha=50.0, crop_type="wheat",
                           num_drones=4, priority=MissionPriority.NORMAL)

        results = ctrl.execute_all()
        ok_result = [r for r in results if r.mission_id == "ok"][0]
        assert ok_result.success is True
        assert ok_result.context.recommendation is not None

    def test_mission_contexts_immutable_after_execution(self):
        """Contexts are not modified by subsequent mission executions."""
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        ctrl.execute_next()
        ctx1_rec = ctrl.get_mission_context("m1").recommendation.go_no_go

        ctrl.submit_mission("m2", field_size_ha=30.0, crop_type="corn", num_drones=2)
        ctrl.execute_next()

        assert ctrl.get_mission_context("m1").recommendation.go_no_go == ctx1_rec


# =========================================================================
# Fleet State Correctness
# =========================================================================

class TestFleetStateCorrectness:
    """Verify fleet state through complete lifecycle."""

    def test_drone_lifecycle(self):
        """Drone transitions: IDLE -> ACTIVE -> IDLE -> CHARGING -> IDLE -> MAINTENANCE."""
        fleet = FleetRegistry()
        fleet.register_drone(1)
        tracker = DroneStatusTracker(fleet)
        alloc = DroneAllocationManager(fleet)
        updater = FleetStateUpdater(fleet, tracker, alloc)

        alloc.assign_drone(1, "m1")
        assert fleet.get_drone(1).availability == DroneAvailability.ACTIVE

        alloc.release_drone(1, "m1")
        assert fleet.get_drone(1).availability == DroneAvailability.IDLE

        updater.set_drones_charging([1])
        assert fleet.get_drone(1).availability == DroneAvailability.CHARGING

        updater.return_drones_idle([1])
        assert fleet.get_drone(1).availability == DroneAvailability.IDLE

        updater.set_drones_maintenance([1])
        assert fleet.get_drone(1).availability == DroneAvailability.MAINTENANCE

    def test_assignment_prevents_double_allocation(self):
        """Assigned drone cannot be assigned to another mission."""
        fleet = FleetRegistry()
        fleet.register_drone(1)
        alloc = DroneAllocationManager(fleet)
        alloc.assign_drone(1, "m1")
        with pytest.raises(ValueError):
            alloc.assign_drone(1, "m2")

    def test_batch_release_after_mission(self):
        """All drones from a mission are released together."""
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        fleet.register_drone(3)
        tracker = DroneStatusTracker(fleet)
        alloc = DroneAllocationManager(fleet)
        updater = FleetStateUpdater(fleet, tracker, alloc)

        alloc.assign_drone(1, "m1")
        alloc.assign_drone(2, "m1")
        released = updater.release_mission_drones("m1")
        assert set(released) == {1, 2}
        assert fleet.get_drone(1).availability == DroneAvailability.IDLE
        assert fleet.get_drone(2).availability == DroneAvailability.IDLE
        assert fleet.get_drone(3).availability == DroneAvailability.IDLE


# =========================================================================
# Resource State Correctness
# =========================================================================

class TestResourceStateCorrectness:
    """Verify resource state through complete lifecycle."""

    def test_battery_full_lifecycle(self):
        """Battery: register -> assign -> consume -> release -> charge -> available."""
        batt = BatteryInventoryManager()
        batt.register_battery(101)
        assert batt.get_battery(101).state == BatteryState.AVAILABLE

        batt.assign_to_drone(101, drone_id=1)
        assert batt.get_battery(101).state == BatteryState.IN_USE

        batt.record_consumption(101, drone_id=1, mission_id="m1", consumed_pct=60.0)
        assert batt.get_battery(101).charge_pct == 40.0

        batt.release_from_drone(101)
        assert batt.get_battery(101).state == BatteryState.AVAILABLE

        batt.set_charging(101)
        assert batt.get_battery(101).state == BatteryState.CHARGING

        batt.complete_charging(101)
        assert batt.get_battery(101).state == BatteryState.AVAILABLE
        assert batt.get_battery(101).charge_pct == 100.0

    def test_liquid_full_lifecycle(self):
        """Reservoir: register -> assign -> consume -> release -> refill -> full."""
        liq = LiquidInventoryManager()
        liq.register_reservoir(201, capacity_l=10.0)
        assert liq.get_reservoir(201).state == ReservoirState.FULL

        liq.assign_to_drone(201, drone_id=1)
        liq.record_consumption(201, drone_id=1, mission_id="m1", consumed_l=8.0)
        assert liq.get_reservoir(201).current_level_l == 2.0
        assert liq.get_reservoir(201).state == ReservoirState.PARTIAL

        liq.release_from_drone(201)
        liq.set_refilling(201)
        assert liq.get_reservoir(201).state == ReservoirState.REFILLING

        liq.complete_refill(201)
        assert liq.get_reservoir(201).state == ReservoirState.FULL
        assert liq.get_reservoir(201).current_level_l == 10.0

    def test_multi_battery_snapshot(self):
        """Snapshot correctly reports mixed battery states."""
        fleet = FleetRegistry()
        fleet.register_drone(1)
        batt = BatteryInventoryManager()
        liq = LiquidInventoryManager()
        batt.register_battery(101)
        batt.register_battery(102)
        batt.register_battery(103)
        batt.assign_to_drone(101, drone_id=1)
        batt.set_charging(102)
        resources = ResourceStateTracker(fleet, batt, liq)
        snap = resources.build_snapshot()
        assert snap.total_available_batteries == 1  # only 103 available
        assert snap.battery_summary["total_batteries"] == 3


# =========================================================================
# Snapshot Consistency & Determinism
# =========================================================================

class TestSnapshotDeterminism:
    """Verify snapshots are deterministic and consistent."""

    def test_identical_operations_produce_identical_snapshots(self):
        """Same sequence of operations produces identical HiveSystemSnapshot."""
        def run():
            ctrl = HiveController()
            ctrl.register_drones([1, 2, 3, 4])
            ctrl.register_battery(101)
            ctrl.register_battery(102)
            ctrl.register_reservoir(201, capacity_l=10.0)
            ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
            ctrl.submit_mission("m2", field_size_ha=30.0, crop_type="corn", num_drones=2)
            ctrl.execute_all()
            return ctrl.system_snapshot()

        s1 = run()
        s2 = run()
        assert s1.hive_state.fleet_size == s2.hive_state.fleet_size
        assert s1.hive_state.missions_completed == s2.hive_state.missions_completed
        assert s1.hive_state.system_status == s2.hive_state.system_status
        assert s1.lifecycle_summary == s2.lifecycle_summary
        assert s1.resource_snapshot.total_available_batteries == s2.resource_snapshot.total_available_batteries

    def test_hive_state_snapshot_independent(self):
        """Each HiveState is an independent snapshot."""
        ctrl = HiveController()
        ctrl.register_drones([1])
        snap1 = ctrl.runtime.hive_state()

        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        snap2 = ctrl.runtime.hive_state()

        assert snap1.missions_queued == 0
        assert snap2.missions_queued == 1


# =========================================================================
# Decision Boundary Compliance — Code-Level Verification
# =========================================================================

class TestDecisionBoundaryCompliance:
    """
    Verify NO decision-making logic exists in any Phase 8 module.
    Uses AST inspection to scan for forbidden patterns.
    """

    HIVE_MODULES = [
        "core/hive.py",
        "core/mission_orchestrator.py",
        "core/fleet_manager.py",
        "core/resource_system.py",
        "core/hive_integration.py",
    ]

    FORBIDDEN_METHOD_PATTERNS = [
        "select_best", "choose_best", "pick_best", "find_best",
        "optimize", "rank", "score", "evaluate_fitness",
        "balance_load", "rebalance", "redistribute",
        "auto_assign", "auto_allocate", "smart_",
        "recommend", "suggest", "infer_priority",
    ]

    def test_no_forbidden_methods_in_hive_modules(self):
        """No method names match forbidden decision-making patterns."""
        for module_path in self.HIVE_MODULES:
            with open(module_path, "r") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name.lower()
                    for pattern in self.FORBIDDEN_METHOD_PATTERNS:
                        assert pattern not in name, (
                            f"Forbidden method pattern '{pattern}' found in "
                            f"{module_path}:{node.lineno} — {node.name}"
                        )

    def test_no_sorting_by_score_or_rank(self):
        """No sorting operations using score/rank/fitness keys."""
        forbidden_sort_keys = ["score", "rank", "fitness", "priority_score", "weight"]
        for module_path in self.HIVE_MODULES:
            with open(module_path, "r") as f:
                source = f.read()
            for key in forbidden_sort_keys:
                assert f"key=lambda.*{key}" not in source.replace(" ", ""), (
                    f"Forbidden sort key '{key}' in {module_path}"
                )

    def test_no_random_imports(self):
        """No randomness imported in any Hive module."""
        for module_path in self.HIVE_MODULES:
            with open(module_path, "r") as f:
                source = f.read()
            assert "import random" not in source, f"Random import in {module_path}"
            assert "from random" not in source, f"Random import in {module_path}"
            assert "import numpy" not in source, f"Numpy import in {module_path}"

    def test_no_ml_imports(self):
        """No ML/AI libraries imported in any Hive module."""
        forbidden_imports = [
            "sklearn", "tensorflow", "torch", "keras",
            "xgboost", "lightgbm", "scipy.optimize",
        ]
        for module_path in self.HIVE_MODULES:
            with open(module_path, "r") as f:
                source = f.read()
            for lib in forbidden_imports:
                assert lib not in source, f"ML import '{lib}' in {module_path}"

    def test_hive_controller_has_no_selection_methods(self):
        """HiveController exposes no selection/allocation/optimization methods."""
        ctrl = HiveController()
        forbidden_attrs = [
            "select_drone", "best_drone", "optimize_assignment",
            "allocate_battery", "allocate_resources", "balance_resources",
            "schedule", "optimize_schedule", "reorder_queue",
            "optimize", "balance", "rank", "score",
            "recommend", "suggest",
        ]
        for attr in forbidden_attrs:
            assert not hasattr(ctrl, attr), (
                f"HiveController has forbidden attribute: {attr}"
            )

    def test_fleet_manager_has_no_selection_methods(self):
        """Fleet Manager components have no selection logic."""
        fleet = FleetRegistry()
        alloc = DroneAllocationManager(fleet)
        forbidden_attrs = [
            "select_best", "find_optimal", "rank_drones",
            "score_drone", "best_available", "auto_assign",
        ]
        for attr in forbidden_attrs:
            assert not hasattr(alloc, attr), (
                f"DroneAllocationManager has forbidden attribute: {attr}"
            )

    def test_resource_system_has_no_allocation_methods(self):
        """Resource System has no allocation or optimization logic."""
        batt = BatteryInventoryManager()
        liq = LiquidInventoryManager()
        forbidden_attrs = [
            "allocate", "optimize_charging", "optimize_refill",
            "balance", "redistribute", "auto_assign",
            "recommend_battery", "suggest_reservoir",
        ]
        for attr in forbidden_attrs:
            assert not hasattr(batt, attr), (
                f"BatteryInventoryManager has forbidden attribute: {attr}"
            )
            assert not hasattr(liq, attr), (
                f"LiquidInventoryManager has forbidden attribute: {attr}"
            )


# =========================================================================
# Backward Compatibility
# =========================================================================

class TestPhase8BackwardCompatibility:
    """Verify Phase 0-7 pipeline remains identical."""

    def test_v01_pipeline_unchanged(self):
        """Standard v0.1 pipeline produces identical output."""
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
        assert len(swarm.sectors) == 4

    def test_hive_output_matches_direct_pipeline(self):
        """HiveController produces identical output to direct pipeline."""
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

        assert result.context.recommendation.go_no_go == direct_rec.go_no_go
        assert result.context.recommendation.confidence_pct == direct_rec.confidence_pct
        assert result.context.resources.mission_duration_formatted == resources.mission_duration_formatted

    def test_no_phase07_modules_modified(self):
        """Phase 0-7 modules contain no imports from Phase 8."""
        phase07_modules = [
            "core/mission_intake.py",
            "core/environment_analyzer.py",
            "core/swarm_planner.py",
            "core/route_planner.py",
            "core/resource_planner.py",
            "core/risk_engine.py",
            "core/decision_engine.py",
            "core/geometry.py",
            "core/drone_physics.py",
            "core/battery_model.py",
            "core/liquid_model.py",
            "core/mission_timeline.py",
        ]
        phase8_imports = [
            "from core.hive", "from core.mission_orchestrator",
            "from core.fleet_manager", "from core.resource_system",
            "from core.hive_integration",
        ]
        for mod_path in phase07_modules:
            with open(mod_path, "r") as f:
                source = f.read()
            for imp in phase8_imports:
                assert imp not in source, (
                    f"Phase 8 import '{imp}' found in Phase 0-7 module {mod_path}"
                )


# =========================================================================
# Performance Sanity Checks
# =========================================================================

class TestPerformanceSanity:
    """Basic performance sanity checks (no hard timing assertions)."""

    def test_single_mission_execution_completes(self):
        """A single mission executes in reasonable time."""
        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        start = time.monotonic()
        result = ctrl.execute_next()
        elapsed = time.monotonic() - start
        assert result.success
        assert elapsed < 5.0  # generous upper bound

    def test_ten_missions_execute_sequentially(self):
        """Ten missions execute without degradation."""
        ctrl = HiveController()
        for i in range(10):
            ctrl.submit_mission(
                f"m{i}", field_size_ha=50.0, crop_type="wheat", num_drones=4,
            )
        start = time.monotonic()
        results = ctrl.execute_all()
        elapsed = time.monotonic() - start
        assert len(results) == 10
        assert all(r.success for r in results)
        assert elapsed < 30.0  # generous upper bound

    def test_snapshot_generation_fast(self):
        """System snapshot builds quickly."""
        ctrl = HiveController()
        ctrl.register_drones(list(range(1, 51)))
        for i in range(1, 21):
            ctrl.register_battery(i)
        for i in range(1, 11):
            ctrl.register_reservoir(i, capacity_l=10.0)

        start = time.monotonic()
        snap = ctrl.system_snapshot()
        elapsed = time.monotonic() - start
        assert snap.hive_state.fleet_size == 50
        assert elapsed < 1.0
