"""
Phase 9.3 — Telemetry Stream System Tests.

Tests for DroneTelemetryFrame, FleetTelemetrySnapshot,
TelemetryStreamProcessor, and telemetry contract compliance.
"""

import ast

from core.hal_interfaces import (
    FlightState,
    GPSPosition,
)
from core.hal_adapters import SimulationAdapter
from core.hal_telemetry import (
    DroneTelemetryFrame,
    FleetTelemetrySnapshot,
    GPSFixQuality,
    TaskState,
    TelemetryStreamProcessor,
    Velocity3D,
    FLIGHT_STATE_TO_TASK,
)
from core.hal_interfaces import CommandSchema, CommandType


# =========================================================================
# DroneTelemetryFrame Tests
# =========================================================================

class TestDroneTelemetryFrame:
    """Verify telemetry frame data structure."""

    def test_create_frame(self):
        frame = DroneTelemetryFrame(
            drone_id=1,
            position=GPSPosition(40.0, -3.0, 15.0),
            velocity=Velocity3D(5.0, 0.0, 0.0),
            heading_deg=90.0,
            battery_level_pct=85.0,
            power_draw_w=120.0,
            mission_id="m1",
            task_state=TaskState.WORKING,
            gps_fix_quality=GPSFixQuality.FIX_3D,
            signal_strength_pct=95.0,
            timestamp_ms=1000,
        )
        assert frame.drone_id == 1
        assert frame.position.latitude == 40.0
        assert frame.velocity.vx == 5.0
        assert frame.battery_level_pct == 85.0
        assert frame.mission_id == "m1"
        assert frame.task_state == TaskState.WORKING

    def test_nullable_mission_id(self):
        frame = DroneTelemetryFrame(
            drone_id=1,
            position=GPSPosition(0.0, 0.0, 0.0),
            velocity=Velocity3D(),
            heading_deg=0.0,
            battery_level_pct=100.0,
            power_draw_w=0.0,
            mission_id=None,
            task_state=TaskState.IDLE,
            gps_fix_quality=GPSFixQuality.NO_FIX,
            signal_strength_pct=0.0,
            timestamp_ms=0,
        )
        assert frame.mission_id is None

    def test_all_required_fields_present(self):
        """Telemetry contract: all mandatory fields exist."""
        required = {
            "drone_id", "position", "velocity", "heading_deg",
            "battery_level_pct", "power_draw_w", "mission_id",
            "task_state", "gps_fix_quality", "signal_strength_pct",
            "timestamp_ms",
        }
        actual = {f.name for f in DroneTelemetryFrame.__dataclass_fields__.values()}
        assert required.issubset(actual)

    def test_all_task_states_exist(self):
        expected = {"idle", "en_route", "working", "returning", "emergency", "landed"}
        actual = {ts.value for ts in TaskState}
        assert actual == expected


# =========================================================================
# FleetTelemetrySnapshot Tests
# =========================================================================

class TestFleetTelemetrySnapshot:
    """Verify fleet-wide telemetry snapshot."""

    def test_create_snapshot(self):
        snap = FleetTelemetrySnapshot(
            total_drones=4,
            active_drones=2,
            idle_drones=1,
            charging_drones=0,
            faulty_drones=1,
            global_timestamp_ms=5000,
        )
        assert snap.total_drones == 4
        assert snap.active_drones == 2
        assert snap.faulty_drones == 1
        assert snap.frames == []

    def test_all_required_fields_present(self):
        """Fleet snapshot contract: all mandatory fields exist."""
        required = {
            "total_drones", "active_drones", "idle_drones",
            "charging_drones", "faulty_drones", "global_timestamp_ms",
        }
        actual = {f.name for f in FleetTelemetrySnapshot.__dataclass_fields__.values()}
        assert required.issubset(actual)


# =========================================================================
# TelemetryStreamProcessor Tests
# =========================================================================

