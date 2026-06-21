"""
Swarm State Manager (Phase 7.1)

Central state registry for all drones and the mission. Provides
read/write access to drone states, mission progress, and failure
detection. This module is purely additive — it does not modify any
existing pipeline module.

The SwarmStateManager is initialized from existing pipeline outputs
(MissionProfile, SwarmPlan, RoutePlan) and provides a live view
of the mission state that Phase 7.2+ modules will consume.

Consumers: ReallocationEngine (7.2), MissionAdapter (7.3),
           SwarmOptimizer (7.4), UI dashboard (future)
Dependencies: MissionProfile, SwarmPlan, RoutePlan (all existing)
"""

from dataclasses import dataclass, field
from enum import Enum

from core.mission_intake import MissionProfile
from core.swarm_planner import SwarmPlan
from core.route_planner import RoutePlan, DroneRoute
from utils.logger import get_logger

logger = get_logger("swarm_state")


class DroneStatus(Enum):
    """Lifecycle states for a single drone."""
    IDLE = "idle"
    LAUNCHING = "launching"
    ACTIVE = "active"
    REFILLING = "refilling"
    SWAPPING_BATTERY = "swapping_battery"
    RETURNING = "returning"
    COMPLETED = "completed"
    FAILED = "failed"


class MissionStatus(Enum):
    """Lifecycle states for the overall mission."""
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETING = "completing"
    DONE = "done"
    ABORTED = "aborted"


@dataclass
class DroneState:
    """Snapshot of a single drone's operational state."""
    drone_id: int
    status: DroneStatus
    current_sector_id: int
    battery_remaining_pct: float
    liquid_remaining_l: float
    position: tuple[float, float]
    flight_time_elapsed_min: float
    passes_completed: int
    passes_total: int


@dataclass
class FailureEvent:
    """Record of a drone failure occurrence."""
    drone_id: int
    reason: str
    timestamp_min: float
    sector_id: int
    passes_completed: int
    passes_remaining: int


@dataclass
class MissionState:
    """Snapshot of the overall mission state."""
    status: MissionStatus
    start_time_min: float
    elapsed_min: float
    drones: list[DroneState]
    sectors_completed: list[int]
    sectors_remaining: list[int]
    coverage_pct: float
    active_alerts: list[str]
    failure_log: list[FailureEvent] = field(default_factory=list)


