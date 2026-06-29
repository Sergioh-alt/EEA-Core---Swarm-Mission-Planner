"""
Phase 9.5 — HAL Architecture Validation Tests.

Validates architectural contracts across all HAL components:
- Interface contract consistency
- Adapter consistency
- Telemetry contract consistency
- Safety contract consistency
- Deterministic behavior
- Adapter independence
- Protocol abstraction integrity
- Backward compatibility

NO new functionality — validation only.
"""

import ast

import pytest

from core.hal_interfaces import (
    BaseDroneInterface,
    CommandSchema,
    CommandType,
    ExecutionResult,
    ExecutionStatus,
    FlightState,
    GPSPosition,
    HALError,
    HALErrorCode,
    TelemetrySchema,
)
from core.hal_adapters import (
    ArduPilotAdapter,
    PX4Adapter,
    SimulationAdapter,
)
from core.hal_telemetry import (
    DroneTelemetryFrame,
    FleetTelemetrySnapshot,
    GPSFixQuality,
    TaskState,
    TelemetryStreamProcessor,
    Velocity3D,
    FLIGHT_STATE_TO_TASK,
)
from core.hal_safety import (
    EmergencySignalHandler,
    EmergencyType,
    FailSafeState,
    FailSafeStateMapper,
    SafetyCommandRelay,
    SafetyCommandResult,
)


# =========================================================================
# Interface Contract Consistency
# =========================================================================

class TestInterfaceContractConsistency:
    """Verify BaseDroneInterface contract is complete and consistent."""

    REQUIRED_METHODS = {
        "send_command", "get_telemetry", "arm", "disarm",
        "return_to_home", "is_connected", "get_adapter_name",
    }

    def test_interface_has_all_required_methods(self):
        actual = {
            name for name in dir(BaseDroneInterface)
            if not name.startswith("_")
        }
        assert self.REQUIRED_METHODS.issubset(actual)

    def test_all_methods_are_abstract(self):
        abstract = getattr(BaseDroneInterface, "__abstractmethods__", set())
        assert self.REQUIRED_METHODS.issubset(abstract)

    def test_command_type_enum_complete(self):
        expected = {
            "arm", "disarm", "takeoff", "land", "goto",
            "return_to_home", "set_speed", "spray_start",
            "spray_stop", "emergency_stop",
        }
        actual = {ct.value for ct in CommandType}
        assert actual == expected

    def test_flight_state_enum_complete(self):
        expected = {
            "grounded", "arming", "armed", "taking_off",
            "in_flight", "landing", "returning", "emergency", "unknown",
        }
        actual = {fs.value for fs in FlightState}
        assert actual == expected

    def test_execution_status_enum_complete(self):
        expected = {"success", "failed", "timeout", "rejected", "safety_override"}
        actual = {es.value for es in ExecutionStatus}
        assert actual == expected

    def test_hal_error_code_enum_complete(self):
        expected = {
            "communication_failure", "command_rejected", "timeout",
            "invalid_state", "hardware_fault", "geofence_violation",
            "emergency_triggered", "adapter_error", "unknown",
        }
        actual = {ec.value for ec in HALErrorCode}
        assert actual == expected

    def test_command_schema_validation(self):
        with pytest.raises(ValueError):
            CommandSchema(command_id="", drone_id=1, command_type=CommandType.ARM)
        with pytest.raises(ValueError):
            CommandSchema(command_id="c1", drone_id=-1, command_type=CommandType.ARM)


# =========================================================================
# Adapter Consistency
# =========================================================================

