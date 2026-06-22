"""
Phase 9.1 — Core HAL Interfaces Tests.

Tests for hardware-agnostic contracts: CommandSchema, TelemetrySchema,
ExecutionResult, HALError, and BaseDroneInterface contract.
"""

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


# =========================================================================
# CommandSchema Tests
# =========================================================================

class TestCommandSchema:
    """Verify standardized command format."""

    def test_create_basic_command(self):
        cmd = CommandSchema(
            command_id="cmd-001",
            drone_id=1,
            command_type=CommandType.ARM,
        )
        assert cmd.command_id == "cmd-001"
        assert cmd.drone_id == 1
        assert cmd.command_type == CommandType.ARM
        assert cmd.params == {}
        assert cmd.mission_id is None
        assert cmd.sequence == 0

    def test_create_command_with_params(self):
        cmd = CommandSchema(
            command_id="cmd-002",
            drone_id=2,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0, "altitude_m": 25.0},
            mission_id="m1",
            sequence=5,
        )
        assert cmd.params["latitude"] == 40.0
        assert cmd.mission_id == "m1"
        assert cmd.sequence == 5

    def test_empty_command_id_rejected(self):
        with pytest.raises(ValueError, match="command_id"):
            CommandSchema(
                command_id="",
                drone_id=1,
                command_type=CommandType.ARM,
            )

    def test_negative_drone_id_rejected(self):
        with pytest.raises(ValueError, match="drone_id"):
            CommandSchema(
                command_id="cmd-003",
                drone_id=-1,
                command_type=CommandType.ARM,
            )

    def test_all_command_types_exist(self):
        expected = {
            "arm", "disarm", "takeoff", "land", "goto",
            "return_to_home", "set_speed", "spray_start",
            "spray_stop", "emergency_stop",
        }
        actual = {ct.value for ct in CommandType}
        assert actual == expected


# =========================================================================
# TelemetrySchema Tests
# =========================================================================

class TestTelemetrySchema:
    """Verify standardized telemetry format."""

    def test_create_minimal_telemetry(self):
        t = TelemetrySchema(
            drone_id=1,
            timestamp_ms=1000,
            flight_state=FlightState.GROUNDED,
        )
        assert t.drone_id == 1
        assert t.flight_state == FlightState.GROUNDED
        assert t.position is None
        assert t.battery_pct is None
        assert t.is_connected is True
        assert t.raw_data == {}

    def test_create_full_telemetry(self):
        pos = GPSPosition(latitude=40.416, longitude=-3.703, altitude_m=15.0)
        t = TelemetrySchema(
            drone_id=2,
            timestamp_ms=5000,
            flight_state=FlightState.IN_FLIGHT,
            position=pos,
            battery_pct=85.0,
            speed_m_s=5.5,
            heading_deg=270.0,
            ground_altitude_m=15.0,
            satellite_count=12,
            signal_strength_pct=95.0,
        )
        assert t.position.latitude == 40.416
        assert t.battery_pct == 85.0
        assert t.speed_m_s == 5.5
        assert t.satellite_count == 12

    def test_all_flight_states_exist(self):
        expected = {
            "grounded", "arming", "armed", "taking_off",
            "in_flight", "landing", "returning", "emergency", "unknown",
        }
        actual = {fs.value for fs in FlightState}
        assert actual == expected


# =========================================================================
# ExecutionResult Tests
# =========================================================================

class TestExecutionResult:
    """Verify command execution outcome model."""

    def test_success_result(self):
        r = ExecutionResult(
            command_id="cmd-001",
            drone_id=1,
            status=ExecutionStatus.SUCCESS,
            message="ARM executed",
        )
        assert r.status == ExecutionStatus.SUCCESS
        assert r.error is None

    def test_failed_result_with_error(self):
        err = HALError(
            code=HALErrorCode.COMMUNICATION_FAILURE,
            message="Connection lost",
            drone_id=1,
        )
        r = ExecutionResult(
            command_id="cmd-002",
            drone_id=1,
            status=ExecutionStatus.FAILED,
            message="Connection lost",
            error=err,
        )
        assert r.status == ExecutionStatus.FAILED
        assert r.error.code == HALErrorCode.COMMUNICATION_FAILURE

    def test_safety_override_result(self):
        r = ExecutionResult(
            command_id="cmd-003",
            drone_id=1,
            status=ExecutionStatus.SAFETY_OVERRIDE,
            message="Geofence violation detected",
        )
        assert r.status == ExecutionStatus.SAFETY_OVERRIDE

    def test_all_execution_statuses_exist(self):
        expected = {"success", "failed", "timeout", "rejected", "safety_override"}
        actual = {es.value for es in ExecutionStatus}
        assert actual == expected


# =========================================================================
# HALError Tests
# =========================================================================

class TestHALError:
    """Verify hardware-agnostic error model."""

    def test_create_error(self):
        err = HALError(
            code=HALErrorCode.HARDWARE_FAULT,
            message="Motor failure detected",
            drone_id=3,
            recoverable=False,
        )
        assert err.code == HALErrorCode.HARDWARE_FAULT
        assert err.recoverable is False
        assert err.drone_id == 3

    def test_recoverable_error(self):
        err = HALError(
            code=HALErrorCode.TIMEOUT,
            message="Command timeout",
            recoverable=True,
        )
        assert err.recoverable is True

    def test_all_error_codes_exist(self):
        expected = {
            "communication_failure", "command_rejected", "timeout",
            "invalid_state", "hardware_fault", "geofence_violation",
            "emergency_triggered", "adapter_error", "unknown",
        }
        actual = {ec.value for ec in HALErrorCode}
        assert actual == expected


# =========================================================================
# BaseDroneInterface Contract Tests
# =========================================================================

class TestBaseDroneInterfaceContract:
    """Verify the interface contract cannot be directly instantiated."""

    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            BaseDroneInterface()

    def test_required_methods(self):
        required = {
            "send_command", "get_telemetry", "arm", "disarm",
            "return_to_home", "is_connected", "get_adapter_name",
        }
        actual = set()
        for name in dir(BaseDroneInterface):
            if not name.startswith("_"):
                actual.add(name)
        assert required.issubset(actual)


# =========================================================================
# GPSPosition Tests
# =========================================================================

class TestGPSPosition:
    """Verify GPS position data structure."""

    def test_create_position(self):
        pos = GPSPosition(latitude=40.416, longitude=-3.703, altitude_m=15.0)
        assert pos.latitude == 40.416
        assert pos.longitude == -3.703
        assert pos.altitude_m == 15.0

    def test_zero_position(self):
        pos = GPSPosition(latitude=0.0, longitude=0.0, altitude_m=0.0)
        assert pos.latitude == 0.0
