"""
Hive System — Core Foundation (Phase 8.1)

Multi-mission orchestration layer built on top of the existing
Phase 0–7 swarm pipeline. Hive orchestrates, it does not replace.

This module provides three structural primitives:

1. FleetRegistry — global drone registry with state tracking
2. MissionQueue — priority-based mission container
3. HiveState — central immutable system snapshot

Design principles:
- Orchestration only — no planning, scheduling, or optimization logic
- Deterministic — identical inputs produce identical outputs
- Opt-in — does not affect system behavior unless explicitly invoked
- Phase 0–7 systems remain unchanged and serve as the execution engine

See docs/architecture/phase8_design.md for full design specification.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from utils.logger import get_logger

logger = get_logger("hive")


# =========================================================================
# Fleet Registry
# =========================================================================

class DroneAvailability(Enum):
    """Drone availability states for fleet management."""
    IDLE = "idle"
    ACTIVE = "active"
    CHARGING = "charging"
    MAINTENANCE = "maintenance"


@dataclass
class FleetDrone:
    """A drone registered in the fleet."""
    drone_id: int
    availability: DroneAvailability = DroneAvailability.IDLE
    assigned_mission_id: Optional[str] = None
    battery_pct: float = 100.0
    notes: str = ""


class FleetRegistry:
    """
    Global registry of all drones in the system.

    Tracks drone states (idle / active / charging / maintenance)
    and exposes availability queries. Contains no allocation logic
    and no scheduling logic — purely a state registry.
    """

    def __init__(self) -> None:
        self._drones: dict[int, FleetDrone] = {}

    def register_drone(self, drone_id: int) -> FleetDrone:
        """Register a new drone in the fleet."""
        if drone_id in self._drones:
            raise ValueError(f"Drone {drone_id} already registered")
        drone = FleetDrone(drone_id=drone_id)
        self._drones[drone_id] = drone
        logger.info("Fleet: drone %d registered", drone_id)
        return drone

    def remove_drone(self, drone_id: int) -> None:
        """Remove a drone from the fleet."""
        if drone_id not in self._drones:
            raise ValueError(f"Drone {drone_id} not in fleet")
        del self._drones[drone_id]
        logger.info("Fleet: drone %d removed", drone_id)

    def get_drone(self, drone_id: int) -> FleetDrone:
        """Get a drone by ID."""
        if drone_id not in self._drones:
            raise ValueError(f"Drone {drone_id} not in fleet")
        return self._drones[drone_id]

    def update_drone(
        self,
        drone_id: int,
        availability: Optional[DroneAvailability] = None,
        assigned_mission_id: Optional[str] = None,
        battery_pct: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> FleetDrone:
        """Update a drone's state."""
        drone = self.get_drone(drone_id)
        if availability is not None:
            drone.availability = availability
        if assigned_mission_id is not None:
            drone.assigned_mission_id = assigned_mission_id
        if battery_pct is not None:
            drone.battery_pct = battery_pct
        if notes is not None:
            drone.notes = notes
        logger.info(
            "Fleet: drone %d updated — %s, mission=%s",
            drone_id, drone.availability.value, drone.assigned_mission_id,
        )
        return drone

    def get_available(self) -> list[FleetDrone]:
        """Return all drones with IDLE availability."""
        return [
            d for d in self._drones.values()
            if d.availability == DroneAvailability.IDLE
        ]

    def get_by_availability(self, status: DroneAvailability) -> list[FleetDrone]:
        """Return all drones with the given availability status."""
        return [
            d for d in self._drones.values()
            if d.availability == status
        ]

    def get_all(self) -> list[FleetDrone]:
        """Return all registered drones."""
        return list(self._drones.values())

    @property
    def fleet_size(self) -> int:
        """Total number of registered drones."""
        return len(self._drones)

    def fleet_health_snapshot(self) -> dict:
        """Return a summary of fleet health."""
        total = self.fleet_size
        by_status = {}
        for status in DroneAvailability:
            count = len(self.get_by_availability(status))
            by_status[status.value] = count
        avg_battery = (
            sum(d.battery_pct for d in self._drones.values()) / total
            if total > 0
            else 0.0
        )
        return {
            "total_drones": total,
            "by_status": by_status,
            "avg_battery_pct": round(avg_battery, 1),
        }


# =========================================================================
# Mission Queue
# =========================================================================

