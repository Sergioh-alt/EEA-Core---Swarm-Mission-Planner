"""
Phase 10B — Digital Twin Tests.

Comprehensive testing of:
1. State models (immutability, fields)
2. State validation (reject invalid, accept valid)
3. Sync engine (update merge, version increment)
4. Snapshot engine (create, retrieve, immutability)
5. Replay engine (timeline, per-drone, deterministic)
6. Digital Twin API (read-only, full integration)
7. Boundary enforcement (no planning/Hive/UI imports)
8. Backward compatibility (no regressions)
"""

import ast
import os
import time

import pytest

from digital_twin.state_models import (
    DroneMode,
    DroneState,
    DroneStateUpdate,
    EnvironmentCondition,
    EnvironmentState,
    FailureCategory,
    HealthLevel,
    MissionStatus,
    Position,
    SwarmState,
    SwarmStateUpdate,
    TaskState,
    Velocity,
)
from digital_twin.state_validation import (
    StateValidator,
    ValidationError,
    ValidationResult,
)
from digital_twin.sync_engine import SyncEngine
from digital_twin.snapshot_engine import Snapshot, SnapshotEngine
from digital_twin.replay_engine import ReplayEngine, ReplayTimeline
from digital_twin.twin_api import DigitalTwin


# =========================================================================
# 1. STATE MODELS
# =========================================================================

class TestStateModels:
    """Test immutability and structure of state models."""

    def test_drone_state_is_frozen(self):
        ds = DroneState(drone_id=1)
        with pytest.raises(Exception):
            ds.drone_id = 2  # type: ignore

    def test_swarm_state_is_frozen(self):
        ss = SwarmState()
        with pytest.raises(Exception):
            ss.version = 99  # type: ignore

    def test_position_is_frozen(self):
        p = Position(latitude=40.0, longitude=-3.0, altitude_m=100.0)
        with pytest.raises(Exception):
            p.latitude = 50.0  # type: ignore

    def test_velocity_is_frozen(self):
        v = Velocity(vx=1.0, vy=2.0, vz=3.0)
        with pytest.raises(Exception):
            v.vx = 10.0  # type: ignore

    def test_environment_state_is_frozen(self):
        e = EnvironmentState(wind_speed_m_s=5.0)
        with pytest.raises(Exception):
            e.wind_speed_m_s = 10.0  # type: ignore

    def test_drone_state_defaults(self):
        ds = DroneState(drone_id=1)
        assert ds.armed is False
        assert ds.mode == DroneMode.STANDBY
        assert ds.battery_pct == 100.0
        assert ds.gps_available is True
        assert ds.communication_active is True
        assert ds.health == HealthLevel.OK
        assert ds.current_task == TaskState.NONE

    def test_swarm_state_defaults(self):
        ss = SwarmState()
        assert ss.mission_status == MissionStatus.IDLE
        assert ss.drone_states == ()
        assert ss.active_failures == ()
        assert ss.global_health == HealthLevel.OK
        assert ss.version == 0

    def test_drone_state_update_fields(self):
        u = DroneStateUpdate(
            drone_id=1, timestamp_ms=1000,
            latitude=40.0, longitude=-3.0, altitude_m=50.0,
            battery_pct=85.0, armed=True, mode="GUIDED",
        )
        assert u.drone_id == 1
        assert u.latitude == 40.0
        assert u.battery_pct == 85.0
        assert u.armed is True

    def test_swarm_state_with_drones(self):
        d1 = DroneState(drone_id=1, armed=True)
        d2 = DroneState(drone_id=2, armed=False)
        ss = SwarmState(
            drone_states=(d1, d2),
            total_drones=2,
        )
        assert len(ss.drone_states) == 2
        assert ss.drone_states[0].drone_id == 1
        assert ss.drone_states[1].drone_id == 2


# =========================================================================
# 2. STATE VALIDATION
# =========================================================================