class TestAdapterConsistency:
    """Verify all adapters behave consistently for same commands."""

    ADAPTER_CLASSES = [SimulationAdapter, PX4Adapter, ArduPilotAdapter]

    def test_all_adapters_subclass_interface(self):
        for cls in self.ADAPTER_CLASSES:
            assert issubclass(cls, BaseDroneInterface), (
                f"{cls.__name__} does not subclass BaseDroneInterface"
            )

    def test_all_adapters_have_register_drone(self):
        for cls in self.ADAPTER_CLASSES:
            assert hasattr(cls, "register_drone")

    def test_all_adapters_accept_all_command_types(self):
        for cls in self.ADAPTER_CLASSES:
            adapter = cls()
            adapter.register_drone(1)
            for ct in CommandType:
                cmd = CommandSchema(
                    command_id=f"test-{ct.value}",
                    drone_id=1,
                    command_type=ct,
                )
                result = adapter.send_command(cmd)
                assert isinstance(result, ExecutionResult)

    def test_unregistered_drone_fails_all_adapters(self):
        for cls in self.ADAPTER_CLASSES:
            adapter = cls()
            result = adapter.send_command(CommandSchema(
                command_id="test", drone_id=99,
                command_type=CommandType.ARM,
            ))
            assert result.status == ExecutionStatus.FAILED

    def test_adapter_names_unique(self):
        names = set()
        for cls in self.ADAPTER_CLASSES:
            adapter = cls()
            name = adapter.get_adapter_name()
            assert name not in names, f"Duplicate adapter name: {name}"
            names.add(name)

    def test_get_telemetry_returns_schema(self):
        for cls in self.ADAPTER_CLASSES:
            adapter = cls()
            adapter.register_drone(1)
            t = adapter.get_telemetry(1)
            assert isinstance(t, TelemetrySchema)

    def test_all_adapters_have_complete_command_maps(self):
        assert set(PX4Adapter.PX4_COMMAND_MAP.keys()) == set(CommandType)
        assert set(ArduPilotAdapter.ARDUPILOT_MODE_MAP.keys()) == set(CommandType)


# =========================================================================
# Telemetry Contract Consistency
# =========================================================================

