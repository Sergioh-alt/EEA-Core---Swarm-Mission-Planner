"""
Phase 10B — Digital Twin State Models.

Immutable state models representing the complete swarm truth.
All models are frozen dataclasses — no mutation allowed.

Architecture rules:
- Pure data — no logic
- No planning information
- No future commands
- No optimizer outputs
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =========================================================================
# Enumerations
# =========================================================================

class MissionStatus(Enum):
    """Mission lifecycle status."""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class DroneMode(Enum):
    """Drone operational mode."""
    STANDBY = "STANDBY"
    MANUAL = "MANUAL"
    GUIDED = "GUIDED"
    AUTO = "AUTO"
    RTL = "RTL"
    LAND = "LAND"


class HealthLevel(Enum):
    """System health level."""
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class TaskState(Enum):
    """Current task state (read-only, no planning)."""
    NONE = "NONE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FailureCategory(Enum):
    """Active failure categories."""
    BATTERY_DEGRADATION = "battery_degradation"
    GPS_LOSS = "gps_loss"
    LINK_LOSS = "link_loss"
    WIND_DISTURBANCE = "wind_disturbance"


class EnvironmentCondition(Enum):
    """Environment condition."""
    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    SEVERE = "SEVERE"


# =========================================================================
# Position & Velocity (immutable sub-models)
# =========================================================================

@dataclass(frozen=True)
class Position:
    """3D geographic position."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0


@dataclass(frozen=True)
class Velocity:
    """3D velocity vector."""
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0


# =========================================================================
# DroneState Model
# =========================================================================

@dataclass(frozen=True)
class DroneState:
    """
    Complete drone state in the Digital Twin.

    Contains:
    - drone_id
    - armed
    - mode
    - position, velocity, heading
    - battery
    - gps, communication
    - health
    - current_task (state only)
    - last_update

    No planning information. No future commands. No optimizer outputs.
    """
    drone_id: int
    armed: bool = False
    mode: DroneMode = DroneMode.STANDBY
    position: Position = field(default_factory=Position)
    velocity: Velocity = field(default_factory=Velocity)
    heading_deg: float = 0.0
    battery_pct: float = 100.0
    battery_voltage: float = 12.6
    gps_available: bool = True
    gps_accuracy_m: float = 1.0
    communication_active: bool = True
    health: HealthLevel = HealthLevel.OK
    current_task: TaskState = TaskState.NONE
    last_update_ms: int = 0


# =========================================================================
# EnvironmentState Model
# =========================================================================

@dataclass(frozen=True)
class EnvironmentState:
    """Environmental conditions affecting the swarm."""
    wind_speed_m_s: float = 0.0
    wind_direction_deg: float = 0.0
    condition: EnvironmentCondition = EnvironmentCondition.NOMINAL
    timestamp_ms: int = 0


# =========================================================================
# SwarmState Model (Single Source of Truth)
# =========================================================================

@dataclass(frozen=True)
class SwarmState:
    """
    Complete swarm state — Single Source of Truth.

    Contains:
    - swarm_id
    - timestamp
    - mission_state
    - simulation_time
    - drone_states
    - global_health
    - active_failures
    - environment_state

    Immutable. Any update produces a new SwarmState instance.
    """
    swarm_id: str = "swarm-default"
    timestamp_ms: int = 0
    mission_status: MissionStatus = MissionStatus.IDLE
    mission_id: Optional[str] = None
    simulation_time_ms: int = 0
    drone_states: tuple[DroneState, ...] = ()
    global_health: HealthLevel = HealthLevel.OK
    active_failures: tuple[FailureCategory, ...] = ()
    environment_state: EnvironmentState = field(default_factory=EnvironmentState)
    total_drones: int = 0
    active_drones: int = 0
    failed_drones: int = 0
    version: int = 0


# =========================================================================
# State Update Messages (input to sync engine)
# =========================================================================

@dataclass(frozen=True)
class DroneStateUpdate:
    """An incoming state update for a single drone (from ROS2 bus)."""
    drone_id: int
    timestamp_ms: int
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    velocity_z: float = 0.0
    battery_pct: float = 100.0
    battery_voltage: float = 12.6
    armed: bool = False
    mode: str = "STANDBY"
    gps_available: bool = True
    gps_accuracy_m: float = 1.0
    communication_active: bool = True
    health: str = "OK"
    current_task: str = "NONE"


@dataclass(frozen=True)
class SwarmStateUpdate:
    """An incoming global state update (from ROS2 bus)."""
    timestamp_ms: int
    mission_id: Optional[str] = None
    active_drone_ids: tuple[int, ...] = ()
    total_drones: int = 0
    active_count: int = 0
    fail_count: int = 0
    coverage_pct: float = 0.0
