"""
Phase 9.4 — Safety & Emergency Layer Tests.

Tests for EmergencySignalHandler, FailSafeStateMapper,
SafetyCommandRelay, and safety boundary compliance.
"""

import ast

from core.hal_interfaces import (
    CommandType,
    ExecutionStatus,
    FlightState,
    TelemetrySchema,
)
from core.hal_adapters import SimulationAdapter, CommandSchema
from core.hal_safety import (
    EmergencySignal,
    EmergencySignalHandler,
    EmergencyType,
    FailSafeState,
    FailSafeStateMapper,
    SafetyCommandRelay,
)


# =========================================================================
# FailSafeStateMapper Tests
# =========================================================================

class TestFailSafeStateMapper:
    """Verify fail-safe to hardware command mapping."""

    def test_kill_maps_to_emergency_stop(self):
        mapper = FailSafeStateMapper()
        cmd = mapper.map_to_command(1, FailSafeState.KILL, "safety-kill-1")
        assert cmd.command_type == CommandType.EMERGENCY_STOP
        assert cmd.drone_id == 1

    def test_rth_maps_to_return_to_home(self):
        mapper = FailSafeStateMapper()
        cmd = mapper.map_to_command(1, FailSafeState.RETURN_TO_HOME, "safety-rth-1")
        assert cmd.command_type == CommandType.RETURN_TO_HOME

    def test_land_maps_to_land(self):
        mapper = FailSafeStateMapper()
        cmd = mapper.map_to_command(1, FailSafeState.LAND_IN_PLACE, "safety-land-1")
        assert cmd.command_type == CommandType.LAND

    def test_hover_maps_to_set_speed_zero(self):
        mapper = FailSafeStateMapper()
        cmd = mapper.map_to_command(1, FailSafeState.HOVER, "safety-hover-1")
        assert cmd.command_type == CommandType.SET_SPEED
        assert cmd.params["speed_m_s"] == 0.0

    def test_disarm_maps_to_disarm(self):
        mapper = FailSafeStateMapper()
        cmd = mapper.map_to_command(1, FailSafeState.DISARM, "safety-disarm-1")
        assert cmd.command_type == CommandType.DISARM

    def test_all_fail_safe_states_mapped(self):
        mapper = FailSafeStateMapper()
        for fs in FailSafeState:
            cmd = mapper.map_to_command(1, fs, f"test-{fs.value}")
            assert cmd.command_type is not None


# =========================================================================
# EmergencySignalHandler Tests
# =========================================================================

