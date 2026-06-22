"""
Phase 9.2 — Hardware Adapters.

Pluggable adapters translating HAL commands to specific hardware
systems. Each adapter implements BaseDroneInterface and translates
commands only — NO mission interpretation, NO decision-making,
NO optimization, NO scheduling, NO cross-drone coordination.

Adapters are PURE TRANSLATION LAYERS.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
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

logger = logging.getLogger("eea.hal_adapters")


# =========================================================================
# Simulation Adapter — For Testing and Validation
# =========================================================================

@dataclass
class SimulatedDrone:
    """Internal state for a simulated drone."""
    drone_id: int
    armed: bool = False
    flight_state: FlightState = FlightState.GROUNDED
    position: GPSPosition = field(
        default_factory=lambda: GPSPosition(0.0, 0.0, 0.0)
    )
    battery_pct: float = 100.0
    speed_m_s: float = 0.0
    heading_deg: float = 0.0
    connected: bool = True
    spraying: bool = False


class SimulationAdapter(BaseDroneInterface):
    """
    Simulation adapter for testing HAL contracts.

    Maintains in-memory simulated drone state. Translates
    CommandSchema into simulated state changes. Does NOT
    interpret mission intent — only applies the command
    mechanically.
    """

    def __init__(self) -> None:
        self._drones: dict[int, SimulatedDrone] = {}
        self._command_log: list[tuple[str, CommandSchema]] = []
        logger.info("SimulationAdapter: initialized")

    def register_drone(self, drone_id: int) -> None:
        """Register a simulated drone."""
        if drone_id in self._drones:
            raise ValueError(f"Drone {drone_id} already registered")
        self._drones[drone_id] = SimulatedDrone(drone_id=drone_id)
        logger.info("SimulationAdapter: drone %d registered", drone_id)

    def _get_drone(self, drone_id: int) -> SimulatedDrone:
        if drone_id not in self._drones:
            raise ValueError(
                f"Drone {drone_id} not registered in SimulationAdapter"
            )
        return self._drones[drone_id]

    def _timestamp(self) -> int:
        return int(time.monotonic() * 1000)

    def send_command(self, command: CommandSchema) -> ExecutionResult:
        """Translate command into simulated state change."""
        self._command_log.append(("send", command))

        try:
            drone = self._get_drone(command.drone_id)
        except ValueError as e:
            return ExecutionResult(
                command_id=command.command_id,
                drone_id=command.drone_id,
                status=ExecutionStatus.FAILED,
                message=str(e),
                error=HALError(
                    code=HALErrorCode.INVALID_STATE,
                    message=str(e),
                    drone_id=command.drone_id,
                    command_id=command.command_id,
                ),
            )

        if not drone.connected:
            return ExecutionResult(
                command_id=command.command_id,
                drone_id=command.drone_id,
                status=ExecutionStatus.FAILED,
                message="Drone not connected",
                error=HALError(
                    code=HALErrorCode.COMMUNICATION_FAILURE,
                    message="Drone not connected",
                    drone_id=command.drone_id,
                    command_id=command.command_id,
                ),
            )

        result = self._apply_command(drone, command)
        logger.info(
            "SimulationAdapter: command %s -> drone %d -> %s",
            command.command_type.value, command.drone_id, result.status.value,
        )
        return result

    def _apply_command(
        self, drone: SimulatedDrone, command: CommandSchema,
    ) -> ExecutionResult:
        """Apply command to simulated drone state. Pure translation."""
        ct = command.command_type

        if ct == CommandType.ARM:
            if drone.flight_state != FlightState.GROUNDED:
                return self._reject(command, "Cannot arm: not grounded")
            drone.armed = True
            drone.flight_state = FlightState.ARMED

        elif ct == CommandType.DISARM:
            if drone.flight_state not in (
                FlightState.GROUNDED, FlightState.ARMED,
            ):
                return self._reject(command, "Cannot disarm: in flight")
            drone.armed = False
            drone.flight_state = FlightState.GROUNDED

        elif ct == CommandType.TAKEOFF:
            if drone.flight_state != FlightState.ARMED:
                return self._reject(command, "Cannot takeoff: not armed")
            altitude = command.params.get("altitude_m", 10.0)
            drone.flight_state = FlightState.IN_FLIGHT
            drone.position = GPSPosition(
                drone.position.latitude,
                drone.position.longitude,
                altitude,
            )
            drone.speed_m_s = 0.0

        elif ct == CommandType.LAND:
            if drone.flight_state not in (
                FlightState.IN_FLIGHT, FlightState.RETURNING,
            ):
                return self._reject(command, "Cannot land: not in flight")
            drone.flight_state = FlightState.GROUNDED
            drone.position = GPSPosition(
                drone.position.latitude,
                drone.position.longitude,
                0.0,
            )
            drone.speed_m_s = 0.0
            drone.armed = False

        elif ct == CommandType.GOTO:
            if drone.flight_state != FlightState.IN_FLIGHT:
                return self._reject(command, "Cannot goto: not in flight")
            lat = command.params.get("latitude", drone.position.latitude)
            lon = command.params.get("longitude", drone.position.longitude)
            alt = command.params.get("altitude_m", drone.position.altitude_m)
            speed = command.params.get("speed_m_s", 5.0)
            drone.position = GPSPosition(lat, lon, alt)
            drone.speed_m_s = speed

        elif ct == CommandType.RETURN_TO_HOME:
            if drone.flight_state not in (
                FlightState.IN_FLIGHT, FlightState.ARMED,
            ):
                return self._reject(command, "Cannot RTH: not in flight")
            drone.flight_state = FlightState.RETURNING
            drone.speed_m_s = 3.0

        elif ct == CommandType.SET_SPEED:
            if drone.flight_state != FlightState.IN_FLIGHT:
                return self._reject(
                    command, "Cannot set speed: not in flight",
                )
            drone.speed_m_s = command.params.get("speed_m_s", 5.0)

        elif ct == CommandType.SPRAY_START:
            if drone.flight_state != FlightState.IN_FLIGHT:
                return self._reject(
                    command, "Cannot spray: not in flight",
                )
            drone.spraying = True

        elif ct == CommandType.SPRAY_STOP:
            drone.spraying = False

        elif ct == CommandType.EMERGENCY_STOP:
            drone.flight_state = FlightState.EMERGENCY
            drone.speed_m_s = 0.0
            drone.spraying = False
            drone.armed = False

        return ExecutionResult(
            command_id=command.command_id,
            drone_id=command.drone_id,
            status=ExecutionStatus.SUCCESS,
            message=f"{command.command_type.value} executed",
            telemetry=self._build_telemetry(drone),
        )

    def _reject(
        self, command: CommandSchema, reason: str,
    ) -> ExecutionResult:
        return ExecutionResult(
            command_id=command.command_id,
            drone_id=command.drone_id,
            status=ExecutionStatus.REJECTED,
            message=reason,
            error=HALError(
                code=HALErrorCode.INVALID_STATE,
                message=reason,
                drone_id=command.drone_id,
                command_id=command.command_id,
            ),
        )

    def _build_telemetry(self, drone: SimulatedDrone) -> TelemetrySchema:
        return TelemetrySchema(
            drone_id=drone.drone_id,
            timestamp_ms=self._timestamp(),
            flight_state=drone.flight_state,
            position=GPSPosition(
                drone.position.latitude,
                drone.position.longitude,
                drone.position.altitude_m,
            ),
            battery_pct=drone.battery_pct,
            speed_m_s=drone.speed_m_s,
            heading_deg=drone.heading_deg,
            is_connected=drone.connected,
        )

    def get_telemetry(self, drone_id: int) -> TelemetrySchema:
        """Read current telemetry from simulated drone."""
        drone = self._get_drone(drone_id)
        return self._build_telemetry(drone)

    def arm(self, drone_id: int) -> ExecutionResult:
        """Arm the simulated drone."""
        cmd = CommandSchema(
            command_id=f"arm-{drone_id}",
            drone_id=drone_id,
            command_type=CommandType.ARM,
        )
        return self.send_command(cmd)

    def disarm(self, drone_id: int) -> ExecutionResult:
        """Disarm the simulated drone."""
        cmd = CommandSchema(
            command_id=f"disarm-{drone_id}",
            drone_id=drone_id,
            command_type=CommandType.DISARM,
        )
        return self.send_command(cmd)

    def return_to_home(self, drone_id: int) -> ExecutionResult:
        """Command simulated drone to return home."""
        cmd = CommandSchema(
            command_id=f"rth-{drone_id}",
            drone_id=drone_id,
            command_type=CommandType.RETURN_TO_HOME,
        )
        return self.send_command(cmd)

    def is_connected(self, drone_id: int) -> bool:
        """Check if simulated drone is connected."""
        try:
            drone = self._get_drone(drone_id)
            return drone.connected
        except ValueError:
            return False

    def get_adapter_name(self) -> str:
        return "SimulationAdapter"

    @property
    def command_log(self) -> list[tuple[str, CommandSchema]]:
        """Read-only access to command history (for testing)."""
        return list(self._command_log)

    def set_connected(self, drone_id: int, connected: bool) -> None:
        """Simulate connection state change (for testing)."""
        self._get_drone(drone_id).connected = connected

    def set_battery(self, drone_id: int, pct: float) -> None:
        """Simulate battery level change (for testing)."""
        self._get_drone(drone_id).battery_pct = pct


# =========================================================================
# PX4 Adapter — PX4 Autopilot Translation Layer
# =========================================================================

class PX4Adapter(BaseDroneInterface):
    """
    PX4 autopilot adapter. Translates HAL commands into PX4
    MAVLink-compatible protocol format.

    This is a structural adapter — actual MAVLink communication
    is deferred to Phase 10 (real-world deployment). For now,
    it validates command translation and produces PX4-formatted
    command representations.

    NO decision-making, NO mission interpretation.
    """

    PX4_COMMAND_MAP: dict[CommandType, str] = {
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

    def __init__(self) -> None:
        self._connected_drones: set[int] = set()
        self._translated_commands: list[dict] = []
        logger.info("PX4Adapter: initialized")

    def register_drone(self, drone_id: int) -> None:
        """Register a PX4 drone connection."""
        self._connected_drones.add(drone_id)
        logger.info("PX4Adapter: drone %d registered", drone_id)

    def send_command(self, command: CommandSchema) -> ExecutionResult:
        """Translate command into PX4 MAVLink format."""
        if command.drone_id not in self._connected_drones:
            return ExecutionResult(
                command_id=command.command_id,
                drone_id=command.drone_id,
                status=ExecutionStatus.FAILED,
                message="Drone not registered in PX4Adapter",
                error=HALError(
                    code=HALErrorCode.COMMUNICATION_FAILURE,
                    message="Drone not registered",
                    drone_id=command.drone_id,
                    command_id=command.command_id,
                ),
            )

        mavlink_cmd = self._translate_to_mavlink(command)
        self._translated_commands.append(mavlink_cmd)

        logger.info(
            "PX4Adapter: translated %s -> %s for drone %d",
            command.command_type.value,
            mavlink_cmd["mavlink_command"],
            command.drone_id,
        )

        return ExecutionResult(
            command_id=command.command_id,
            drone_id=command.drone_id,
            status=ExecutionStatus.SUCCESS,
            message=f"PX4: {mavlink_cmd['mavlink_command']} sent",
        )

    def _translate_to_mavlink(self, command: CommandSchema) -> dict:
        """Pure translation from HAL command to MAVLink format."""
        mavlink_cmd = self.PX4_COMMAND_MAP.get(
            command.command_type, "MAV_CMD_UNKNOWN",
        )

        translated = {
            "mavlink_command": mavlink_cmd,
            "target_system": command.drone_id,
            "target_component": 1,
            "command_id": command.command_id,
            "params": {},
        }

        ct = command.command_type
        if ct == CommandType.ARM:
            translated["params"] = {"arm": 1, "force": 0}
        elif ct == CommandType.DISARM:
            translated["params"] = {"arm": 0, "force": 0}
        elif ct == CommandType.TAKEOFF:
            translated["params"] = {
                "altitude": command.params.get("altitude_m", 10.0),
            }
        elif ct == CommandType.GOTO:
            translated["params"] = {
                "latitude": command.params.get("latitude", 0.0),
                "longitude": command.params.get("longitude", 0.0),
                "altitude": command.params.get("altitude_m", 10.0),
            }
        elif ct == CommandType.SET_SPEED:
            translated["params"] = {
                "speed": command.params.get("speed_m_s", 5.0),
                "speed_type": 1,
            }
        elif ct == CommandType.EMERGENCY_STOP:
            translated["params"] = {"arm": 0, "force": 21196}

        return translated

    def get_telemetry(self, drone_id: int) -> TelemetrySchema:
        """Read PX4 telemetry (structural — returns placeholder)."""
        if drone_id not in self._connected_drones:
            raise ValueError(f"Drone {drone_id} not registered in PX4Adapter")
        return TelemetrySchema(
            drone_id=drone_id,
            timestamp_ms=int(time.monotonic() * 1000),
            flight_state=FlightState.UNKNOWN,
            is_connected=True,
            raw_data={"adapter": "px4", "note": "actual telemetry requires MAVLink connection"},
        )

    def arm(self, drone_id: int) -> ExecutionResult:
        cmd = CommandSchema(
            command_id=f"px4-arm-{drone_id}",
            drone_id=drone_id,
            command_type=CommandType.ARM,
        )
        return self.send_command(cmd)

    def disarm(self, drone_id: int) -> ExecutionResult:
        cmd = CommandSchema(
            command_id=f"px4-disarm-{drone_id}",
            drone_id=drone_id,
            command_type=CommandType.DISARM,
        )
        return self.send_command(cmd)

    def return_to_home(self, drone_id: int) -> ExecutionResult:
        cmd = CommandSchema(
            command_id=f"px4-rth-{drone_id}",
            drone_id=drone_id,
            command_type=CommandType.RETURN_TO_HOME,
        )
        return self.send_command(cmd)

    def is_connected(self, drone_id: int) -> bool:
        return drone_id in self._connected_drones

    def get_adapter_name(self) -> str:
        return "PX4Adapter"

    @property
    def translated_commands(self) -> list[dict]:
        """Read-only access to translated command history."""
        return list(self._translated_commands)


# =========================================================================
# ArduPilot Adapter — ArduPilot Translation Layer
# =========================================================================

class ArduPilotAdapter(BaseDroneInterface):
    """
    ArduPilot adapter. Translates HAL commands into ArduPilot
    MAVLink-compatible protocol format.

    ArduPilot uses similar MAVLink commands to PX4 but with
    different parameter conventions and flight modes.

    NO decision-making, NO mission interpretation.
    """

    ARDUPILOT_MODE_MAP: dict[CommandType, str] = {
        CommandType.ARM: "ARM",
        CommandType.DISARM: "DISARM",
        CommandType.TAKEOFF: "GUIDED_TAKEOFF",
        CommandType.LAND: "LAND",
        CommandType.GOTO: "GUIDED",
        CommandType.RETURN_TO_HOME: "RTL",
        CommandType.SET_SPEED: "SET_SPEED",
        CommandType.SPRAY_START: "SERVO_ON",
        CommandType.SPRAY_STOP: "SERVO_OFF",
        CommandType.EMERGENCY_STOP: "EMERGENCY_DISARM",
    }

    def __init__(self) -> None:
        self._connected_drones: set[int] = set()
        self._translated_commands: list[dict] = []
        logger.info("ArduPilotAdapter: initialized")

    def register_drone(self, drone_id: int) -> None:
        """Register an ArduPilot drone connection."""
        self._connected_drones.add(drone_id)
        logger.info("ArduPilotAdapter: drone %d registered", drone_id)

    def send_command(self, command: CommandSchema) -> ExecutionResult:
        """Translate command into ArduPilot format."""
        if command.drone_id not in self._connected_drones:
            return ExecutionResult(
                command_id=command.command_id,
                drone_id=command.drone_id,
                status=ExecutionStatus.FAILED,
                message="Drone not registered in ArduPilotAdapter",
                error=HALError(
                    code=HALErrorCode.COMMUNICATION_FAILURE,
                    message="Drone not registered",
                    drone_id=command.drone_id,
                    command_id=command.command_id,
                ),
            )

        ardu_cmd = self._translate_to_ardupilot(command)
        self._translated_commands.append(ardu_cmd)

        logger.info(
            "ArduPilotAdapter: translated %s -> %s for drone %d",
            command.command_type.value,
            ardu_cmd["mode"],
            command.drone_id,
        )

        return ExecutionResult(
            command_id=command.command_id,
            drone_id=command.drone_id,
            status=ExecutionStatus.SUCCESS,
            message=f"ArduPilot: {ardu_cmd['mode']} sent",
        )

    def _translate_to_ardupilot(self, command: CommandSchema) -> dict:
        """Pure translation from HAL command to ArduPilot format."""
        mode = self.ARDUPILOT_MODE_MAP.get(
            command.command_type, "UNKNOWN",
        )

        translated = {
            "mode": mode,
            "target_system": command.drone_id,
            "command_id": command.command_id,
            "params": {},
        }

        ct = command.command_type
        if ct == CommandType.TAKEOFF:
            translated["params"] = {
                "altitude": command.params.get("altitude_m", 10.0),
                "mode": "GUIDED",
            }
        elif ct == CommandType.GOTO:
            translated["params"] = {
                "lat": command.params.get("latitude", 0.0),
                "lon": command.params.get("longitude", 0.0),
                "alt": command.params.get("altitude_m", 10.0),
                "frame": "GLOBAL_RELATIVE_ALT",
            }
        elif ct == CommandType.SET_SPEED:
            translated["params"] = {
                "airspeed": command.params.get("speed_m_s", 5.0),
                "throttle": -1,
            }
        elif ct == CommandType.SPRAY_START:
            translated["params"] = {
                "servo_channel": command.params.get("servo_channel", 9),
                "pwm": command.params.get("pwm_on", 1900),
            }
        elif ct == CommandType.SPRAY_STOP:
            translated["params"] = {
                "servo_channel": command.params.get("servo_channel", 9),
                "pwm": command.params.get("pwm_off", 1100),
            }

        return translated

    def get_telemetry(self, drone_id: int) -> TelemetrySchema:
        """Read ArduPilot telemetry (structural — returns placeholder)."""
        if drone_id not in self._connected_drones:
            raise ValueError(
                f"Drone {drone_id} not registered in ArduPilotAdapter",
            )
        return TelemetrySchema(
            drone_id=drone_id,
            timestamp_ms=int(time.monotonic() * 1000),
            flight_state=FlightState.UNKNOWN,
            is_connected=True,
            raw_data={"adapter": "ardupilot", "note": "actual telemetry requires MAVLink connection"},
        )

    def arm(self, drone_id: int) -> ExecutionResult:
        cmd = CommandSchema(
            command_id=f"ardu-arm-{drone_id}",
            drone_id=drone_id,
            command_type=CommandType.ARM,
        )
        return self.send_command(cmd)

    def disarm(self, drone_id: int) -> ExecutionResult:
        cmd = CommandSchema(
            command_id=f"ardu-disarm-{drone_id}",
            drone_id=drone_id,
            command_type=CommandType.DISARM,
        )
        return self.send_command(cmd)

    def return_to_home(self, drone_id: int) -> ExecutionResult:
        cmd = CommandSchema(
            command_id=f"ardu-rth-{drone_id}",
            drone_id=drone_id,
            command_type=CommandType.RETURN_TO_HOME,
        )
        return self.send_command(cmd)

    def is_connected(self, drone_id: int) -> bool:
        return drone_id in self._connected_drones

    def get_adapter_name(self) -> str:
        return "ArduPilotAdapter"

    @property
    def translated_commands(self) -> list[dict]:
        """Read-only access to translated command history."""
        return list(self._translated_commands)
