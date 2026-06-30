"""
Phase 10A — Simulation Core.

Multi-drone SITL orchestrator that integrates:
- SimulationAdapter (HAL Phase 9.2) for drone state
- MAVLink Bridge for command execution with ACK/NACK
- ROS2 Swarm Bus for state publication
- Failure Injection for controlled fault simulation

Single execution path (ENFORCED):
  Hive → CommandSchema → MAVLink Bridge → PX4 SITL (sim)
  PX4 SITL → ROS2 Swarm Bus → Digital Twin (Phase 10B)

Architecture rules:
- NO decision-making
- NO Hive state modification
- NO UI logic
- NO command bypass (all via CommandSchema)
- Simulation is execution + state transport ONLY
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
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
from core.hal_adapters import SimulationAdapter
from simulation.mavlink_bridge import (
    MAVLinkACKResult,
    MAVLinkACKStatus,
    MAVLinkBridge,
    MAVLinkCommandEnvelope,
    translate_to_envelope,
)
from simulation.ros2_swarm_bus import (
    DroneActivityState,
    DroneHealthStatus,
    DroneStateMessage,
    SwarmBus,
    SwarmGlobalState,
)
from simulation.failure_injection import (
    FailureConfig,
    FailureInjector,
    FailureType,
)

logger = logging.getLogger("eea.sim_core")


# =========================================================================
# SITL Executor — Simulation-backed MAVLink Execution
# =========================================================================

class SITLExecutor:
    """
    Executes MAVLink commands against the in-memory SimulationAdapter.

    This bridges the MAVLink Bridge to the SimulationAdapter, providing
    ACK/NACK responses based on command execution results.

    In production, this would be replaced with actual PX4 SITL
    communication via pymavlink.
    """

    def __init__(self, adapter: SimulationAdapter) -> None:
        self._adapter = adapter

    def execute_mavlink(
        self, envelope: MAVLinkCommandEnvelope, attempt: int,
    ) -> MAVLinkACKResult:
        """
        Execute a MAVLink envelope against the simulation adapter.

        Translates the envelope back to a CommandSchema (which the
        adapter already knows) and returns ACK/NACK based on result.
        """
        cmd = CommandSchema(
            command_id=envelope.command_id,
            drone_id=envelope.drone_id,
            command_type=self._resolve_command_type(envelope.mavlink_command),
            params=self._resolve_params(envelope),
        )

        result = self._adapter.send_command(cmd)

        if result.status == ExecutionStatus.SUCCESS:
            return MAVLinkACKResult(
                command_id=envelope.command_id,
                drone_id=envelope.drone_id,
                status=MAVLinkACKStatus.ACK,
                mavlink_command=envelope.mavlink_command,
                attempts=attempt,
                timestamp_ms=int(time.monotonic() * 1000),
            )
        elif result.status == ExecutionStatus.REJECTED:
            return MAVLinkACKResult(
                command_id=envelope.command_id,
                drone_id=envelope.drone_id,
                status=MAVLinkACKStatus.NACK,
                mavlink_command=envelope.mavlink_command,
                attempts=attempt,
                error_message=result.message,
                timestamp_ms=int(time.monotonic() * 1000),
            )
        else:
            return MAVLinkACKResult(
                command_id=envelope.command_id,
                drone_id=envelope.drone_id,
                status=MAVLinkACKStatus.NACK,
                mavlink_command=envelope.mavlink_command,
                attempts=attempt,
                error_message=result.message,
                timestamp_ms=int(time.monotonic() * 1000),
            )

    def _resolve_command_type(self, mavlink_cmd: str) -> CommandType:
        """Reverse-map MAVLink command to CommandType."""
        reverse_map = {
            "MAV_CMD_COMPONENT_ARM_DISARM": CommandType.ARM,
            "MAV_CMD_NAV_TAKEOFF": CommandType.TAKEOFF,
            "MAV_CMD_NAV_LAND": CommandType.LAND,
            "MAV_CMD_NAV_WAYPOINT": CommandType.GOTO,
            "MAV_CMD_NAV_RETURN_TO_LAUNCH": CommandType.RETURN_TO_HOME,
            "MAV_CMD_DO_CHANGE_SPEED": CommandType.SET_SPEED,
            "MAV_CMD_DO_SET_ACTUATOR": CommandType.SPRAY_START,
        }
        return reverse_map.get(mavlink_cmd, CommandType.ARM)

    def _resolve_params(self, envelope: MAVLinkCommandEnvelope) -> dict:
        """Translate MAVLink params back to HAL params format."""
        params = {}
        ep = envelope.params

        if envelope.mavlink_command == "MAV_CMD_NAV_TAKEOFF":
            params["altitude_m"] = ep.get("param7", 10.0)
        elif envelope.mavlink_command == "MAV_CMD_NAV_WAYPOINT":
            params["latitude"] = ep.get("param5", 0.0)
            params["longitude"] = ep.get("param6", 0.0)
            params["altitude_m"] = ep.get("param7", 10.0)
        elif envelope.mavlink_command == "MAV_CMD_DO_CHANGE_SPEED":
            params["speed_m_s"] = ep.get("param2", 5.0)
        elif envelope.mavlink_command == "MAV_CMD_COMPONENT_ARM_DISARM":
            if ep.get("param2", 0.0) == 21196.0:
                pass  # emergency stop uses force param

        return params


# =========================================================================
# Flight State → Activity State Mapping (Deterministic)
# =========================================================================

FLIGHT_STATE_TO_ACTIVITY: dict[FlightState, DroneActivityState] = {
    FlightState.GROUNDED: DroneActivityState.IDLE,
    FlightState.ARMING: DroneActivityState.IDLE,
    FlightState.ARMED: DroneActivityState.IDLE,
    FlightState.TAKING_OFF: DroneActivityState.ACTIVE,
    FlightState.IN_FLIGHT: DroneActivityState.ACTIVE,
    FlightState.LANDING: DroneActivityState.RETURNING,
    FlightState.RETURNING: DroneActivityState.RETURNING,
    FlightState.EMERGENCY: DroneActivityState.FAIL,
    FlightState.UNKNOWN: DroneActivityState.IDLE,
}


# =========================================================================
# Simulation Core
# =========================================================================

class SimulationCore:
    """
    Multi-drone simulation environment.

    Orchestrates 2+ simulated PX4 SITL drones with:
    - Command execution via MAVLink Bridge (ACK/NACK/retry)
    - State publication via ROS2 Swarm Bus
    - Controlled failure injection
    - Telemetry streaming

    Single execution path:
      CommandSchema → MAVLink Bridge → SITLExecutor → SimulationAdapter

    State output path:
      SimulationAdapter → ROS2 Swarm Bus → (Digital Twin in Phase 10B)
    """

    def __init__(
        self,
        num_drones: int = 3,
        failure_seed: Optional[int] = None,
    ) -> None:
        if num_drones < 1:
            raise ValueError("Must have at least 1 drone")

        self._num_drones = num_drones
        self._drone_ids = list(range(1, num_drones + 1))

        # Simulation adapter (HAL Phase 9.2)
        self._adapter = SimulationAdapter()
        for drone_id in self._drone_ids:
            self._adapter.register_drone(drone_id)

        # MAVLink Bridge (Phase 10A)
        self._sitl_executor = SITLExecutor(self._adapter)
        self._bridge = MAVLinkBridge(self._sitl_executor)

        # ROS2 Swarm Bus (Phase 10A)
        self._bus = SwarmBus()

        # Failure Injection (Phase 10A)
        self._failure_injector = FailureInjector(seed=failure_seed)
        for drone_id in self._drone_ids:
            self._failure_injector.register_drone(drone_id)

        self._running = False
        self._tick_count = 0

        logger.info(
            "SimulationCore: initialized with %d drones [%s]",
            num_drones, self._drone_ids,
        )

    @property
    def adapter(self) -> SimulationAdapter:
        """Access to underlying simulation adapter (read-only intent)."""
        return self._adapter

    @property
    def bridge(self) -> MAVLinkBridge:
        """Access to MAVLink bridge."""
        return self._bridge

    @property
    def bus(self) -> SwarmBus:
        """Access to ROS2 swarm bus."""
        return self._bus

    @property
    def failure_injector(self) -> FailureInjector:
        """Access to failure injection system."""
        return self._failure_injector

    @property
    def drone_ids(self) -> list[int]:
        """Registered drone IDs."""
        return list(self._drone_ids)

    @property
    def tick_count(self) -> int:
        """Number of simulation ticks executed."""
        return self._tick_count

    # -----------------------------------------------------------------
    # Command Execution (Single Entry Point: CommandSchema)
    # -----------------------------------------------------------------

    def execute_command(self, command: CommandSchema) -> ExecutionResult:
        """
        Execute a command through the full MAVLink bridge path.

        Flow: CommandSchema → MAVLink Bridge → SITL Executor → Adapter
        Returns: HAL ExecutionResult
        """
        if command.drone_id not in self._drone_ids:
            return ExecutionResult(
                command_id=command.command_id,
                drone_id=command.drone_id,
                status=ExecutionStatus.FAILED,
                message=f"Drone {command.drone_id} not in simulation",
                error=HALError(
                    code=HALErrorCode.INVALID_STATE,
                    message=f"Drone {command.drone_id} not registered",
                    drone_id=command.drone_id,
                    command_id=command.command_id,
                ),
            )

        ack_result = self._bridge.execute_command(command)
        execution_result = self._bridge.to_execution_result(ack_result)

        self._publish_drone_state(command.drone_id)

        return execution_result

    # -----------------------------------------------------------------
    # State Publication (ROS2 Swarm Bus)
    # -----------------------------------------------------------------

    def _publish_drone_state(self, drone_id: int) -> None:
        """Publish current drone state to ROS2 bus."""
        telemetry = self._adapter.get_telemetry(drone_id)
        now_ms = int(time.monotonic() * 1000)

        activity = FLIGHT_STATE_TO_ACTIVITY.get(
            telemetry.flight_state, DroneActivityState.IDLE,
        )

        health = DroneHealthStatus.OK
        if telemetry.battery_pct < 10:
            health = DroneHealthStatus.CRITICAL
        elif telemetry.battery_pct < 25:
            health = DroneHealthStatus.WARNING

        if not telemetry.is_connected:
            health = DroneHealthStatus.CRITICAL
            activity = DroneActivityState.FAIL

        msg = DroneStateMessage(
            drone_id=drone_id,
            timestamp_ms=now_ms,
            latitude=telemetry.position.latitude if telemetry.position else 0.0,
            longitude=telemetry.position.longitude if telemetry.position else 0.0,
            altitude_m=telemetry.position.altitude_m if telemetry.position else 0.0,
            battery_pct=telemetry.battery_pct,
            state=activity,
            health=health,
        )
        self._bus.publish_drone_state(msg)

    def publish_all_states(self) -> None:
        """Publish state for all drones + global state to bus."""
        for drone_id in self._drone_ids:
            self._publish_drone_state(drone_id)
        self._publish_global_state()

    def _publish_global_state(self) -> None:
        """Publish aggregated swarm state."""
        active = []
        idle = 0
        fail = 0

        for drone_id in self._drone_ids:
            telemetry = self._adapter.get_telemetry(drone_id)
            activity = FLIGHT_STATE_TO_ACTIVITY.get(
                telemetry.flight_state, DroneActivityState.IDLE,
            )
            if not telemetry.is_connected:
                activity = DroneActivityState.FAIL
            if activity == DroneActivityState.ACTIVE:
                active.append(drone_id)
            elif activity == DroneActivityState.FAIL:
                fail += 1
            else:
                idle += 1

        msg = SwarmGlobalState(
            active_drone_ids=tuple(active),
            total_drones=self._num_drones,
            active_count=len(active),
            idle_count=idle,
            fail_count=fail,
            timestamp_ms=int(time.monotonic() * 1000),
        )
        self._bus.publish_global_state(msg)

    # -----------------------------------------------------------------
    # Simulation Tick
    # -----------------------------------------------------------------

    def tick(self, dt_seconds: float = 1.0) -> None:
        """
        Advance simulation by one tick.

        Applies failure injection, updates telemetry, publishes state.
        No decision-making — pure state update.
        """
        self._tick_count += 1

        for drone_id in self._drone_ids:
            telemetry = self._adapter.get_telemetry(drone_id)

            failure_state = self._failure_injector.apply_failures(
                drone_id=drone_id,
                battery_pct=telemetry.battery_pct,
                position_lat=telemetry.position.latitude if telemetry.position else 0.0,
                position_lon=telemetry.position.longitude if telemetry.position else 0.0,
                position_alt=telemetry.position.altitude_m if telemetry.position else 0.0,
                dt_seconds=dt_seconds,
            )

            self._adapter.set_battery(drone_id, failure_state["battery_pct"])

            if not failure_state["link_available"]:
                self._adapter.set_connected(drone_id, False)
            else:
                self._adapter.set_connected(drone_id, True)

        self.publish_all_states()

    # -----------------------------------------------------------------
    # Mission Execution (Basic Sequence)
    # -----------------------------------------------------------------

    def execute_basic_mission(
        self,
        mission_id: str,
        waypoints: list[dict],
    ) -> list[ExecutionResult]:
        """
        Execute a basic mission: arm → takeoff → goto waypoints → land.

        Commands are issued via CommandSchema only.
        Returns list of ExecutionResults.
        """
        results: list[ExecutionResult] = []
        cmd_counter = 0

        for drone_id in self._drone_ids:
            cmd_counter += 1
            arm_cmd = CommandSchema(
                command_id=f"{mission_id}-arm-{drone_id}-{cmd_counter}",
                drone_id=drone_id,
                command_type=CommandType.ARM,
            )
            results.append(self.execute_command(arm_cmd))

            cmd_counter += 1
            takeoff_cmd = CommandSchema(
                command_id=f"{mission_id}-takeoff-{drone_id}-{cmd_counter}",
                drone_id=drone_id,
                command_type=CommandType.TAKEOFF,
                params={"altitude_m": 15.0},
            )
            results.append(self.execute_command(takeoff_cmd))

        for wp in waypoints:
            drone_id = wp.get("drone_id", self._drone_ids[0])
            if drone_id not in self._drone_ids:
                continue
            cmd_counter += 1
            goto_cmd = CommandSchema(
                command_id=f"{mission_id}-goto-{drone_id}-{cmd_counter}",
                drone_id=drone_id,
                command_type=CommandType.GOTO,
                params={
                    "latitude": wp.get("latitude", 0.0),
                    "longitude": wp.get("longitude", 0.0),
                    "altitude_m": wp.get("altitude_m", 15.0),
                },
            )
            results.append(self.execute_command(goto_cmd))

        for drone_id in self._drone_ids:
            cmd_counter += 1
            land_cmd = CommandSchema(
                command_id=f"{mission_id}-land-{drone_id}-{cmd_counter}",
                drone_id=drone_id,
                command_type=CommandType.LAND,
            )
            results.append(self.execute_command(land_cmd))

        return results

    # -----------------------------------------------------------------
    # Telemetry Access
    # -----------------------------------------------------------------

    def get_telemetry(self, drone_id: int) -> TelemetrySchema:
        """Get current telemetry for a drone."""
        return self._adapter.get_telemetry(drone_id)

    def get_all_telemetry(self) -> dict[int, TelemetrySchema]:
        """Get telemetry for all drones."""
        return {
            drone_id: self._adapter.get_telemetry(drone_id)
            for drone_id in self._drone_ids
        }