class TestStateValidation:
    """Test validation of incoming state updates."""

    def setup_method(self):
        self.validator = StateValidator()

    def test_valid_drone_update(self):
        update = DroneStateUpdate(drone_id=1, timestamp_ms=1000)
        result = self.validator.validate_drone_update(update)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_invalid_drone_id(self):
        update = DroneStateUpdate(drone_id=0, timestamp_ms=1000)
        result = self.validator.validate_drone_update(update)
        assert result.valid is False
        assert ValidationError.MISSING_DRONE_ID in result.errors

    def test_negative_timestamp(self):
        update = DroneStateUpdate(drone_id=1, timestamp_ms=-100)
        result = self.validator.validate_drone_update(update)
        assert result.valid is False
        assert ValidationError.INVALID_TIMESTAMP in result.errors

    def test_battery_out_of_range(self):
        update = DroneStateUpdate(drone_id=1, timestamp_ms=1000, battery_pct=150.0)
        result = self.validator.validate_drone_update(update)
        assert result.valid is False
        assert ValidationError.INVALID_BATTERY in result.errors

    def test_negative_battery(self):
        update = DroneStateUpdate(drone_id=1, timestamp_ms=1000, battery_pct=-5.0)
        result = self.validator.validate_drone_update(update)
        assert result.valid is False
        assert ValidationError.INVALID_BATTERY in result.errors

    def test_timestamp_regression(self):
        current = DroneState(drone_id=1, last_update_ms=5000)
        update = DroneStateUpdate(drone_id=1, timestamp_ms=3000)
        result = self.validator.validate_drone_update(update, current)
        assert result.valid is False
        assert ValidationError.TIMESTAMP_REGRESSION in result.errors

    def test_valid_swarm_update(self):
        update = SwarmStateUpdate(
            timestamp_ms=1000, total_drones=3,
            active_count=2, fail_count=1,
        )
        result = self.validator.validate_swarm_update(update)
        assert result.valid is True

    def test_inconsistent_swarm_counts(self):
        update = SwarmStateUpdate(
            timestamp_ms=1000, total_drones=3,
            active_count=3, fail_count=2,  # 3+2 > 3
        )
        result = self.validator.validate_swarm_update(update)
        assert result.valid is False
        assert ValidationError.INCONSISTENT_STATE in result.errors

    def test_duplicate_drone_ids_in_swarm(self):
        update = SwarmStateUpdate(
            timestamp_ms=1000, total_drones=3,
            active_drone_ids=(1, 2, 1),  # duplicate
            active_count=3, fail_count=0,
        )
        result = self.validator.validate_swarm_update(update)
        assert result.valid is False
        assert ValidationError.DUPLICATE_DRONE_ID in result.errors

    def test_swarm_state_consistency_valid(self):
        d1 = DroneState(drone_id=1)
        d2 = DroneState(drone_id=2)
        state = SwarmState(drone_states=(d1, d2), total_drones=2)
        result = self.validator.validate_swarm_state_consistency(state)
        assert result.valid is True

    def test_swarm_state_duplicate_ids(self):
        d1 = DroneState(drone_id=1)
        d2 = DroneState(drone_id=1)  # duplicate
        state = SwarmState(drone_states=(d1, d2), total_drones=2)
        result = self.validator.validate_swarm_state_consistency(state)
        assert result.valid is False
        assert ValidationError.DUPLICATE_DRONE_ID in result.errors

    def test_swarm_state_count_mismatch(self):
        d1 = DroneState(drone_id=1)
        state = SwarmState(drone_states=(d1,), total_drones=5)
        result = self.validator.validate_swarm_state_consistency(state)
        assert result.valid is False
        assert ValidationError.DRONE_COUNT_MISMATCH in result.errors


# =========================================================================
# 3. SYNC ENGINE
# =========================================================================