class SwarmStateManager:
    """
    Central state registry for all drones and the mission.

    Initialized from existing pipeline outputs. Provides query and
    update methods for drone states, mission progress tracking,
    and failure detection.
    """

    def __init__(
        self,
        profile: MissionProfile,
        swarm: SwarmPlan,
        routes: RoutePlan,
    ) -> None:
        self._profile = profile
        self._swarm = swarm
        self._routes = routes

        self._route_map: dict[int, DroneRoute] = {
            r.drone_id: r for r in routes.routes
        }

        self._drones: dict[int, DroneState] = {}
        for sector in swarm.sectors:
            route = self._route_map.get(sector.drone_id)
            passes_total = route.num_passes if route else 0
            start_pos = (sector.x_start, sector.y_start)

            self._drones[sector.drone_id] = DroneState(
                drone_id=sector.drone_id,
                status=DroneStatus.IDLE,
                current_sector_id=sector.id,
                battery_remaining_pct=100.0,
                liquid_remaining_l=profile.liquid_capacity_l,
                position=start_pos,
                flight_time_elapsed_min=0.0,
                passes_completed=0,
                passes_total=passes_total,
            )

        self._mission_status = MissionStatus.PLANNING
        self._elapsed_min = 0.0
        self._failure_log: list[FailureEvent] = []
        self._alerts: list[str] = []

        logger.info(
            "SwarmStateManager initialized: %d drones, %d sectors",
            len(self._drones), len(swarm.sectors),
        )

    def get_state(self) -> MissionState:
        """Return a snapshot of the current mission state."""
        drones = list(self._drones.values())

        total_passes = sum(d.passes_total for d in drones)
        completed_passes = sum(d.passes_completed for d in drones)
        coverage_pct = (completed_passes / total_passes * 100) if total_passes > 0 else 0.0

        sectors_completed = [
            d.current_sector_id for d in drones
            if d.status == DroneStatus.COMPLETED
        ]
        all_sector_ids = [s.id for s in self._swarm.sectors]
        sectors_remaining = [
            sid for sid in all_sector_ids
            if sid not in sectors_completed
        ]

        return MissionState(
            status=self._mission_status,
            start_time_min=0.0,
            elapsed_min=self._elapsed_min,
            drones=drones,
            sectors_completed=sectors_completed,
            sectors_remaining=sectors_remaining,
            coverage_pct=round(coverage_pct, 1),
            active_alerts=list(self._alerts),
            failure_log=list(self._failure_log),
        )

    def get_drone(self, drone_id: int) -> DroneState:
        """Get state for a specific drone."""
        if drone_id not in self._drones:
            raise ValueError(f"Drone {drone_id} not found in swarm")
        return self._drones[drone_id]

    def update_drone(self, drone_id: int, **kwargs: object) -> None:
        """
        Update drone state fields.

        Accepts any DroneState field as a keyword argument:
        status, battery_remaining_pct, liquid_remaining_l,
        position, flight_time_elapsed_min, passes_completed, etc.
        """
        drone = self.get_drone(drone_id)

        valid_fields = {f.name for f in drone.__dataclass_fields__.values()}
        for key, value in kwargs.items():
            if key == "drone_id":
                continue
            if key not in valid_fields:
                raise ValueError(f"Invalid DroneState field: {key}")
            setattr(drone, key, value)

        logger.info(
            "Drone %d updated: %s",
            drone_id, ", ".join(f"{k}={v}" for k, v in kwargs.items()),
        )

    def mark_drone_failed(self, drone_id: int, reason: str) -> FailureEvent:
        """
        Mark a drone as failed and log the failure event.

        Returns the FailureEvent for downstream consumption
        (e.g., by ReallocationEngine in Phase 7.2).
        """
        drone = self.get_drone(drone_id)
        passes_remaining = drone.passes_total - drone.passes_completed

        event = FailureEvent(
            drone_id=drone_id,
            reason=reason,
            timestamp_min=self._elapsed_min,
            sector_id=drone.current_sector_id,
            passes_completed=drone.passes_completed,
            passes_remaining=passes_remaining,
        )

        drone.status = DroneStatus.FAILED
        self._failure_log.append(event)

        alert = f"Drone {drone_id} FAILED: {reason} (sector {drone.current_sector_id}, {passes_remaining} passes remaining)"
        self._alerts.append(alert)

        logger.warning(
            "Drone %d failed: %s (sector %d, %d passes remaining)",
            drone_id, reason, drone.current_sector_id, passes_remaining,
        )

        return event

    def get_available_drones(self) -> list[DroneState]:
        """Return drones that can accept additional work."""
        available_statuses = {
            DroneStatus.IDLE,
            DroneStatus.ACTIVE,
            DroneStatus.COMPLETED,
        }
        return [
            d for d in self._drones.values()
            if d.status in available_statuses
        ]

    def get_failed_drones(self) -> list[DroneState]:
        """Return all drones in FAILED state."""
        return [
            d for d in self._drones.values()
            if d.status == DroneStatus.FAILED
        ]

    def update_elapsed_time(self, elapsed_min: float) -> None:
        """Update the mission elapsed time."""
        self._elapsed_min = elapsed_min

    def set_mission_status(self, status: MissionStatus) -> None:
        """Update overall mission status."""
        old = self._mission_status
        self._mission_status = status
        logger.info("Mission status: %s → %s", old.value, status.value)

    def add_alert(self, alert: str) -> None:
        """Add a mission alert."""
        self._alerts.append(alert)
        logger.warning("Alert: %s", alert)

    def clear_alerts(self) -> None:
        """Clear all active alerts."""
        self._alerts.clear()

    @property
    def drone_count(self) -> int:
        """Total number of drones in the swarm."""
        return len(self._drones)

    @property
    def active_drone_count(self) -> int:
        """Number of drones currently active."""
        return sum(
            1 for d in self._drones.values()
            if d.status == DroneStatus.ACTIVE
        )

    @property
    def failed_drone_count(self) -> int:
        """Number of drones in FAILED state."""
        return sum(
            1 for d in self._drones.values()
            if d.status == DroneStatus.FAILED
        )
