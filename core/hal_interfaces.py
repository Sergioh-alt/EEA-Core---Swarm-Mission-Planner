"""
Phase 9.1 — Core HAL Interfaces.

Hardware-agnostic contracts between the Hive System (Phase 8) and
all hardware systems. Defines data schemas and the base drone
interface that every hardware adapter must implement.

HAL is strictly a Translation + Safety + Execution layer.
NO planning, optimization, allocation, scheduling, or decision-making.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("eea.hal")


# =========================================================================
# Command Schema — Standardized Command Format
# =========================================================================

class CommandType(Enum):
    """Hardware-agnostic command types."""
    ARM = "arm"
    DISARM = "disarm"
    TAKEOFF = "takeoff"
    LAND = "land"
    GOTO = "goto"
    RETURN_TO_HOME = "return_to_home"
    SET_SPEED = "set_speed"
    SPRAY_START = "spray_start"
    SPRAY_STOP = "spray_stop"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class CommandSchema:
    """
    Standardized command format for all hardware adapters.

    The command_type defines what to do; params carries
    hardware-agnostic parameters. The adapter translates
    these into hardware-specific protocol messages.
    """
    command_id: str
    drone_id: int
    command_type: CommandType
    params: dict = field(default_factory=dict)
    mission_id: Optional[str] = None
    sequence: int = 0

    def __post_init__(self) -> None:
        if not self.command_id:
            raise ValueError("command_id must not be empty")
        if self.drone_id < 0:
            raise ValueError("drone_id must be non-negative")


# =========================================================================
# Telemetry Schema — Standardized Telemetry Format
# =========================================================================

class FlightState(Enum):
    """Hardware-agnostic flight states."""
    GROUNDED = "grounded"
    ARMING = "arming"
    ARMED = "armed"
    TAKING_OFF = "taking_off"
    IN_FLIGHT = "in_flight"
    LANDING = "landing"
    RETURNING = "returning"
    EMERGENCY = "emergency"
    UNKNOWN = "unknown"


@dataclass
class GPSPosition:
    """Normalized GPS position."""
    latitude: float
    longitude: float
    altitude_m: float


@dataclass
class TelemetrySchema:
    """
    Standardized telemetry format from any hardware adapter.

    Adapters normalize hardware-specific telemetry into this
    common schema. HAL does not interpret the data — it only
    forwards it to Hive for state updates.
    """
    drone_id: int
    timestamp_ms: int
    flight_state: FlightState
    position: Optional[GPSPosition] = None
    battery_pct: Optional[float] = None
    speed_m_s: Optional[float] = None
    heading_deg: Optional[float] = None
    ground_altitude_m: Optional[float] = None
    satellite_count: Optional[int] = None
    signal_strength_pct: Optional[float] = None
    is_connected: bool = True
    raw_data: dict = field(default_factory=dict)


# =========================================================================
# Execution Result — Command Execution Outcome
# =========================================================================

class ExecutionStatus(Enum):
    """Outcome of a command execution."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    REJECTED = "rejected"
    SAFETY_OVERRIDE = "safety_override"


@dataclass
class ExecutionResult:
    """
    Result of executing a single command on hardware.

    The adapter produces this after attempting to translate and
    send a CommandSchema to the hardware. No retry or recovery
    logic — that is Hive's responsibility.
    """
    command_id: str
    drone_id: int
    status: ExecutionStatus
    message: str = ""
    telemetry: Optional[TelemetrySchema] = None
    error: Optional["HALError"] = None


# =========================================================================
# Error Model — Hardware-Agnostic Errors
# =========================================================================

class HALErrorCode(Enum):
    """Hardware-agnostic error codes."""
    COMMUNICATION_FAILURE = "communication_failure"
    COMMAND_REJECTED = "command_rejected"
    TIMEOUT = "timeout"
    INVALID_STATE = "invalid_state"
    HARDWARE_FAULT = "hardware_fault"
    GEOFENCE_VIOLATION = "geofence_violation"
    EMERGENCY_TRIGGERED = "emergency_triggered"
    ADAPTER_ERROR = "adapter_error"
    UNKNOWN = "unknown"


@dataclass
class HALError:
    """
    Hardware-agnostic error representation.

    Adapters translate hardware-specific errors into this common
    format so Hive can handle failures uniformly regardless of
    the underlying hardware platform.
    """
    code: HALErrorCode
    message: str
    drone_id: Optional[int] = None
    command_id: Optional[str] = None
    recoverable: bool = False
    raw_error: Optional[str] = None


# =========================================================================
# Base Drone Interface — Contract for All Adapters
# =========================================================================

class BaseDroneInterface(ABC):
    """
    Hardware-agnostic interface that every adapter must implement.

    Defines the contract between HAL and hardware. Each method
    translates a high-level operation into hardware-specific
    protocol calls. No planning, optimization, or decision-making.

    Methods:
        send_command — Translate and send a CommandSchema to hardware.
        get_telemetry — Read current telemetry from hardware.
        arm — Arm the drone motors.
        disarm — Disarm the drone motors.
        return_to_home — Command drone to return to launch point.
        is_connected — Check if hardware communication is active.
        get_adapter_name — Return the name of this adapter.
    """

    @abstractmethod
    def send_command(self, command: CommandSchema) -> ExecutionResult:
        """Translate and send a command to hardware."""

    @abstractmethod
    def get_telemetry(self, drone_id: int) -> TelemetrySchema:
        """Read current telemetry from the drone."""

    @abstractmethod
    def arm(self, drone_id: int) -> ExecutionResult:
        """Arm the drone. Returns execution result."""

    @abstractmethod
    def disarm(self, drone_id: int) -> ExecutionResult:
        """Disarm the drone. Returns execution result."""

    @abstractmethod
    def return_to_home(self, drone_id: int) -> ExecutionResult:
        """Command the drone to return to its launch point."""

    @abstractmethod
    def is_connected(self, drone_id: int) -> bool:
        """Check if the drone hardware is reachable."""

    @abstractmethod
    def get_adapter_name(self) -> str:
        """Return the name of this hardware adapter."""