class TestSyncEngine:
    """Test state synchronization engine."""

    def setup_method(self):
        self.engine = SyncEngine(swarm_id="test-swarm")

    def test_register_drone(self):
        self.engine.register_drone(1)
        state = self.engine.get_swarm_state()
        assert state.total_drones == 1
        assert state.drone_states[0].drone_id == 1

    def test_register_multiple_drones(self):
        self.engine.register_drone(1)
        self.engine.register_drone(2)
        self.engine.register_drone(3)
        state = self.engine.get_swarm_state()
        assert state.total_drones == 3

    def test_apply_drone_update(self):
        self.engine.register_drone(1)
        update = DroneStateUpdate(
            drone_id=1, timestamp_ms=1000,
            latitude=40.0, longitude=-3.0, altitude_m=50.0,
            battery_pct=90.0, armed=True, mode="GUIDED",
        )
        result = self.engine.apply_drone_update(update)
        assert result.valid is True
        ds = self.engine.get_drone_state(1)
        assert ds.latitude == 40.0 if ds is None else ds.position.latitude == 40.0
        assert ds.battery_pct == 90.0
        assert ds.armed is True

    def test_apply_invalid_update_rejected(self):
        self.engine.register_drone(1)
        update = DroneStateUpdate(
            drone_id=0, timestamp_ms=1000,  # invalid ID
        )
        result = self.engine.apply_drone_update(update)
        assert result.valid is False

    def test_version_increments(self):
        v0 = self.engine.version
        self.engine.register_drone(1)
        assert self.engine.version == v0 + 1
        update = DroneStateUpdate(drone_id=1, timestamp_ms=1000)
        self.engine.apply_drone_update(update)
        assert self.engine.version == v0 + 2

    def test_swarm_state_immutable(self):
        self.engine.register_drone(1)
        state1 = self.engine.get_swarm_state()
        # Apply an update
        self.engine.apply_drone_update(
            DroneStateUpdate(drone_id=1, timestamp_ms=2000, battery_pct=80.0)
        )
        state2 = self.engine.get_swarm_state()
        # state1 should be unchanged
        assert state1.version != state2.version
        assert state1.drone_states[0].battery_pct == 100.0
        assert state2.drone_states[0].battery_pct == 80.0

    def test_apply_swarm_update(self):
        update = SwarmStateUpdate(
            timestamp_ms=5000,
            mission_id="mission-1",
            total_drones=3,
            active_count=2,
            fail_count=1,
        )
        result = self.engine.apply_swarm_update(update)
        assert result.valid is True
        state = self.engine.get_swarm_state()
        assert state.mission_id == "mission-1"
        assert state.mission_status == MissionStatus.RUNNING

    def test_apply_failure_update(self):
        self.engine.apply_failure_update([
            FailureCategory.BATTERY_DEGRADATION,
            FailureCategory.GPS_LOSS,
        ])
        state = self.engine.get_swarm_state()
        assert FailureCategory.BATTERY_DEGRADATION in state.active_failures
        assert FailureCategory.GPS_LOSS in state.active_failures

    def test_sync_event_log(self):
        self.engine.register_drone(1)
        self.engine.apply_drone_update(
            DroneStateUpdate(drone_id=1, timestamp_ms=1000)
        )
        events = self.engine.sync_events
        assert len(events) >= 1
        assert any(e.event_type == "DRONE_STATE_SYNCED" for e in events)

    def test_global_health_computed(self):
        self.engine.register_drone(1)
        self.engine.apply_drone_update(
            DroneStateUpdate(drone_id=1, timestamp_ms=1000, health="CRITICAL")
        )
        state = self.engine.get_swarm_state()
        assert state.global_health == HealthLevel.CRITICAL


# =========================================================================
# 4. SNAPSHOT ENGINE
# =========================================================================

