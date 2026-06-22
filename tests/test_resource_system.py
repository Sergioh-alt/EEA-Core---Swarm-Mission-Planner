"""
Tests for Phase 8.4 — Resource System.

Tests cover:
- BatteryInventoryManager: registration, assignment, consumption, charging lifecycle
- LiquidInventoryManager: registration, assignment, consumption, refill lifecycle
- ResourceStateTracker: per-drone resource state, fleet snapshot, mission consumption
- Resource simulation: multi-mission tracking, isolation, determinism
- Backward compatibility: existing pipeline unchanged
"""

import pytest

from core.hive import FleetRegistry
from core.resource_system import (
    BatteryState,
    BatteryInventoryManager,
    ReservoirState,
    LiquidInventoryManager,
    ResourceSnapshot,
    ResourceStateTracker,
)


# =========================================================================
# BatteryInventoryManager Tests
# =========================================================================

class TestBatteryInventoryManager:
    """Tests for battery inventory tracking."""

    def test_register_battery(self):
        mgr = BatteryInventoryManager()
        b = mgr.register_battery(1)
        assert b.battery_id == 1
        assert b.charge_pct == 100.0
        assert b.state == BatteryState.AVAILABLE
        assert b.assigned_drone_id is None
        assert b.cycle_count == 0

    def test_register_battery_with_partial_charge(self):
        mgr = BatteryInventoryManager()
        b = mgr.register_battery(1, charge_pct=75.0)
        assert b.charge_pct == 75.0
        assert b.state == BatteryState.AVAILABLE

    def test_register_duplicate_battery_raises(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1)
        with pytest.raises(ValueError, match="already registered"):
            mgr.register_battery(1)

    def test_get_battery(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1)
        b = mgr.get_battery(1)
        assert b.battery_id == 1

    def test_get_nonexistent_battery_raises(self):
        mgr = BatteryInventoryManager()
        with pytest.raises(ValueError, match="not in inventory"):
            mgr.get_battery(999)

    def test_assign_to_drone(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1)
        b = mgr.assign_to_drone(1, drone_id=10)
        assert b.state == BatteryState.IN_USE
        assert b.assigned_drone_id == 10

    def test_assign_unavailable_battery_raises(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1)
        mgr.assign_to_drone(1, drone_id=10)
        with pytest.raises(ValueError, match="not available"):
            mgr.assign_to_drone(1, drone_id=20)

    def test_record_consumption(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1, charge_pct=100.0)
        mgr.assign_to_drone(1, drone_id=10)
        rec = mgr.record_consumption(1, drone_id=10, mission_id="m1", consumed_pct=30.0)
        assert rec.start_pct == 100.0
        assert rec.end_pct == 70.0
        assert rec.consumed_pct == 30.0
        b = mgr.get_battery(1)
        assert b.charge_pct == 70.0

    def test_consumption_depletes_battery(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1, charge_pct=20.0)
        mgr.assign_to_drone(1, drone_id=10)
        mgr.record_consumption(1, drone_id=10, mission_id="m1", consumed_pct=25.0)
        b = mgr.get_battery(1)
        assert b.charge_pct == 0.0
        assert b.state == BatteryState.DEPLETED

    def test_release_from_drone(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1)
        mgr.assign_to_drone(1, drone_id=10)
        b = mgr.release_from_drone(1)
        assert b.assigned_drone_id is None
        assert b.state == BatteryState.AVAILABLE
        assert b.cycle_count == 1

    def test_release_depleted_battery(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1, charge_pct=5.0)
        mgr.assign_to_drone(1, drone_id=10)
        mgr.record_consumption(1, drone_id=10, mission_id="m1", consumed_pct=10.0)
        b = mgr.release_from_drone(1)
        assert b.state == BatteryState.DEPLETED
        assert b.assigned_drone_id is None

    def test_charging_lifecycle(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1, charge_pct=10.0)
        mgr.set_charging(1)
        b = mgr.get_battery(1)
        assert b.state == BatteryState.CHARGING
        mgr.complete_charging(1, charge_pct=100.0)
        b = mgr.get_battery(1)
        assert b.state == BatteryState.AVAILABLE
        assert b.charge_pct == 100.0

    def test_charge_in_use_battery_raises(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1)
        mgr.assign_to_drone(1, drone_id=10)
        with pytest.raises(ValueError, match="in use"):
            mgr.set_charging(1)

    def test_complete_charging_not_charging_raises(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1)
        with pytest.raises(ValueError, match="not charging"):
            mgr.complete_charging(1)

    def test_get_by_state(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1)
        mgr.register_battery(2)
        mgr.register_battery(3)
        mgr.assign_to_drone(2, drone_id=10)
        available = mgr.get_by_state(BatteryState.AVAILABLE)
        assert len(available) == 2
        in_use = mgr.get_by_state(BatteryState.IN_USE)
        assert len(in_use) == 1

    def test_get_available(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1)
        mgr.register_battery(2)
        mgr.assign_to_drone(1, drone_id=10)
        available = mgr.get_available()
        assert len(available) == 1
        assert available[0].battery_id == 2

    def test_consumption_log_filter(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1)
        mgr.register_battery(2)
        mgr.assign_to_drone(1, drone_id=10)
        mgr.assign_to_drone(2, drone_id=20)
        mgr.record_consumption(1, drone_id=10, mission_id="m1", consumed_pct=20.0)
        mgr.record_consumption(2, drone_id=20, mission_id="m2", consumed_pct=15.0)
        all_log = mgr.get_consumption_log()
        assert len(all_log) == 2
        m1_log = mgr.get_consumption_log(mission_id="m1")
        assert len(m1_log) == 1
        assert m1_log[0].mission_id == "m1"

    def test_inventory_summary(self):
        mgr = BatteryInventoryManager()
        mgr.register_battery(1, charge_pct=100.0)
        mgr.register_battery(2, charge_pct=50.0)
        summary = mgr.inventory_summary()
        assert summary["total_batteries"] == 2
        assert summary["avg_charge_pct"] == 75.0
        assert summary["by_state"]["available"] == 2
        assert summary["total_consumption_events"] == 0