class MissionPriority(Enum):
    """Mission priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MissionStatus(Enum):
    """Mission lifecycle states within the Hive queue."""
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueuedMission:
    """A mission entry in the queue."""
    mission_id: str
    field_size_ha: float
    crop_type: str
    num_drones: int
    priority: MissionPriority = MissionPriority.NORMAL
    status: MissionStatus = MissionStatus.QUEUED
    wind_speed_kmh: float = 10.0
    temperature_c: float = 25.0
    notes: str = ""


class MissionQueue:
    """
    Priority-based mission container.

    Stores pending missions, provides deterministic priority ordering,
    and exposes the next mission for orchestration. Contains no
    execution logic and no optimization logic — purely a container.

    Ordering: higher MissionPriority value first, then insertion order
    (FIFO within same priority).
    """

    def __init__(self) -> None:
        self._missions: list[QueuedMission] = []

    def enqueue(self, mission: QueuedMission) -> None:
        """Add a mission to the queue."""
        if any(m.mission_id == mission.mission_id for m in self._missions):
            raise ValueError(f"Mission {mission.mission_id} already in queue")
        self._missions.append(mission)
        logger.info(
            "Queue: mission '%s' enqueued (priority=%s)",
            mission.mission_id, mission.priority.name,
        )

    def dequeue(self) -> Optional[QueuedMission]:
        """
        Remove and return the highest-priority QUEUED mission.

        Returns None if no queued missions exist.
        Ordering: highest priority first, then FIFO within same priority.
        """
        queued = [m for m in self._missions if m.status == MissionStatus.QUEUED]
        if not queued:
            return None
        # Sort by priority descending (highest first), stable sort preserves FIFO
        queued.sort(key=lambda m: m.priority.value, reverse=True)
        next_mission = queued[0]
        next_mission.status = MissionStatus.EXECUTING
        logger.info(
            "Queue: mission '%s' dequeued (priority=%s)",
            next_mission.mission_id, next_mission.priority.name,
        )
        return next_mission

    def peek(self) -> Optional[QueuedMission]:
        """Return the next mission without removing it."""
        queued = [m for m in self._missions if m.status == MissionStatus.QUEUED]
        if not queued:
            return None
        queued.sort(key=lambda m: m.priority.value, reverse=True)
        return queued[0]

    def cancel(self, mission_id: str) -> QueuedMission:
        """Cancel a queued mission."""
        for m in self._missions:
            if m.mission_id == mission_id:
                if m.status != MissionStatus.QUEUED:
                    raise ValueError(
                        f"Cannot cancel mission '{mission_id}' — "
                        f"status is {m.status.value}"
                    )
                m.status = MissionStatus.CANCELLED
                logger.info("Queue: mission '%s' cancelled", mission_id)
                return m
        raise ValueError(f"Mission '{mission_id}' not found in queue")

    def complete(self, mission_id: str) -> QueuedMission:
        """Mark an executing mission as completed."""
        for m in self._missions:
            if m.mission_id == mission_id:
                if m.status != MissionStatus.EXECUTING:
                    raise ValueError(
                        f"Cannot complete mission '{mission_id}' — "
                        f"status is {m.status.value}"
                    )
                m.status = MissionStatus.COMPLETED
                logger.info("Queue: mission '%s' completed", mission_id)
                return m
        raise ValueError(f"Mission '{mission_id}' not found in queue")

    def fail(self, mission_id: str) -> QueuedMission:
        """Mark an executing mission as failed."""
        for m in self._missions:
            if m.mission_id == mission_id:
                if m.status != MissionStatus.EXECUTING:
                    raise ValueError(
                        f"Cannot fail mission '{mission_id}' — "
                        f"status is {m.status.value}"
                    )
                m.status = MissionStatus.FAILED
                logger.info("Queue: mission '%s' failed", mission_id)
                return m
        raise ValueError(f"Mission '{mission_id}' not found in queue")

    def get_mission(self, mission_id: str) -> QueuedMission:
        """Get a mission by ID."""
        for m in self._missions:
            if m.mission_id == mission_id:
                return m
        raise ValueError(f"Mission '{mission_id}' not found in queue")

    def get_by_status(self, status: MissionStatus) -> list[QueuedMission]:
        """Return all missions with the given status."""
        return [m for m in self._missions if m.status == status]

    @property
    def pending_count(self) -> int:
        """Number of queued missions."""
        return len(self.get_by_status(MissionStatus.QUEUED))

    @property
    def total_count(self) -> int:
        """Total number of missions in the queue."""
        return len(self._missions)


# =========================================================================
# Hive State
# =========================================================================

@dataclass
class HiveState:
    """
    Central immutable system snapshot.

    Provides a read-heavy, deterministic snapshot of the entire
    Hive system state at a point in time. Used for observability
    and system-level queries. Does not make decisions.
    """
    fleet_size: int
    fleet_health: dict
    missions_queued: int
    missions_executing: int
    missions_completed: int
    missions_failed: int
    missions_cancelled: int
    total_missions: int
    system_status: str


def build_hive_state(
    fleet: FleetRegistry,
    queue: MissionQueue,
) -> HiveState:
    """
    Build an immutable snapshot of the current Hive system state.

    This is a read-only operation that aggregates data from the
    FleetRegistry and MissionQueue into a single HiveState object.
    """
    queued = len(queue.get_by_status(MissionStatus.QUEUED))
    executing = len(queue.get_by_status(MissionStatus.EXECUTING))
    completed = len(queue.get_by_status(MissionStatus.COMPLETED))
    failed = len(queue.get_by_status(MissionStatus.FAILED))
    cancelled = len(queue.get_by_status(MissionStatus.CANCELLED))

    # Determine system status
    if fleet.fleet_size == 0:
        system_status = "no_fleet"
    elif executing > 0:
        system_status = "active"
    elif queued > 0:
        system_status = "ready"
    else:
        system_status = "idle"

    state = HiveState(
        fleet_size=fleet.fleet_size,
        fleet_health=fleet.fleet_health_snapshot(),
        missions_queued=queued,
        missions_executing=executing,
        missions_completed=completed,
        missions_failed=failed,
        missions_cancelled=cancelled,
        total_missions=queue.total_count,
        system_status=system_status,
    )

    logger.info(
        "HiveState: fleet=%d, queued=%d, executing=%d, status=%s",
        state.fleet_size, queued, executing, system_status,
    )
    return state