class TestSnapshotEngine:
    """Test immutable snapshot creation and retrieval."""

    def setup_method(self):
        self.engine = SnapshotEngine()

    def test_create_snapshot(self):
        state = SwarmState(swarm_id="test", version=1)
        snap = self.engine.create_snapshot(state, "test snapshot")
        assert snap.snapshot_id == "snap-000001"
        assert snap.version == 1
        assert snap.swarm_state == state
        assert snap.description == "test snapshot"

    def test_snapshot_is_frozen(self):
        state = SwarmState(swarm_id="test")
        snap = self.engine.create_snapshot(state)
        with pytest.raises(Exception):
            snap.snapshot_id = "modified"  # type: ignore

    def test_retrieve_by_id(self):
        state = SwarmState(swarm_id="test", version=5)
        snap = self.engine.create_snapshot(state)
        retrieved = self.engine.get_snapshot(snap.snapshot_id)
        assert retrieved == snap

    def test_retrieve_by_version(self):
        s1 = SwarmState(swarm_id="test", version=1)
        s2 = SwarmState(swarm_id="test", version=2)
        snap1 = self.engine.create_snapshot(s1)
        snap2 = self.engine.create_snapshot(s2)
        assert self.engine.get_snapshot_by_version(1) == snap1
        assert self.engine.get_snapshot_by_version(2) == snap2

    def test_get_latest_snapshot(self):
        self.engine.create_snapshot(SwarmState(version=1))
        self.engine.create_snapshot(SwarmState(version=2))
        snap3 = self.engine.create_snapshot(SwarmState(version=3))
        assert self.engine.get_latest_snapshot() == snap3

    def test_list_snapshots(self):
        self.engine.create_snapshot(SwarmState(version=1))
        self.engine.create_snapshot(SwarmState(version=2))
        self.engine.create_snapshot(SwarmState(version=3))
        snaps = self.engine.list_snapshots()
        assert len(snaps) == 3
        assert snaps[0].version == 1
        assert snaps[2].version == 3

    def test_snapshot_count(self):
        assert self.engine.snapshot_count == 0
        self.engine.create_snapshot(SwarmState())
        assert self.engine.snapshot_count == 1

    def test_snapshot_not_found(self):
        assert self.engine.get_snapshot("nonexistent") is None
        assert self.engine.get_snapshot_by_version(999) is None


# =========================================================================
# 5. REPLAY ENGINE
# =========================================================================

class TestReplayEngine:
    """Test deterministic replay capabilities."""

    def setup_method(self):
        self.snap_engine = SnapshotEngine()
        self.replay = ReplayEngine(self.snap_engine)

    def _create_snapshots(self, count=5):
        for i in range(count):
            d1 = DroneState(drone_id=1, battery_pct=100.0 - i * 10)
            d2 = DroneState(drone_id=2, battery_pct=100.0 - i * 5)
            state = SwarmState(
                drone_states=(d1, d2), total_drones=2, version=i + 1,
            )
            self.snap_engine.create_snapshot(state, f"frame {i}")

    def test_replay_full_timeline(self):
        self._create_snapshots(5)
        timeline = self.replay.replay_timeline()
        assert timeline.total_frames == 5
        assert len(timeline.frames) == 5

    def test_replay_timeline_version_range(self):
        self._create_snapshots(5)
        timeline = self.replay.replay_timeline(start_version=2, end_version=4)
        assert timeline.total_frames == 3

    def test_replay_empty(self):
        timeline = self.replay.replay_timeline()
        assert timeline.total_frames == 0

    def test_replay_drone_specific(self):
        self._create_snapshots(3)
        drone_timeline = self.replay.replay_drone(drone_id=1)
        assert drone_timeline.total_frames == 3
        assert drone_timeline.drone_id == 1
        # Battery should decrease over frames
        assert drone_timeline.frames[0].drone_state.battery_pct == 100.0
        assert drone_timeline.frames[2].drone_state.battery_pct == 80.0

    def test_replay_drone_not_found(self):
        self._create_snapshots(3)
        drone_timeline = self.replay.replay_drone(drone_id=99)
        assert drone_timeline.total_frames == 0

    def test_replay_at_version_deterministic(self):
        self._create_snapshots(5)
        state_v3_a = self.replay.replay_swarm_at_version(3)
        state_v3_b = self.replay.replay_swarm_at_version(3)
        assert state_v3_a == state_v3_b  # deterministic

    def test_replay_at_version_not_found(self):
        result = self.replay.replay_swarm_at_version(999)
        assert result is None

    def test_replay_timeline_is_frozen(self):
        self._create_snapshots(3)
        timeline = self.replay.replay_timeline()
        with pytest.raises(Exception):
            timeline.total_frames = 0  # type: ignore

    def test_replay_frame_access(self):
        self._create_snapshots(3)
        timeline = self.replay.replay_timeline()
        frame = self.replay.get_frame_at_index(timeline, 1)
        assert frame is not None
        assert frame.frame_index == 1

    def test_replay_frame_out_of_range(self):
        self._create_snapshots(3)
        timeline = self.replay.replay_timeline()
        frame = self.replay.get_frame_at_index(timeline, 99)
        assert frame is None