class TestTelemetryContractConsistency:
    """Verify telemetry contracts are complete and consistent."""

    def test_drone_telemetry_frame_fields(self):
        required = {
            "drone_id", "position", "velocity", "heading_deg",
            "battery_level_pct", "power_draw_w", "mission_id",
            "task_state", "gps_fix_quality", "signal_strength_pct",
            "timestamp_ms",
        }
        actual = {f.name for f in DroneTelemetryFrame.__dataclass_fields__.values()}
        assert required.issubset(actual)

    def test_fleet_snapshot_fields(self):
        required = {
            "total_drones", "active_drones", "idle_drones",
            "charging_drones", "faulty_drones", "global_timestamp_ms",
        }
        actual = {f.name for f in FleetTelemetrySnapshot.__dataclass_fields__.values()}
        assert required.issubset(actual)

    def test_task_state_enum_complete(self):
        expected = {"idle", "en_route", "working", "returning", "emergency", "landed"}
        actual = {ts.value for ts in TaskState}
        assert actual == expected

    def test_gps_fix_quality_enum_complete(self):
        expected = {"no_fix", "2d", "3d", "dgps", "rtk_float", "rtk_fixed"}
        actual = {q.value for q in GPSFixQuality}
        assert actual == expected

    def test_flight_state_to_task_mapping_complete(self):
        for fs in FlightState:
            assert fs in FLIGHT_STATE_TO_TASK, (
                f"FlightState.{fs.name} not mapped to TaskState"
            )

    def test_gps_quality_derivation_deterministic(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        proc = TelemetryStreamProcessor(adapter)
        proc.register_drone(1)
        f1 = proc.read_frame(1)
        f2 = proc.read_frame(1)
        assert f1.gps_fix_quality == f2.gps_fix_quality


# =========================================================================
# Safety Contract Consistency
# =========================================================================

class TestSafetyContractConsistency:
    """Verify safety contracts are complete and consistent."""

    def test_emergency_type_enum_complete(self):
        expected = {
            "emergency_stop", "communication_loss",
            "low_battery_critical", "hardware_fault",
            "geofence_breach", "gps_loss",
        }
        actual = {et.value for et in EmergencyType}
        assert actual == expected

    def test_fail_safe_state_enum_complete(self):
        expected = {"kill", "return_to_home", "land_in_place", "hover", "disarm"}
        actual = {fs.value for fs in FailSafeState}
        assert actual == expected

    def test_all_fail_safes_have_command_mapping(self):
        mapper = FailSafeStateMapper()
        for fs in FailSafeState:
            cmd = mapper.map_to_command(1, fs, f"test-{fs.value}")
            assert isinstance(cmd, CommandSchema)
            assert cmd.command_type in CommandType

    def test_safety_relay_produces_result(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        relay = SafetyCommandRelay(adapter)
        result = relay.emergency_stop(1)
        assert isinstance(result, SafetyCommandResult)
        assert isinstance(result.execution_result, ExecutionResult)


# =========================================================================
# Deterministic Behavior Validation
# =========================================================================

class TestDeterministicBehavior:
    """Verify all HAL operations produce deterministic outputs."""

    def test_adapter_same_command_same_result(self):
        a1 = SimulationAdapter()
        a1.register_drone(1)
        a2 = SimulationAdapter()
        a2.register_drone(1)

        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        r1 = a1.send_command(cmd)
        r2 = a2.send_command(cmd)
        assert r1.status == r2.status

    def test_telemetry_normalization_deterministic(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        proc = TelemetryStreamProcessor(adapter)
        proc.register_drone(1)

        f1 = proc.read_frame(1)
        f2 = proc.read_frame(1)
        assert f1.task_state == f2.task_state
        assert f1.battery_level_pct == f2.battery_level_pct
        assert f1.position.latitude == f2.position.latitude

    def test_safety_mapping_deterministic(self):
        mapper = FailSafeStateMapper()
        for fs in FailSafeState:
            cmd1 = mapper.map_to_command(1, fs, "test")
            cmd2 = mapper.map_to_command(1, fs, "test")
            assert cmd1.command_type == cmd2.command_type
            assert cmd1.params == cmd2.params

    def test_emergency_detection_deterministic(self):
        handler = EmergencySignalHandler()
        telemetry = TelemetrySchema(
            drone_id=1, timestamp_ms=1000,
            flight_state=FlightState.IN_FLIGHT,
            battery_pct=3.0, is_connected=False,
        )
        s1 = handler.check_telemetry(telemetry)
        h2 = EmergencySignalHandler()
        s2 = h2.check_telemetry(telemetry)
        types1 = {s.emergency_type for s in s1}
        types2 = {s.emergency_type for s in s2}
        assert types1 == types2

    def test_px4_translation_deterministic(self):
        a1 = PX4Adapter()
        a1.register_drone(1)
        a2 = PX4Adapter()
        a2.register_drone(1)
        cmd = CommandSchema(
            command_id="goto-1", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0},
        )
        a1.send_command(cmd)
        a2.send_command(cmd)
        assert a1.translated_commands[0] == a2.translated_commands[0]

    def test_ardupilot_translation_deterministic(self):
        a1 = ArduPilotAdapter()
        a1.register_drone(1)
        a2 = ArduPilotAdapter()
        a2.register_drone(1)
        cmd = CommandSchema(
            command_id="goto-1", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0},
        )
        a1.send_command(cmd)
        a2.send_command(cmd)
        assert a1.translated_commands[0] == a2.translated_commands[0]


# =========================================================================
# Adapter Independence
# =========================================================================

class TestAdapterIndependence:
    """Verify adapters are independent and swappable."""

    def test_adapters_share_no_state(self):
        sim = SimulationAdapter()
        sim.register_drone(1)
        sim.arm(1)

        px4 = PX4Adapter()
        px4.register_drone(1)
        assert not px4.translated_commands

    def test_multi_adapter_concurrent_use(self):
        sim = SimulationAdapter()
        sim.register_drone(1)
        px4 = PX4Adapter()
        px4.register_drone(1)
        ardu = ArduPilotAdapter()
        ardu.register_drone(1)

        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        r_sim = sim.send_command(cmd)
        r_px4 = px4.send_command(cmd)
        r_ardu = ardu.send_command(cmd)

        assert r_sim.status == ExecutionStatus.SUCCESS
        assert r_px4.status == ExecutionStatus.SUCCESS
        assert r_ardu.status == ExecutionStatus.SUCCESS

    def test_telemetry_works_with_any_adapter(self):
        for adapter_cls in [SimulationAdapter, PX4Adapter, ArduPilotAdapter]:
            adapter = adapter_cls()
            adapter.register_drone(1)
            proc = TelemetryStreamProcessor(adapter)
            proc.register_drone(1)
            frame = proc.read_frame(1)
            assert isinstance(frame, DroneTelemetryFrame)

    def test_safety_works_with_any_adapter(self):
        for adapter_cls in [SimulationAdapter, PX4Adapter, ArduPilotAdapter]:
            adapter = adapter_cls()
            adapter.register_drone(1)
            relay = SafetyCommandRelay(adapter)
            result = relay.emergency_stop(1)
            assert isinstance(result, SafetyCommandResult)


# =========================================================================
# Protocol Abstraction Integrity
# =========================================================================

class TestProtocolAbstractionIntegrity:
    """Verify protocol abstraction hides hardware details."""

    def test_px4_produces_mavlink_commands(self):
        adapter = PX4Adapter()
        adapter.register_drone(1)
        adapter.send_command(CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        ))
        cmd = adapter.translated_commands[0]
        assert "mavlink_command" in cmd
        assert cmd["mavlink_command"].startswith("MAV_CMD_")

    def test_ardupilot_produces_mode_commands(self):
        adapter = ArduPilotAdapter()
        adapter.register_drone(1)
        adapter.send_command(CommandSchema(
            command_id="rth-1", drone_id=1,
            command_type=CommandType.RETURN_TO_HOME,
        ))
        cmd = adapter.translated_commands[0]
        assert "mode" in cmd
        assert cmd["mode"] == "RTL"

    def test_simulation_maintains_state_model(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        t = adapter.get_telemetry(1)
        assert t.flight_state == FlightState.ARMED

    def test_hive_output_consumable_by_hal(self):
        """Hive mission output can be translated to HAL commands."""
        from core.hive_integration import HiveController

        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=30.0, crop_type="corn", num_drones=3)
        result = ctrl.execute_next()
        assert result.success

        adapter = SimulationAdapter()
        for i in range(1, 4):
            adapter.register_drone(i)

        for route in result.context.routes.routes:
            arm_r = adapter.arm(route.drone_id)
            assert arm_r.status == ExecutionStatus.SUCCESS


