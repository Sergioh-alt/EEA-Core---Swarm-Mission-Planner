"""
Phase 10A — MAVLink Bridge Layer.

Translates CommandSchema into MAVLink v2 command envelopes and
manages the ACK/NACK/timeout/retry protocol.

Architecture rules:
- Only entry point for MAVLink commands is CommandSchema
- ACK required for every command
- NACK handling with configurable retry (max 3)
- Timeout of 3000ms per attempt
- NO decision-making — pure command translation and execution
- NO Hive imports
- NO planning imports
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.hal_interfaces import (
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

logger = logging.getLogger("eea.mavlink_bridge")


# =========================================================================
# MAVLink Command Envelope
# =========================================================================

class MAVLinkACKStatus(Enum):
    """ACK status from MAVLink command execution."""
    ACK = "ACK"
    NACK = "NACK"
    TIMEOUT = "TIMEOUT"
    IN_PROGRESS = "IN_PROGRESS"


@dataclass(frozen=True)
class MAVLinkCommandEnvelope:
    """
    MAVLink v2 command envelope.

    Encapsulates a translated command ready for MAVLink transmission.
    This is a data structure — no logic.
    """
    command_id: str
    drone_id: int
    mavlink_command: str
    target_system: int
    target_component: int = 1
    params: dict = field(default_factory=dict)
    ack_required: bool = True
    timeout_ms: int = 3000
    priority: str = "NORMAL"


@dataclass
class MAVLinkACKResult:
    """
    Result of a MAVLink command execution with ACK status.
    """
    command_id: str
    drone_id: int
    status: MAVLinkACKStatus
    mavlink_command: str
    attempts: int = 1
    error_message: Optional[str] = None
    timestamp_ms: int = 0


# =========================================================================
# MAVLink Command Translation (Pure)
# =========================================================================

# PX4 MAVLink v2 command mapping — deterministic 1:1 translation
MAVLINK_COMMAND_MAP: dict[CommandType, str] = {
    CommandType.ARM: "MAV_CMD_COMPONENT_ARM_DISARM",
    CommandType.DISARM: "MAV_CMD_COMPONENT_ARM_DISARM",
    CommandType.TAKEOFF: "MAV_CMD_NAV_TAKEOFF",
    CommandType.LAND: "MAV_CMD_NAV_LAND",
    CommandType.GOTO: "MAV_CMD_NAV_WAYPOINT",
    CommandType.RETURN_TO_HOME: "MAV_CMD_NAV_RETURN_TO_LAUNCH",
    CommandType.SET_SPEED: "MAV_CMD_DO_CHANGE_SPEED",
    CommandType.SPRAY_START: "MAV_CMD_DO_SET_ACTUATOR",
    CommandType.SPRAY_STOP: "MAV_CMD_DO_SET_ACTUATOR",
    CommandType.EMERGENCY_STOP: "MAV_CMD_COMPONENT_ARM_DISARM",
}


def translate_to_envelope(command: CommandSchema) -> MAVLinkCommandEnvelope:
    """
    Pure translation: CommandSchema → MAVLinkCommandEnvelope.

    No decision-making. Deterministic 1:1 mapping.
    """
    mavlink_cmd = MAVLINK_COMMAND_MAP.get(
        command.command_type, "MAV_CMD_UNKNOWN",
    )

    params: dict = {}
    ct = command.command_type

    if ct == CommandType.ARM:
        params = {"param1": 1.0, "param2": 0.0}
    elif ct == CommandType.DISARM:
        params = {"param1": 0.0, "param2": 0.0}
    elif ct == CommandType.TAKEOFF:
        params = {
            "param7": command.params.get("altitude_m", 10.0),
        }
    elif ct == CommandType.LAND:
        params = {
            "param5": command.params.get("latitude", 0.0),
            "param6": command.params.get("longitude", 0.0),
        }
    elif ct == CommandType.GOTO:
        params = {
            "param5": command.params.get("latitude", 0.0),
            "param6": command.params.get("longitude", 0.0),
            "param7": command.params.get("altitude_m", 10.0),
        }
    elif ct == CommandType.RETURN_TO_HOME:
        params = {}
    elif ct == CommandType.SET_SPEED:
        params = {
            "param1": 1.0,
            "param2": command.params.get("speed_m_s", 5.0),
        }
    elif ct == CommandType.SPRAY_START:
        params = {"param1": 1.0}
    elif ct == CommandType.SPRAY_STOP:
        params = {"param1": 0.0}
    elif ct == CommandType.EMERGENCY_STOP:
        params = {"param1": 0.0, "param2": 21196.0}

    return MAVLinkCommandEnvelope(
        command_id=command.command_id,
        drone_id=command.drone_id,
        mavlink_command=mavlink_cmd,
        target_system=command.drone_id,
        params=params,
    )


# =========================================================================
# MAVLink Bridge
# =========================================================================

class MAVLinkBridge:
    """
    MAVLink Bridge — command execution with ACK/NACK/timeout/retry.

    Executes MAVLink commands against a target (PX4 SITL or simulation)
    with mandatory acknowledgment flow:

    1. Translate CommandSchema → MAVLinkCommandEnvelope
    2. Send command to target
    3. Wait for ACK (timeout: 3000ms)
    4. On NACK or TIMEOUT: retry (max 3 attempts)
    5. Return MAVLinkACKResult

    Architecture rules:
    - Commands enter ONLY via CommandSchema (no direct MAVLink)
    - Bridge is transport only — no decision-making
    - No Hive imports
    """

    MAX_RETRIES: int = 3
    TIMEOUT_MS: int = 3000

    def __init__(self, adapter: "_SITLExecutor") -> None:
        self._executor = adapter
        self._command_log: list[MAVLinkACKResult] = []
        self._lock = threading.Lock()
        logger.info("MAVLinkBridge: initialized")

    def execute_command(self, command: CommandSchema) -> MAVLinkACKResult:
        """
        Execute a command through the MAVLink bridge.

        Flow: CommandSchema → Envelope → Execute → ACK/NACK → Retry
        """
        envelope = translate_to_envelope(command)
        return self._execute_with_retry(envelope)

    def _execute_with_retry(
        self, envelope: MAVLinkCommandEnvelope,
    ) -> MAVLinkACKResult:
        """Execute with ACK/NACK/timeout handling and retry logic."""
        with self._lock:
            for attempt in range(1, self.MAX_RETRIES + 1):
                result = self._execute_single(envelope, attempt)

                if result.status == MAVLinkACKStatus.ACK:
                    self._command_log.append(result)
                    return result

                if result.status == MAVLinkACKStatus.NACK:
                    logger.warning(
                        "MAVLinkBridge: NACK for %s drone %d (attempt %d/%d)",
                        envelope.mavlink_command, envelope.drone_id,
                        attempt, self.MAX_RETRIES,
                    )
                    if attempt < self.MAX_RETRIES:
                        continue
                elif result.status == MAVLinkACKStatus.TIMEOUT:
                    logger.warning(
                        "MAVLinkBridge: TIMEOUT for %s drone %d (attempt %d/%d)",
                        envelope.mavlink_command, envelope.drone_id,
                        attempt, self.MAX_RETRIES,
                    )
                    if attempt < self.MAX_RETRIES:
                        continue

                result = MAVLinkACKResult(
                    command_id=envelope.command_id,
                    drone_id=envelope.drone_id,
                    status=result.status,
                    mavlink_command=envelope.mavlink_command,
                    attempts=attempt,
                    error_message=result.error_message,
                    timestamp_ms=int(time.monotonic() * 1000),
                )
                self._command_log.append(result)
                return result

            final = MAVLinkACKResult(
                command_id=envelope.command_id,
                drone_id=envelope.drone_id,
                status=MAVLinkACKStatus.TIMEOUT,
                mavlink_command=envelope.mavlink_command,
                attempts=self.MAX_RETRIES,
                error_message="Max retries exceeded",
                timestamp_ms=int(time.monotonic() * 1000),
            )
            self._command_log.append(final)
            return final

    def _execute_single(
        self, envelope: MAVLinkCommandEnvelope, attempt: int,
    ) -> MAVLinkACKResult:
        """Execute a single MAVLink command against the executor."""
        return self._executor.execute_mavlink(envelope, attempt)

    def to_execution_result(
        self, ack_result: MAVLinkACKResult,
    ) -> ExecutionResult:
        """Convert MAVLinkACKResult → HAL ExecutionResult."""
        if ack_result.status == MAVLinkACKStatus.ACK:
            return ExecutionResult(
                command_id=ack_result.command_id,
                drone_id=ack_result.drone_id,
                status=ExecutionStatus.SUCCESS,
                message=(
                    f"MAVLink {ack_result.mavlink_command} ACK "
                    f"(attempts: {ack_result.attempts})"
                ),
            )
        elif ack_result.status == MAVLinkACKStatus.NACK:
            return ExecutionResult(
                command_id=ack_result.command_id,
                drone_id=ack_result.drone_id,
                status=ExecutionStatus.REJECTED,
                message=f"MAVLink NACK: {ack_result.error_message}",
                error=HALError(
                    code=HALErrorCode.COMMAND_REJECTED,
                    message=ack_result.error_message or "Command rejected",
                    drone_id=ack_result.drone_id,
                    command_id=ack_result.command_id,
                ),
            )
        else:
            return ExecutionResult(
                command_id=ack_result.command_id,
                drone_id=ack_result.drone_id,
                status=ExecutionStatus.TIMEOUT,
                message=(
                    f"MAVLink TIMEOUT after {ack_result.attempts} attempts"
                ),
                error=HALError(
                    code=HALErrorCode.TIMEOUT,
                    message=f"Timeout after {ack_result.attempts} attempts",
                    drone_id=ack_result.drone_id,
                    command_id=ack_result.command_id,
                ),
            )

    @property
    def command_log(self) -> list[MAVLinkACKResult]:
        """Read-only access to command execution history."""
        return list(self._command_log)