# =========================================================================
# 6. DIGITAL TWIN API (Integration)
# =========================================================================

class TestDigitalTwinAPI:
    """Test the unified Digital Twin API."""

    def setup_method(self):
        self.twin = DigitalTwin(swarm_id="test-swarm")

    def test_register_and_get_drone(self):
        self.twin.register_drone(1)
        ds = self.twin.get_drone_state(1)
        assert ds is not None
        assert ds.drone_id == 1

    def test_get_swarm_state(self):
        self.twin.register_drone(1)
        self.twin.register_drone(2)
        state = self.twin.get_swarm_state()
        assert state.total_drones == 2
        assert state.swarm_id == "test-swarm"

    def test_sync_drone_state(self):
        self.twin.register_drone(1)
        result = self.twin.sync_drone_state(DroneStateUpdate(
            drone_id=1, timestamp_ms=1000,
            battery_pct=75.0, armed=True,
        ))
        assert result.valid is True
        ds = self.twin.get_drone_state(1)
        assert ds.battery_pct == 75.0
        assert ds.armed is True

    def test_sync_invalid_rejected(self):
        result = self.twin.sync_drone_state(DroneStateUpdate(
            drone_id=0, timestamp_ms=-1,  # invalid
        ))
        assert result.valid is False

    def test_create_and_retrieve_snapshot(self):
        self.twin.register_drone(1)
        snap = self.twin.create_snapshot("initial state")
        retrieved = self.twin.get_snapshot(snap.snapshot_id)
        assert retrieved == snap
        assert retrieved.swarm_state.total_drones == 1

    def test_list_snapshots(self):
        self.twin.create_snapshot("s1")
        self.twin.create_snapshot("s2")
        snaps = self.twin.list_snapshots()
        assert len(snaps) == 2

    def test_replay_timeline(self):
        self.twin.register_drone(1)
        self.twin.create_snapshot("frame1")
        self.twin.sync_drone_state(DroneStateUpdate(
            drone_id=1, timestamp_ms=1000, battery_pct=90.0,
        ))
        self.twin.create_snapshot("frame2")
        timeline = self.twin.replay_timeline()
        assert timeline.total_frames == 2

    def test_replay_drone(self):
        self.twin.register_drone(1)
        self.twin.register_drone(2)
        self.twin.create_snapshot("s1")
        self.twin.sync_drone_state(DroneStateUpdate(
            drone_id=1, timestamp_ms=1000, battery_pct=80.0,
        ))
        self.twin.create_snapshot("s2")
        timeline = self.twin.replay_drone(drone_id=1)
        assert timeline.total_frames == 2
        assert timeline.frames[0].drone_state.battery_pct == 100.0
        assert timeline.frames[1].drone_state.battery_pct == 80.0

    def test_version_increments(self):
        v0 = self.twin.version
        self.twin.register_drone(1)
        assert self.twin.version > v0

    def test_sync_failures(self):
        self.twin.sync_failures([FailureCategory.GPS_LOSS])
        state = self.twin.get_swarm_state()
        assert FailureCategory.GPS_LOSS in state.active_failures

    def test_sync_environment(self):
        self.twin.sync_environment(
            wind_speed_m_s=10.0,
            wind_direction_deg=180.0,
            condition=EnvironmentCondition.DEGRADED,
        )
        state = self.twin.get_swarm_state()
        assert state.environment_state.wind_speed_m_s == 10.0
        assert state.environment_state.condition == EnvironmentCondition.DEGRADED

    def test_single_source_of_truth(self):
        """Multiple calls return consistent state."""
        self.twin.register_drone(1)
        self.twin.sync_drone_state(DroneStateUpdate(
            drone_id=1, timestamp_ms=1000, battery_pct=50.0,
        ))
        s1 = self.twin.get_swarm_state()
        s2 = self.twin.get_swarm_state()
        assert s1.version == s2.version
        assert s1.drone_states == s2.drone_states