# =========================================================================
# Backward Compatibility
# =========================================================================

class TestBackwardCompatibility:
    """Verify Phase 9.5 introduces no regressions."""

    def test_pipeline_unchanged(self):
        """Base planning pipeline produces same output."""
        from core.hive_integration import HiveController

        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        result = ctrl.execute_next()
        assert result.success
        assert result.context.routes is not None
        assert len(result.context.routes.routes) > 0

    def test_existing_hal_interfaces_unchanged(self):
        """All interface types still exist and are importable."""
        from core.hal_interfaces import (
            BaseDroneInterface,
            CommandSchema,
            CommandType,
            ExecutionResult,
            ExecutionStatus,
            FlightState,
            GPSPosition,
            HALError,
            HALErrorCode,
            TelemetrySchema,
        )
        assert BaseDroneInterface is not None
        assert len(CommandType) == 10
        assert len(FlightState) == 9

    def test_existing_adapters_unchanged(self):
        from core.hal_adapters import (
            ArduPilotAdapter,
            PX4Adapter,
            SimulationAdapter,
        )
        assert SimulationAdapter().get_adapter_name() == "SimulationAdapter"
        assert PX4Adapter().get_adapter_name() == "PX4Adapter"
        assert ArduPilotAdapter().get_adapter_name() == "ArduPilotAdapter"

    def test_existing_telemetry_unchanged(self):
        from core.hal_telemetry import (
            DroneTelemetryFrame,
            FleetTelemetrySnapshot,
            TelemetryStreamProcessor,
            TaskState,
            GPSFixQuality,
        )
        assert len(TaskState) == 6
        assert len(GPSFixQuality) == 6

    def test_existing_safety_unchanged(self):
        from core.hal_safety import (
            EmergencySignalHandler,
            EmergencyType,
            FailSafeState,
            FailSafeStateMapper,
            SafetyCommandRelay,
        )
        assert len(EmergencyType) == 6
        assert len(FailSafeState) == 5