class TestEmergencySignalHandler:
    """Verify emergency signal detection."""

    def test_detect_communication_loss(self):
        handler = EmergencySignalHandler()
        telemetry = TelemetrySchema(
            drone_id=1, timestamp_ms=1000,
            flight_state=FlightState.IN_FLIGHT,
            is_connected=False,
        )
        signals = handler.check_telemetry(telemetry)
        assert len(signals) >= 1
        types = {s.emergency_type for s in signals}
        assert EmergencyType.COMMUNICATION_LOSS in types

    def test_detect_low_battery(self):
        handler = EmergencySignalHandler(low_battery_threshold_pct=15.0)
        telemetry = TelemetrySchema(
            drone_id=1, timestamp_ms=1000,
            flight_state=FlightState.IN_FLIGHT,
            battery_pct=5.0,
        )
        signals = handler.check_telemetry(telemetry)
        types = {s.emergency_type for s in signals}
        assert EmergencyType.LOW_BATTERY_CRITICAL in types

    def test_detect_gps_loss(self):
        handler = EmergencySignalHandler(signal_loss_threshold_pct=10.0)
        telemetry = TelemetrySchema(
            drone_id=1, timestamp_ms=1000,
            flight_state=FlightState.IN_FLIGHT,
            signal_strength_pct=2.0,
        )
        signals = handler.check_telemetry(telemetry)
        types = {s.emergency_type for s in signals}
        assert EmergencyType.GPS_LOSS in types

    def test_no_signal_on_healthy_telemetry(self):
        handler = EmergencySignalHandler()
        telemetry = TelemetrySchema(
            drone_id=1, timestamp_ms=1000,
            flight_state=FlightState.IN_FLIGHT,
            battery_pct=80.0,
            signal_strength_pct=90.0,
            is_connected=True,
        )
        signals = handler.check_telemetry(telemetry)
        assert len(signals) == 0

    def test_multiple_signals_detected(self):
        handler = EmergencySignalHandler()
        telemetry = TelemetrySchema(
            drone_id=1, timestamp_ms=1000,
            flight_state=FlightState.IN_FLIGHT,
            battery_pct=3.0,
            signal_strength_pct=1.0,
            is_connected=False,
        )
        signals = handler.check_telemetry(telemetry)
        assert len(signals) == 3

    def test_create_manual_signal(self):
        handler = EmergencySignalHandler()
        sig = handler.create_signal(
            drone_id=1,
            emergency_type=EmergencyType.HARDWARE_FAULT,
            timestamp_ms=5000,
            message="Motor 3 failure",
        )
        assert sig.emergency_type == EmergencyType.HARDWARE_FAULT
        assert sig.drone_id == 1
        assert len(handler.signal_log) == 1

    def test_signal_log_accumulates(self):
        handler = EmergencySignalHandler()
        t1 = TelemetrySchema(
            drone_id=1, timestamp_ms=1000,
            flight_state=FlightState.IN_FLIGHT,
            is_connected=False,
        )
        t2 = TelemetrySchema(
            drone_id=2, timestamp_ms=2000,
            flight_state=FlightState.IN_FLIGHT,
            battery_pct=5.0,
        )
        handler.check_telemetry(t1)
        handler.check_telemetry(t2)
        assert len(handler.signal_log) == 2

    def test_configurable_thresholds(self):
        handler = EmergencySignalHandler(low_battery_threshold_pct=50.0)
        telemetry = TelemetrySchema(
            drone_id=1, timestamp_ms=1000,
            flight_state=FlightState.IN_FLIGHT,
            battery_pct=40.0,
        )
        signals = handler.check_telemetry(telemetry)
        types = {s.emergency_type for s in signals}
        assert EmergencyType.LOW_BATTERY_CRITICAL in types

    def test_all_emergency_types_exist(self):
        expected = {
            "emergency_stop", "communication_loss",
            "low_battery_critical", "hardware_fault",
            "geofence_breach", "gps_loss",
        }
        actual = {et.value for et in EmergencyType}
        assert actual == expected


# =========================================================================
# SafetyCommandRelay Tests
# =========================================================================