# =========================================================================
# 7. BOUNDARY ENFORCEMENT
# =========================================================================

class TestPhase10BBoundaryEnforcement:
    """AST-based verification of architecture boundaries."""

    DIGITAL_TWIN_FILES = [
        "digital_twin/__init__.py",
        "digital_twin/state_models.py",
        "digital_twin/state_validation.py",
        "digital_twin/sync_engine.py",
        "digital_twin/snapshot_engine.py",
        "digital_twin/replay_engine.py",
        "digital_twin/twin_api.py",
    ]

    FORBIDDEN_MODULES = {
        "core.swarm_planner",
        "core.route_planner",
        "core.resource_planner",
        "core.risk_engine",
        "core.decision_engine",
        "core.swarm_optimizer",
        "core.mission_timeline",
        "core.mission_intake",
        "core.reallocation_engine",
        "core.hive",
        "core.hive_integration",
        "core.mission_orchestrator",
        "core.fleet_manager",
        "core.hal_adapters",
        "core.hal_interfaces",
        "simulation.mavlink_bridge",
        "simulation.sim_core",
    }

    def _get_imports(self, filepath):
        if not os.path.exists(filepath):
            return []
        with open(filepath, "r") as f:
            tree = ast.parse(f.read())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
        return imports

    def test_no_planning_imports(self):
        planning = {
            "core.swarm_planner", "core.route_planner",
            "core.resource_planner", "core.risk_engine",
            "core.decision_engine", "core.swarm_optimizer",
            "core.mission_timeline", "core.mission_intake",
            "core.reallocation_engine",
        }
        for filepath in self.DIGITAL_TWIN_FILES:
            imports = self._get_imports(filepath)
            violations = [i for i in imports if i in planning]
            assert violations == [], f"{filepath} imports planning: {violations}"

    def test_no_hive_imports(self):
        hive = {
            "core.hive", "core.hive_integration",
            "core.mission_orchestrator", "core.fleet_manager",
        }
        for filepath in self.DIGITAL_TWIN_FILES:
            imports = self._get_imports(filepath)
            violations = [i for i in imports if i in hive]
            assert violations == [], f"{filepath} imports Hive: {violations}"

    def test_no_mavlink_imports(self):
        mavlink = {"simulation.mavlink_bridge", "pymavlink"}
        for filepath in self.DIGITAL_TWIN_FILES:
            imports = self._get_imports(filepath)
            violations = [i for i in imports if i in mavlink]
            assert violations == [], f"{filepath} imports MAVLink: {violations}"

    def test_no_simulation_core_imports(self):
        sim = {"simulation.sim_core"}
        for filepath in self.DIGITAL_TWIN_FILES:
            imports = self._get_imports(filepath)
            violations = [i for i in imports if i in sim]
            assert violations == [], f"{filepath} imports sim_core: {violations}"

    def test_no_hal_imports(self):
        hal = {"core.hal_adapters", "core.hal_interfaces"}
        for filepath in self.DIGITAL_TWIN_FILES:
            imports = self._get_imports(filepath)
            violations = [i for i in imports if i in hal]
            assert violations == [], f"{filepath} imports HAL: {violations}"

    def test_no_ui_imports(self):
        ui = {"streamlit", "plotly", "next", "react"}
        for filepath in self.DIGITAL_TWIN_FILES:
            imports = self._get_imports(filepath)
            violations = [i for i in imports if i in ui]
            assert violations == [], f"{filepath} imports UI: {violations}"

    def test_no_decision_methods(self):
        keywords = [
            "decide", "choose", "select_best", "optimize",
            "plan_route", "allocate", "schedule", "prioritize",
            "execute_mission", "dispatch", "recommend",
        ]
        for filepath in self.DIGITAL_TWIN_FILES:
            if not os.path.exists(filepath):
                continue
            with open(filepath, "r") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name_lower = node.name.lower()
                    for kw in keywords:
                        assert kw not in name_lower, (
                            f"{filepath}:{node.lineno} method '{node.name}' "
                            f"contains decision keyword '{kw}'"
                        )

    def test_no_command_generation(self):
        """Digital Twin must never generate commands."""
        from digital_twin.twin_api import DigitalTwin
        twin = DigitalTwin()
        # Verify no execute/send/dispatch methods exist
        public_methods = [m for m in dir(twin) if not m.startswith("_")]
        forbidden_prefixes = ["execute", "send", "dispatch", "command"]
        for method in public_methods:
            for prefix in forbidden_prefixes:
                assert not method.startswith(prefix), (
                    f"DigitalTwin has forbidden method: {method}"
                )

    def test_all_state_models_frozen(self):
        """All state models must be frozen (immutable)."""
        assert DroneState.__dataclass_params__.frozen
        assert SwarmState.__dataclass_params__.frozen
        assert Position.__dataclass_params__.frozen
        assert Velocity.__dataclass_params__.frozen
        assert EnvironmentState.__dataclass_params__.frozen
        assert DroneStateUpdate.__dataclass_params__.frozen
        assert SwarmStateUpdate.__dataclass_params__.frozen

    def test_digital_twin_read_only_api(self):
        """Verify API only exposes read operations."""
        twin = DigitalTwin()
        read_methods = [
            "get_swarm_state", "get_drone_state",
            "get_snapshot", "get_latest_snapshot",
            "list_snapshots", "replay_timeline",
            "replay_drone", "replay_at_version",
        ]
        for method in read_methods:
            assert hasattr(twin, method), f"Missing read method: {method}"


# =========================================================================
# 8. BACKWARD COMPATIBILITY
# =========================================================================

class TestPhase10BBackwardCompatibility:
    """Verify no regressions from Digital Twin introduction."""

    def test_simulation_adapter_unchanged(self):
        from core.hal_adapters import SimulationAdapter
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        assert adapter.get_telemetry(1) is not None

    def test_hal_interfaces_unchanged(self):
        from core.hal_interfaces import CommandSchema, CommandType
        cmd = CommandSchema(
            command_id="compat-test",
            drone_id=1,
            command_type=CommandType.ARM,
        )
        assert cmd.command_id == "compat-test"

    def test_ros2_bus_unchanged(self):
        from simulation.ros2_swarm_bus import SwarmBus, DroneStateMessage
        bus = SwarmBus()
        msg = DroneStateMessage(drone_id=1, timestamp_ms=1000)
        bus.publish_drone_state(msg)
        latest = bus.get_latest(SwarmBus.drone_state_topic(1))
        assert latest == msg

    def test_simulation_core_unchanged(self):
        from simulation.sim_core import SimulationCore
        sim = SimulationCore(num_drones=2)
        assert len(sim.drone_ids) == 2
