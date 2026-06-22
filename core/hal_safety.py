"""
Phase 9.4 — Safety & Emergency Layer.

Deterministic safety relay system for hardware-level emergency
conditions. HAL detects raw fault signals and relays safety
commands to hardware. All emergency DECISIONS belong to Hive.

HAL only:
- Detects raw fault signals
- Maps faults to fail-safe states
- Relays safety commands to hardware adapters

NO autonomous safety decisions, NO mission abortion logic,
NO fleet-level safety reasoning, NO optimization under
failure conditions, NO behavioral inference.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.hal_interfaces import (
    BaseDroneInterface,
    CommandSchema,
    CommandType,
    ExecutionResult,
    TelemetrySchema,
)

logger = logging.getLogger("eea.hal_safety")


# =========================================================================
# Emergency Signal Types
# =========================================================================

class EmergencyType(Enum):
    """Raw emergency signal types from hardware."""
    EMERGENCY_STOP = "emergency_stop"
    COMMUNICATION_LOSS = "communication_loss"
    LOW_BATTERY_CRITICAL = "low_battery_critical"
    HARDWARE_FAULT = "hardware_fault"
    GEOFENCE_BREACH = "geofence_breach"
    GPS_LOSS = "gps_loss"


# =========================================================================
# Fail-Safe States
# =========================================================================

class FailSafeState(Enum):
    """Hardware fail-safe states that adapters can execute."""
    KILL = "kill"
    RETURN_TO_HOME = "return_to_home"
    LAND_IN_PLACE = "land_in_place"
    HOVER = "hover"
    DISARM = "disarm"


# =========================================================================
# Emergency Signal
# =========================================================================

@dataclass
class EmergencySignal:
    """
    Raw emergency signal detected from hardware or commanded by Hive.

    HAL does not decide how to respond — it only packages the signal
    for Hive to process or relays Hive's commanded response.
    """
    drone_id: int
    emergency_type: EmergencyType
    timestamp_ms: int
    message: str = ""
    raw_data: dict = field(default_factory=dict)


# =========================================================================
# Safety Command Result
# =========================================================================

@dataclass
class SafetyCommandResult:
    """Result of a safety command relay to hardware."""
    drone_id: int
    fail_safe_state: FailSafeState
    execution_result: ExecutionResult
    signal: Optional[EmergencySignal] = None


# =========================================================================
# FailSafeStateMapper — Maps Emergency Types to Hardware Commands
# =========================================================================

class FailSafeStateMapper:
    """
    Maps fail-safe states to hardware command sequences.

    Pure mapping — no decision logic. The mapping is deterministic
    and configured at initialization. Hive decides which fail-safe
    state to activate; this mapper only translates it to commands.
    """

    FAIL_SAFE_COMMANDS: dict[FailSafeState, CommandType] = {
        FailSafeState.KILL: CommandType.EMERGENCY_STOP,
        FailSafeState.RETURN_TO_HOME: CommandType.RETURN_TO_HOME,
        FailSafeState.LAND_IN_PLACE: CommandType.LAND,
        FailSafeState.HOVER: CommandType.SET_SPEED,
        FailSafeState.DISARM: CommandType.DISARM,
    }

    FAIL_SAFE_PARAMS: dict[FailSafeState, dict] = {
        FailSafeState.HOVER: {"speed_m_s": 0.0},
    }

    def map_to_command(
        self, drone_id: int, fail_safe: FailSafeState, command_id: str,
    ) -> CommandSchema:
        """Map a fail-safe state to a hardware command. Pure translation."""
        cmd_type = self.FAIL_SAFE_COMMANDS[fail_safe]
        params = dict(self.FAIL_SAFE_PARAMS.get(fail_safe, {}))

        return CommandSchema(
            command_id=command_id,
            drone_id=drone_id,
            command_type=cmd_type,
            params=params,
        )


# =========================================================================
# EmergencySignalHandler — Detects and Packages Emergency Signals
# =========================================================================

class EmergencySignalHandler:
    """
    Detects raw emergency conditions from telemetry.

    Only packages signals — does NOT decide responses. All
    response decisions belong to Hive. Thresholds are
    configurable but deterministic.
    """

    def __init__(
        self,
        low_battery_threshold_pct: float = 10.0,
        signal_loss_threshold_pct: float = 5.0,
    ) -> None:
        self._low_battery_threshold = low_battery_threshold_pct
        self._signal_loss_threshold = signal_loss_threshold_pct
        self._signal_log: list[EmergencySignal] = []
        logger.info(
            "EmergencySignalHandler: initialized "
            "(battery_threshold=%.1f%%, signal_threshold=%.1f%%)",
            low_battery_threshold_pct, signal_loss_threshold_pct,
        )

    def check_telemetry(self, telemetry: TelemetrySchema) -> list[EmergencySignal]:
        """
        Check telemetry for raw emergency conditions.

        Returns a list of detected signals. Does NOT decide
        what to do — only reports conditions.
        """
        signals: list[EmergencySignal] = []
        ts = telemetry.timestamp_ms

        if not telemetry.is_connected:
            sig = EmergencySignal(
                drone_id=telemetry.drone_id,
                emergency_type=EmergencyType.COMMUNICATION_LOSS,
                timestamp_ms=ts,
                message="Communication lost",
            )
            signals.append(sig)

        if (
            telemetry.battery_pct is not None
            and telemetry.battery_pct <= self._low_battery_threshold
        ):
            sig = EmergencySignal(
                drone_id=telemetry.drone_id,
                emergency_type=EmergencyType.LOW_BATTERY_CRITICAL,
                timestamp_ms=ts,
                message=f"Battery critical: {telemetry.battery_pct:.1f}%",
            )
            signals.append(sig)

        if (
            telemetry.signal_strength_pct is not None
            and telemetry.signal_strength_pct <= self._signal_loss_threshold
        ):
            sig = EmergencySignal(
                drone_id=telemetry.drone_id,
                emergency_type=EmergencyType.GPS_LOSS,
                timestamp_ms=ts,
                message=f"GPS signal critical: {telemetry.signal_strength_pct:.1f}%",
            )
            signals.append(sig)

        for sig in signals:
            self._signal_log.append(sig)
            logger.warning(
                "EmergencySignalHandler: %s detected for drone %d — %s",
                sig.emergency_type.value, sig.drone_id, sig.message,
            )

        return signals

    def create_signal(
        self, drone_id: int, emergency_type: EmergencyType,
        timestamp_ms: int, message: str = "",
    ) -> EmergencySignal:
        """Create an emergency signal manually (e.g., from Hive command)."""
        sig = EmergencySignal(
            drone_id=drone_id,
            emergency_type=emergency_type,
            timestamp_ms=timestamp_ms,
            message=message,
        )
        self._signal_log.append(sig)
        logger.warning(
            "EmergencySignalHandler: manual signal %s for drone %d",
            emergency_type.value, drone_id,
        )
        return sig

    @property
    def signal_log(self) -> list[EmergencySignal]:
        """Read-only access to signal history."""
        return list(self._signal_log)


# =========================================================================
# SafetyCommandRelay — Relays Safety Commands to Hardware
# =========================================================================

class SafetyCommandRelay:
    """
    Relays safety commands to hardware adapters.

    Pure pass-through — takes a fail-safe state (decided by Hive),
    maps it to a hardware command, and sends it to the adapter.
    No interpretation, no autonomous decisions.
    """

    def __init__(
        self,
        adapter: BaseDroneInterface,
        mapper: Optional[FailSafeStateMapper] = None,
    ) -> None:
        self._adapter = adapter
        self._mapper = mapper or FailSafeStateMapper()
        self._relay_log: list[SafetyCommandResult] = []
        logger.info(
            "SafetyCommandRelay: initialized with %s",
            adapter.get_adapter_name(),
        )

    def relay_fail_safe(
        self,
        drone_id: int,
        fail_safe: FailSafeState,
        signal: Optional[EmergencySignal] = None,
    ) -> SafetyCommandResult:
        """
        Relay a fail-safe command to hardware.

        The fail-safe state is decided by Hive — this method
        only translates and sends it.
        """
        cmd_id = f"safety-{fail_safe.value}-{drone_id}"
        command = self._mapper.map_to_command(drone_id, fail_safe, cmd_id)
        result = self._adapter.send_command(command)

        scr = SafetyCommandResult(
            drone_id=drone_id,
            fail_safe_state=fail_safe,
            execution_result=result,
            signal=signal,
        )
        self._relay_log.append(scr)

        logger.info(
            "SafetyCommandRelay: %s -> drone %d -> %s",
            fail_safe.value, drone_id, result.status.value,
        )
        return scr

    def emergency_stop(self, drone_id: int) -> SafetyCommandResult:
        """Relay emergency stop (KILL) to hardware."""
        return self.relay_fail_safe(drone_id, FailSafeState.KILL)

    def return_to_home(self, drone_id: int) -> SafetyCommandResult:
        """Relay return-to-home to hardware."""
        return self.relay_fail_safe(drone_id, FailSafeState.RETURN_TO_HOME)

    def land_in_place(self, drone_id: int) -> SafetyCommandResult:
        """Relay land-in-place to hardware."""
        return self.relay_fail_safe(drone_id, FailSafeState.LAND_IN_PLACE)

    @property
    def relay_log(self) -> list[SafetyCommandResult]:
        """Read-only access to relay history."""
        return list(self._relay_log)