class TestSafetyCommandRelay:
    """Verify safety command relay to hardware."""

    def _setup(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        relay = SafetyCommandRelay(adapter)
        return adapter, relay

    def test_emergency_stop_relay(self):
        adapter, relay = self._setup()
        result = relay.emergency_stop(1)
        assert result.execution_result.status == ExecutionStatus.SUCCESS
        assert result.fail_safe_state == FailSafeState.KILL
        t = adapter.get_telemetry(1)
        assert t.flight_state == FlightState.EMERGENCY

    def test_return_to_home_relay(self):
        adapter, relay = self._setup()
        result = relay.return_to_home(1)
        assert result.execution_result.status == ExecutionStatus.SUCCESS
        assert result.fail_safe_state == FailSafeState.RETURN_TO_HOME
        t = adapter.get_telemetry(1)
        assert t.flight_state == FlightState.RETURNING

    def test_land_in_place_relay(self):
        adapter, relay = self._setup()
        result = relay.land_in_place(1)
        assert result.execution_result.status == ExecutionStatus.SUCCESS
        assert result.fail_safe_state == FailSafeState.LAND_IN_PLACE
        t = adapter.get_telemetry(1)
        assert t.flight_state == FlightState.GROUNDED

    def test_relay_with_signal(self):
        adapter, relay = self._setup()
        sig = EmergencySignal(
            drone_id=1,
            emergency_type=EmergencyType.LOW_BATTERY_CRITICAL,
            timestamp_ms=5000,
            message="Battery at 5%",
        )
        result = relay.relay_fail_safe(1, FailSafeState.LAND_IN_PLACE, signal=sig)
        assert result.signal.emergency_type == EmergencyType.LOW_BATTERY_CRITICAL

    def test_relay_log_records(self):
        _, relay = self._setup()
        relay.emergency_stop(1)
        assert len(relay.relay_log) == 1

    def test_relay_to_grounded_drone_rejected(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        relay = SafetyCommandRelay(adapter)
        result = relay.land_in_place(1)
        assert result.execution_result.status == ExecutionStatus.REJECTED


# =========================================================================
# End-to-End Safety Flow Tests
# =========================================================================

class TestSafetyEndToEnd:
    """Verify complete detection → relay flow."""

    def test_detect_and_relay_low_battery(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        adapter.set_battery(1, 5.0)

        handler = EmergencySignalHandler()
        relay = SafetyCommandRelay(adapter)

        telemetry = adapter.get_telemetry(1)
        signals = handler.check_telemetry(telemetry)
        assert len(signals) >= 1

        for sig in signals:
            if sig.emergency_type == EmergencyType.LOW_BATTERY_CRITICAL:
                result = relay.relay_fail_safe(
                    1, FailSafeState.LAND_IN_PLACE, signal=sig,
                )
                assert result.execution_result.status == ExecutionStatus.SUCCESS
                break

    def test_detect_and_relay_comm_loss(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))

        handler = EmergencySignalHandler()

        disconnected_telemetry = TelemetrySchema(
            drone_id=1, timestamp_ms=5000,
            flight_state=FlightState.IN_FLIGHT,
            is_connected=False,
        )
        signals = handler.check_telemetry(disconnected_telemetry)
        assert any(s.emergency_type == EmergencyType.COMMUNICATION_LOSS for s in signals)

    def test_multi_drone_independent_safety(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.register_drone(2)
        adapter.arm(1)
        adapter.arm(2)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        adapter.send_command(CommandSchema(
            command_id="takeoff-2", drone_id=2,
            command_type=CommandType.TAKEOFF,
        ))

        relay = SafetyCommandRelay(adapter)
        relay.emergency_stop(1)

        t1 = adapter.get_telemetry(1)
        t2 = adapter.get_telemetry(2)
        assert t1.flight_state == FlightState.EMERGENCY
        assert t2.flight_state == FlightState.IN_FLIGHT


# =========================================================================
# Safety Compliance Tests
# =========================================================================

class TestSafetyCompliance:
    """Verify no autonomous decision-making in safety module."""

    def test_no_forbidden_methods(self):
        forbidden = [
            "select_best", "optimize", "rank", "score",
            "balance", "schedule", "plan_mission", "infer",
            "predict", "recommend", "abort_mission",
            "fleet_level_safety",
        ]
        with open("core/hal_safety.py", "r") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                for pattern in forbidden:
                    assert pattern not in name, (
                        f"Forbidden pattern '{pattern}' in hal_safety.py — {node.name}"
                    )

    def test_no_hive_imports(self):
        with open("core/hal_safety.py", "r") as f:
            source = f.read()
        assert "from core.hive" not in source
        assert "from core.mission_orchestrator" not in source
        assert "from core.fleet_manager" not in source
        assert "from core.resource_system" not in source
        assert "from core.hive_integration" not in source

    def test_no_ml_or_random(self):
        with open("core/hal_safety.py", "r") as f:
            source = f.read()
        assert "import random" not in source
        assert "import numpy" not in source
        assert "sklearn" not in source

    def test_no_mission_abort_logic(self):
        """Safety module does not abort missions — that's Hive's job."""
        with open("core/hal_safety.py", "r") as f:
            source = f.read()
        assert "abort_mission" not in source
        assert "cancel_mission" not in source
        assert "stop_mission" not in source
