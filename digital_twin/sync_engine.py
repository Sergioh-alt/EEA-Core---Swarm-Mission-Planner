"""
Phase 10B — Sync Engine.

Consumes ROS2 state updates and produces immutable SwarmState.
Priority order for reconciliation:
1. HAL real telemetry (highest priority)
2. Simulation telemetry
3. Hive predicted state

Architecture rules:
- Receive state updates ONLY
- Merge updates into unified state
- Validate consistency
- Publish immutable Digital Twin state
- NO decision-making
- NO scheduling
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, replace
from typing import Optional

from digital_twin.state_models import (
    DroneMode,
    DroneState,
    DroneStateUpdate,
    EnvironmentCondition,
    EnvironmentState,
    FailureCategory,
    HealthLevel,
    MissionStatus,
    Position,
    SwarmState,
    SwarmStateUpdate,
    TaskState,
    Velocity,
)
from digital_twin.state_validation import StateValidator, ValidationResult

logger = logging.getLogger("eea.digital_twin.sync_engine")


# =========================================================================
# Sync Event Types
# =========================================================================

@dataclass(frozen=True)
class SyncEvent:
    """Record of a synchronization event."""
    timestamp_ms: int
    event_type: str
    drone_id: Optional[int] = None
    description: str = ""


# =========================================================================
# Sync Engine
# =========================================================================

class SyncEngine:
    """
    Synchronization engine for the Digital Twin.

    Consumes state updates from ROS2 bus, validates them,
    and maintains the single source of truth SwarmState.

    NO decision-making. NO scheduling. State merge only.
    """

    def __init__(self, swarm_id: str = "swarm-default") -> None:
        self._swarm_id = swarm_id
        self._validator = StateValidator()
        self._lock = threading.RLock()
        self._version: int = 0

        # Internal mutable tracking (produces immutable outputs)
        self._drone_states: dict[int, DroneState] = {}
        self._mission_status = MissionStatus.IDLE
        self._mission_id: Optional[str] = None
        self._active_failures: list[FailureCategory] = []
        self._environment = EnvironmentState()
        self._simulation_time_ms: int = 0

        # Sync event log
        self._sync_events: list[SyncEvent] = []

        logger.info("SyncEngine: initialized for swarm '%s'", swarm_id)

    @property
    def version(self) -> int:
        """Current state version (increments on each update)."""
        return self._version

    @property
    def sync_events(self) -> list[SyncEvent]:
        """Log of sync events."""
        return list(self._sync_events)

    def apply_drone_update(self, update: DroneStateUpdate) -> ValidationResult:
        """
        Apply a drone state update from ROS2 bus.

        Validates the update, then merges into current state.
        Returns validation result.
        """
        with self._lock:
            current = self._drone_states.get(update.drone_id)
            result = self._validator.validate_drone_update(update, current)

            if not result.valid:
                self._sync_events.append(SyncEvent(
                    timestamp_ms=update.timestamp_ms,
                    event_type="DRONE_UPDATE_REJECTED",
                    drone_id=update.drone_id,
                    description=f"Validation failed: {result.details}",
                ))
                return result

            # Convert update to DroneState
            mode = _parse_drone_mode(update.mode)
            health = _parse_health_level(update.health)
            task = _parse_task_state(update.current_task)

            new_state = DroneState(
                drone_id=update.drone_id,
                armed=update.armed,
                mode=mode,
                position=Position(
                    latitude=update.latitude,
                    longitude=update.longitude,
                    altitude_m=update.altitude_m,
                ),
                velocity=Velocity(
                    vx=update.velocity_x,
                    vy=update.velocity_y,
                    vz=update.velocity_z,
                ),
                battery_pct=update.battery_pct,
                battery_voltage=update.battery_voltage,
                gps_available=update.gps_available,
                gps_accuracy_m=update.gps_accuracy_m,
                communication_active=update.communication_active,
                health=health,
                current_task=task,
                last_update_ms=update.timestamp_ms,
            )

            self._drone_states[update.drone_id] = new_state
            self._version += 1

            self._sync_events.append(SyncEvent(
                timestamp_ms=update.timestamp_ms,
                event_type="DRONE_STATE_SYNCED",
                drone_id=update.drone_id,
                description=f"v{self._version}",
            ))

            return result

    def apply_swarm_update(self, update: SwarmStateUpdate) -> ValidationResult:
        """
        Apply a swarm-level state update.

        Validates and merges global state information.
        """
        with self._lock:
            current = self.get_swarm_state()
            result = self._validator.validate_swarm_update(update, current)

            if not result.valid:
                self._sync_events.append(SyncEvent(
                    timestamp_ms=update.timestamp_ms,
                    event_type="SWARM_UPDATE_REJECTED",
                    description=f"Validation failed: {result.details}",
                ))
                return result

            if update.mission_id:
                self._mission_id = update.mission_id
                self._mission_status = MissionStatus.RUNNING

            self._simulation_time_ms = update.timestamp_ms
            self._version += 1

            self._sync_events.append(SyncEvent(
                timestamp_ms=update.timestamp_ms,
                event_type="SWARM_STATE_SYNCED",
                description=f"v{self._version} drones={update.total_drones}",
            ))

            return result

    def apply_failure_update(
        self, failures: list[FailureCategory],
    ) -> None:
        """Update active failure list from simulation layer."""
        with self._lock:
            self._active_failures = list(failures)
            self._version += 1

    def apply_environment_update(
        self,
        wind_speed_m_s: float = 0.0,
        wind_direction_deg: float = 0.0,
        condition: EnvironmentCondition = EnvironmentCondition.NOMINAL,
    ) -> None:
        """Update environment state."""
        with self._lock:
            self._environment = EnvironmentState(
                wind_speed_m_s=wind_speed_m_s,
                wind_direction_deg=wind_direction_deg,
                condition=condition,
                timestamp_ms=int(time.monotonic() * 1000),
            )
            self._version += 1

    def register_drone(self, drone_id: int) -> None:
        """Register a drone in the Digital Twin."""
        with self._lock:
            if drone_id not in self._drone_states:
                self._drone_states[drone_id] = DroneState(
                    drone_id=drone_id,
                    last_update_ms=0,
                )
                self._version += 1
                logger.info("SyncEngine: registered drone %d", drone_id)

    def get_swarm_state(self) -> SwarmState:
        """
        Get the current immutable SwarmState.

        This is the single source of truth — always consistent,
        always immutable.
        """
        with self._lock:
            drones = tuple(
                self._drone_states[k]
                for k in sorted(self._drone_states.keys())
            )

            # Compute health
            global_health = _compute_global_health(drones)

            # Count active/failed
            active = sum(
                1 for d in drones
                if d.communication_active and d.armed
            )
            failed = sum(
                1 for d in drones
                if not d.communication_active or d.health == HealthLevel.CRITICAL
            )

            return SwarmState(
                swarm_id=self._swarm_id,
                timestamp_ms=int(time.monotonic() * 1000),
                mission_status=self._mission_status,
                mission_id=self._mission_id,
                simulation_time_ms=self._simulation_time_ms,
                drone_states=drones,
                global_health=global_health,
                active_failures=tuple(self._active_failures),
                environment_state=self._environment,
                total_drones=len(drones),
                active_drones=active,
                failed_drones=failed,
                version=self._version,
            )

    def get_drone_state(self, drone_id: int) -> Optional[DroneState]:
        """Get current state of a specific drone."""
        with self._lock:
            return self._drone_states.get(drone_id)


# =========================================================================
# Internal Helpers (pure functions, no side effects)
# =========================================================================

def _parse_drone_mode(mode_str: str) -> DroneMode:
    """Parse mode string to enum."""
    try:
        return DroneMode(mode_str)
    except ValueError:
        return DroneMode.STANDBY


def _parse_health_level(health_str: str) -> HealthLevel:
    """Parse health string to enum."""
    try:
        return HealthLevel(health_str)
    except ValueError:
        return HealthLevel.OK


def _parse_task_state(task_str: str) -> TaskState:
    """Parse task state string to enum."""
    try:
        return TaskState(task_str)
    except ValueError:
        return TaskState.NONE


def _compute_global_health(drones: tuple[DroneState, ...]) -> HealthLevel:
    """Compute global health from individual drone states."""
    if not drones:
        return HealthLevel.OK

    if any(d.health == HealthLevel.CRITICAL for d in drones):
        return HealthLevel.CRITICAL
    if any(d.health == HealthLevel.WARNING for d in drones):
        return HealthLevel.WARNING
    return HealthLevel.OK