# =========================================================================
# LiquidInventoryManager Tests
# =========================================================================

class TestLiquidInventoryManager:
    """Tests for liquid inventory tracking."""

    def test_register_reservoir(self):
        mgr = LiquidInventoryManager()
        r = mgr.register_reservoir(1, capacity_l=10.0)
        assert r.reservoir_id == 1
        assert r.capacity_l == 10.0
        assert r.current_level_l == 10.0
        assert r.state == ReservoirState.FULL
        assert r.assigned_drone_id is None

    def test_register_partial_reservoir(self):
        mgr = LiquidInventoryManager()
        r = mgr.register_reservoir(1, capacity_l=10.0, current_level_l=5.0)
        assert r.current_level_l == 5.0

    def test_register_duplicate_reservoir_raises(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        with pytest.raises(ValueError, match="already registered"):
            mgr.register_reservoir(1, capacity_l=10.0)

    def test_get_reservoir(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        r = mgr.get_reservoir(1)
        assert r.reservoir_id == 1

    def test_get_nonexistent_reservoir_raises(self):
        mgr = LiquidInventoryManager()
        with pytest.raises(ValueError, match="not in inventory"):
            mgr.get_reservoir(999)

    def test_assign_to_drone(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        r = mgr.assign_to_drone(1, drone_id=10)
        assert r.assigned_drone_id == 10

    def test_assign_empty_reservoir_raises(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0, current_level_l=0.0)
        mgr.get_reservoir(1).state = ReservoirState.EMPTY
        with pytest.raises(ValueError, match="not available"):
            mgr.assign_to_drone(1, drone_id=10)

    def test_assign_refilling_reservoir_raises(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        r = mgr.get_reservoir(1)
        r.assigned_drone_id = None
        mgr.set_refilling(1)
        with pytest.raises(ValueError, match="not available"):
            mgr.assign_to_drone(1, drone_id=10)

    def test_record_consumption(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        mgr.assign_to_drone(1, drone_id=10)
        rec = mgr.record_consumption(1, drone_id=10, mission_id="m1", consumed_l=3.0)
        assert rec.start_level_l == 10.0
        assert rec.end_level_l == 7.0
        assert rec.consumed_l == 3.0
        r = mgr.get_reservoir(1)
        assert r.current_level_l == 7.0
        assert r.state == ReservoirState.PARTIAL

    def test_consumption_empties_reservoir(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0, current_level_l=2.0)
        mgr.assign_to_drone(1, drone_id=10)
        mgr.record_consumption(1, drone_id=10, mission_id="m1", consumed_l=5.0)
        r = mgr.get_reservoir(1)
        assert r.current_level_l == 0.0
        assert r.state == ReservoirState.EMPTY

    def test_release_from_drone(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        mgr.assign_to_drone(1, drone_id=10)
        r = mgr.release_from_drone(1)
        assert r.assigned_drone_id is None

    def test_refill_lifecycle(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0, current_level_l=0.0)
        mgr.get_reservoir(1).state = ReservoirState.EMPTY
        mgr.set_refilling(1)
        r = mgr.get_reservoir(1)
        assert r.state == ReservoirState.REFILLING
        mgr.complete_refill(1)
        r = mgr.get_reservoir(1)
        assert r.state == ReservoirState.FULL
        assert r.current_level_l == 10.0

    def test_refill_partial(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0, current_level_l=0.0)
        mgr.get_reservoir(1).state = ReservoirState.EMPTY
        mgr.set_refilling(1)
        mgr.complete_refill(1, fill_level_l=7.0)
        r = mgr.get_reservoir(1)
        assert r.state == ReservoirState.PARTIAL
        assert r.current_level_l == 7.0

    def test_refill_assigned_reservoir_raises(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        mgr.assign_to_drone(1, drone_id=10)
        with pytest.raises(ValueError, match="release before refilling"):
            mgr.set_refilling(1)

    def test_complete_refill_not_refilling_raises(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        with pytest.raises(ValueError, match="not refilling"):
            mgr.complete_refill(1)

    def test_get_by_state(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        mgr.register_reservoir(2, capacity_l=10.0, current_level_l=5.0)
        full = mgr.get_by_state(ReservoirState.FULL)
        assert len(full) == 2

    def test_get_available(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        mgr.register_reservoir(2, capacity_l=10.0, current_level_l=0.0)
        mgr.get_reservoir(2).state = ReservoirState.EMPTY
        available = mgr.get_available()
        assert len(available) == 1

    def test_consumption_log_filter(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        mgr.register_reservoir(2, capacity_l=10.0)
        mgr.assign_to_drone(1, drone_id=10)
        mgr.assign_to_drone(2, drone_id=20)
        mgr.record_consumption(1, drone_id=10, mission_id="m1", consumed_l=3.0)
        mgr.record_consumption(2, drone_id=20, mission_id="m2", consumed_l=2.0)
        all_log = mgr.get_consumption_log()
        assert len(all_log) == 2
        m2_log = mgr.get_consumption_log(mission_id="m2")
        assert len(m2_log) == 1
        assert m2_log[0].mission_id == "m2"

    def test_inventory_summary(self):
        mgr = LiquidInventoryManager()
        mgr.register_reservoir(1, capacity_l=10.0)
        mgr.register_reservoir(2, capacity_l=10.0, current_level_l=5.0)
        summary = mgr.inventory_summary()
        assert summary["total_reservoirs"] == 2
        assert summary["total_capacity_l"] == 20.0
        assert summary["total_current_l"] == 15.0
        assert summary["fill_pct"] == 75.0
        assert summary["total_consumption_events"] == 0


# =========================================================================
# ResourceStateTracker Tests
# =========================================================================

class TestResourceStateTracker:
    """Tests for unified resource state tracking."""

    def _build_tracker(self):
        """Helper to build a ResourceStateTracker with fleet + inventories."""
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        batteries = BatteryInventoryManager()
        batteries.register_battery(101)
        batteries.register_battery(102)
        liquids = LiquidInventoryManager()
        liquids.register_reservoir(201, capacity_l=10.0)
        liquids.register_reservoir(202, capacity_l=10.0)
        tracker = ResourceStateTracker(fleet, batteries, liquids)
        return tracker, fleet, batteries, liquids

    def test_get_drone_resources_no_assignment(self):
        tracker, _, _, _ = self._build_tracker()
        state = tracker.get_drone_resources(1)
        assert state.drone_id == 1
        assert state.battery_id is None
        assert state.reservoir_id is None

    def test_get_drone_resources_with_assignment(self):
        tracker, _, batteries, liquids = self._build_tracker()
        batteries.assign_to_drone(101, drone_id=1)
        liquids.assign_to_drone(201, drone_id=1)
        state = tracker.get_drone_resources(1)
        assert state.battery_id == 101
        assert state.battery_charge_pct == 100.0
        assert state.battery_state == BatteryState.IN_USE
        assert state.reservoir_id == 201
        assert state.liquid_level_l == 10.0
        assert state.reservoir_state == ReservoirState.FULL

    def test_get_drone_resources_nonexistent_drone_raises(self):
        tracker, _, _, _ = self._build_tracker()
        with pytest.raises(ValueError):
            tracker.get_drone_resources(999)

    def test_get_fleet_resources(self):
        tracker, _, batteries, liquids = self._build_tracker()
        batteries.assign_to_drone(101, drone_id=1)
        liquids.assign_to_drone(201, drone_id=2)
        fleet_res = tracker.get_fleet_resources()
        assert len(fleet_res) == 2
        d1 = [r for r in fleet_res if r.drone_id == 1][0]
        d2 = [r for r in fleet_res if r.drone_id == 2][0]
        assert d1.battery_id == 101
        assert d1.reservoir_id is None
        assert d2.battery_id is None
        assert d2.reservoir_id == 201

    def test_build_snapshot(self):
        tracker, _, batteries, liquids = self._build_tracker()
        batteries.assign_to_drone(101, drone_id=1)
        snapshot = tracker.build_snapshot()
        assert isinstance(snapshot, ResourceSnapshot)
        assert snapshot.total_available_batteries == 1
        assert snapshot.total_available_reservoirs == 2
        assert len(snapshot.drone_resources) == 2
        assert snapshot.battery_summary["total_batteries"] == 2
        assert snapshot.liquid_summary["total_reservoirs"] == 2

    def test_get_mission_consumption(self):
        tracker, _, batteries, liquids = self._build_tracker()
        batteries.assign_to_drone(101, drone_id=1)
        liquids.assign_to_drone(201, drone_id=1)
        batteries.record_consumption(101, drone_id=1, mission_id="m1", consumed_pct=25.0)
        liquids.record_consumption(201, drone_id=1, mission_id="m1", consumed_l=4.0)
        result = tracker.get_mission_consumption("m1")
        assert result["mission_id"] == "m1"
        assert result["battery_consumption_events"] == 1
        assert result["total_battery_consumed_pct"] == 25.0
        assert result["liquid_consumption_events"] == 1
        assert result["total_liquid_consumed_l"] == 4.0

    def test_get_mission_consumption_no_records(self):
        tracker, _, _, _ = self._build_tracker()
        result = tracker.get_mission_consumption("m_nonexistent")
        assert result["battery_consumption_events"] == 0
        assert result["liquid_consumption_events"] == 0


# =========================================================================
# Resource Simulation Tests
# =========================================================================

class TestResourceSimulation:
    """Integration tests for multi-mission resource tracking."""

    def test_multi_mission_resource_isolation(self):
        """Resources consumed by mission A do not affect mission B."""
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        batteries = BatteryInventoryManager()
        batteries.register_battery(101)
        batteries.register_battery(102)
        liquids = LiquidInventoryManager()
        liquids.register_reservoir(201, capacity_l=10.0)
        liquids.register_reservoir(202, capacity_l=10.0)
        tracker = ResourceStateTracker(fleet, batteries, liquids)

        batteries.assign_to_drone(101, drone_id=1)
        liquids.assign_to_drone(201, drone_id=1)
        batteries.assign_to_drone(102, drone_id=2)
        liquids.assign_to_drone(202, drone_id=2)

        batteries.record_consumption(101, drone_id=1, mission_id="mA", consumed_pct=40.0)
        liquids.record_consumption(201, drone_id=1, mission_id="mA", consumed_l=6.0)

        batteries.record_consumption(102, drone_id=2, mission_id="mB", consumed_pct=20.0)
        liquids.record_consumption(202, drone_id=2, mission_id="mB", consumed_l=3.0)

        mA = tracker.get_mission_consumption("mA")
        mB = tracker.get_mission_consumption("mB")
        assert mA["total_battery_consumed_pct"] == 40.0
        assert mA["total_liquid_consumed_l"] == 6.0
        assert mB["total_battery_consumed_pct"] == 20.0
        assert mB["total_liquid_consumed_l"] == 3.0

        d1 = tracker.get_drone_resources(1)
        d2 = tracker.get_drone_resources(2)
        assert d1.battery_charge_pct == 60.0
        assert d1.liquid_level_l == 4.0
        assert d2.battery_charge_pct == 80.0
        assert d2.liquid_level_l == 7.0

    def test_sequential_mission_resource_reuse(self):
        """Resources can be reused across missions after release and recharge."""
        batteries = BatteryInventoryManager()
        batteries.register_battery(1, charge_pct=100.0)

        batteries.assign_to_drone(1, drone_id=10)
        batteries.record_consumption(1, drone_id=10, mission_id="m1", consumed_pct=60.0)
        batteries.release_from_drone(1)
        assert batteries.get_battery(1).charge_pct == 40.0

        batteries.set_charging(1)
        batteries.complete_charging(1, charge_pct=100.0)
        assert batteries.get_battery(1).state == BatteryState.AVAILABLE

        batteries.assign_to_drone(1, drone_id=20)
        batteries.record_consumption(1, drone_id=20, mission_id="m2", consumed_pct=30.0)
        assert batteries.get_battery(1).charge_pct == 70.0
        assert batteries.get_battery(1).cycle_count == 1

        log = batteries.get_consumption_log()
        assert len(log) == 2
        assert log[0].mission_id == "m1"
        assert log[1].mission_id == "m2"

    def test_full_resource_lifecycle(self):
        """Full lifecycle: register, assign, consume, release, recharge/refill."""
        fleet = FleetRegistry()
        fleet.register_drone(1)
        batteries = BatteryInventoryManager()
        batteries.register_battery(101)
        liquids = LiquidInventoryManager()
        liquids.register_reservoir(201, capacity_l=10.0)
        tracker = ResourceStateTracker(fleet, batteries, liquids)

        batteries.assign_to_drone(101, drone_id=1)
        liquids.assign_to_drone(201, drone_id=1)

        batteries.record_consumption(101, drone_id=1, mission_id="m1", consumed_pct=50.0)
        liquids.record_consumption(201, drone_id=1, mission_id="m1", consumed_l=8.0)

        d1 = tracker.get_drone_resources(1)
        assert d1.battery_charge_pct == 50.0
        assert d1.liquid_level_l == 2.0

        batteries.release_from_drone(101)
        liquids.release_from_drone(201)

        batteries.set_charging(101)
        batteries.complete_charging(101, charge_pct=100.0)
        liquids.set_refilling(201)
        liquids.complete_refill(201)

        snapshot = tracker.build_snapshot()
        assert snapshot.total_available_batteries == 1
        assert snapshot.total_available_reservoirs == 1
        assert batteries.get_battery(101).charge_pct == 100.0
        assert liquids.get_reservoir(201).current_level_l == 10.0

    def test_deterministic_resource_state(self):
        """Same operations produce identical resource state."""
        def run_scenario():
            batteries = BatteryInventoryManager()
            batteries.register_battery(1, charge_pct=100.0)
            batteries.register_battery(2, charge_pct=80.0)
            batteries.assign_to_drone(1, drone_id=10)
            batteries.record_consumption(1, drone_id=10, mission_id="m1", consumed_pct=35.0)
            return batteries.inventory_summary()

        result1 = run_scenario()
        result2 = run_scenario()
        assert result1 == result2


# =========================================================================
# Backward Compatibility Tests
# =========================================================================

class TestBackwardCompatibility:
    """Verify Phase 0–8.3 behavior is unchanged."""

    def test_fleet_registry_unchanged(self):
        """FleetRegistry works exactly as before without resource system."""
        fleet = FleetRegistry()
        fleet.register_drone(1)
        fleet.register_drone(2)
        assert fleet.fleet_size == 2
        assert len(fleet.get_available()) == 2
        health = fleet.fleet_health_snapshot()
        assert health["total_drones"] == 2

    def test_pipeline_unchanged_without_resource_system(self):
        """Existing v0.1 pipeline produces identical output when resource system is not invoked."""
        from core.mission_intake import create_mission_profile
        from core.environment_analyzer import analyze_environment
        from core.swarm_planner import plan_swarm
        from core.route_planner import plan_routes
        from core.resource_planner import plan_resources
        from core.risk_engine import evaluate_risks
        from core.decision_engine import generate_recommendation

        profile = create_mission_profile(
            field_size_ha=50.0,
            crop_type="wheat",
            num_drones=4,
            battery_capacity_mah=5000,
            liquid_capacity_l=10.0,
            temperature_c=25.0,
            wind_speed_kmh=10.0,
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