class TestTelemetryStreamProcessor:
    """Verify telemetry normalization and streaming."""

    def _setup_adapter(self, num_drones=1):
        adapter = SimulationAdapter()
        for i in range(1, num_drones + 1):
            adapter.register_drone(i)
        return adapter

    def test_read_single_frame(self):
        adapter = self._setup_adapter()
        proc = TelemetryStreamProcessor(adapter)
        proc.register_drone(1)
        frame = proc.read_frame(1)
        assert isinstance(frame, DroneTelemetryFrame)
        assert frame.drone_id == 1
        assert frame.task_state == TaskState.LANDED
        assert frame.battery_level_pct == 100.0

    def test_read_all_frames(self):
        adapter = self._setup_adapter(num_drones=3)
        proc = TelemetryStreamProcessor(adapter)
        for i in range(1, 4):
            proc.register_drone(i)
        frames = proc.read_all_frames()
        assert len(frames) == 3
        assert {f.drone_id for f in frames} == {1, 2, 3}

    def test_flight_state_to_task_mapping(self):
        adapter = self._setup_adapter()
        proc = TelemetryStreamProcessor(adapter)
        proc.register_drone(1)

        adapter.arm(1)
        frame = proc.read_frame(1)
        assert frame.task_state == TaskState.IDLE

        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        frame = proc.read_frame(1)
        assert frame.task_state == TaskState.WORKING

        adapter.return_to_home(1)
        frame = proc.read_frame(1)
        assert frame.task_state == TaskState.RETURNING

    def test_mission_id_tracked(self):
        adapter = self._setup_adapter()
        proc = TelemetryStreamProcessor(adapter)
        proc.register_drone(1, mission_id="m1")
        frame = proc.read_frame(1)
        assert frame.mission_id == "m1"

        proc.set_mission(1, "m2")
        frame = proc.read_frame(1)
        assert frame.mission_id == "m2"

    def test_gps_fix_quality_mapping(self):
        adapter = self._setup_adapter()
        proc = TelemetryStreamProcessor(adapter)
        proc.register_drone(1)
        frame = proc.read_frame(1)
        assert frame.gps_fix_quality == GPSFixQuality.NO_FIX

    def test_build_fleet_snapshot(self):
        adapter = self._setup_adapter(num_drones=4)
        proc = TelemetryStreamProcessor(adapter)
        for i in range(1, 5):
            proc.register_drone(i)

        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        adapter.arm(2)
        adapter.send_command(CommandSchema(
            command_id="takeoff-2", drone_id=2,
            command_type=CommandType.TAKEOFF,
        ))
        adapter.send_command(CommandSchema(
            command_id="estop-3", drone_id=3,
            command_type=CommandType.EMERGENCY_STOP,
        ))

        snap = proc.build_fleet_snapshot()
        assert snap.total_drones == 4
        assert snap.active_drones == 2
        assert snap.idle_drones == 1
        assert snap.faulty_drones == 1
        assert len(snap.frames) == 4

    def test_disconnected_drone_excluded(self):
        adapter = self._setup_adapter(num_drones=2)
        proc = TelemetryStreamProcessor(adapter)
        proc.register_drone(1)
        proc.register_drone(2)
        adapter.set_connected(2, False)
        frames = proc.read_all_frames()
        assert len(frames) == 1
        assert frames[0].drone_id == 1

    def test_all_flight_states_mapped(self):
        """Every FlightState has a corresponding TaskState."""
        for fs in FlightState:
            assert fs in FLIGHT_STATE_TO_TASK

    def test_velocity_computed_from_speed_heading(self):
        adapter = self._setup_adapter()
        proc = TelemetryStreamProcessor(adapter)
        proc.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        adapter.send_command(CommandSchema(
            command_id="goto-1", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0, "speed_m_s": 10.0},
        ))
        frame = proc.read_frame(1)
        assert frame.velocity.vx != 0.0 or frame.velocity.vy != 0.0


# =========================================================================
# Telemetry Compliance Tests
# =========================================================================

class TestTelemetryCompliance:
    """Verify no decision-making in telemetry module."""

    def test_no_forbidden_methods(self):
        forbidden = [
            "select_best", "optimize", "rank", "score",
            "balance", "schedule", "plan_mission", "infer",
            "predict", "recommend",
        ]
        with open("core/hal_telemetry.py", "r") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                for pattern in forbidden:
                    assert pattern not in name, (
                        f"Forbidden pattern '{pattern}' in hal_telemetry.py — {node.name}"
                    )

    def test_no_hive_imports(self):
        with open("core/hal_telemetry.py", "r") as f:
            source = f.read()
        assert "from core.hive" not in source
        assert "from core.mission_orchestrator" not in source
        assert "from core.fleet_manager" not in source
        assert "from core.resource_system" not in source
        assert "from core.hive_integration" not in source

    def test_no_storage_layer(self):
        """Telemetry has no persistent storage."""
        with open("core/hal_telemetry.py", "r") as f:
            source = f.read()
        assert "sqlite" not in source.lower()
        assert "database" not in source.lower()
        assert "write_to_disk" not in source.lower()
        assert "save_to_file" not in source.lower()
