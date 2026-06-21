"""
Fleet Manager (Phase 8.3)

Drone-level fleet awareness and assignment tracking across missions.
This module manages the mapping between drones and missions, tracks
drone state transitions, and provides fleet-wide assignment queries.

This is a state tracking layer only — it does NOT perform:
- scheduling logic
- optimization logic
- decision-making (does not select or infer optimal assignments)
- resource balancing across missions
- mission planning

Components:
- DroneStatusTracker: extended state tracking with transition history
- DroneAllocationManager: mission-to-drone assignment tracking
- FleetStateUpdater: batch state updates for fleet-wide transitions

See docs/architecture/phase8_design.md (Phase 8.3) for design spec.
"""

from dataclasses import dataclass
from typing import Optional

from core.hive import FleetRegistry, FleetDrone, DroneAvailability
from utils.logger import get_logger

logger = get_logger("fleet_manager")


# =========================================================================
# Drone Status Tracker
# =========================================================================

@dataclass
class StateTransition:
    """Record of a drone state transition."""
    drone_id: int
    from_state: DroneAvailability
    to_state: DroneAvailability
    reason: str


class DroneStatusTracker:
    """
    Extended drone state tracking with transition history.

    Wraps FleetRegistry to add transition logging and validation.
    Does not make scheduling or allocation decisions — purely
    records and queries state transitions.
    """

    def __init__(self, fleet: FleetRegistry) -> None:
        self._fleet = fleet
        self._history: list[StateTransition] = []

    def transition(
        self,
        drone_id: int,
        to_state: DroneAvailability,
        reason: str = "",
    ) -> FleetDrone:
        """
        Transition a drone to a new state and record the change.

        Validates that the drone exists and records the transition
        in history. No decision-making — caller determines the
        target state.
        """
        drone = self._fleet.get_drone(drone_id)
        from_state = drone.availability

        if from_state == to_state:
            return drone

        transition = StateTransition(
            drone_id=drone_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
        )
        self._history.append(transition)

        self._fleet.update_drone(drone_id, availability=to_state)

        logger.info(
            "StatusTracker: drone %d %s → %s (%s)",
            drone_id, from_state.value, to_state.value, reason,
        )
        return self._fleet.get_drone(drone_id)

    def get_history(self, drone_id: Optional[int] = None) -> list[StateTransition]:
        """Return transition history, optionally filtered by drone."""
        if drone_id is not None:
            return [t for t in self._history if t.drone_id == drone_id]
        return list(self._history)

    def get_current_state(self, drone_id: int) -> DroneAvailability:
        """Return a drone's current availability state."""
        return self._fleet.get_drone(drone_id).availability

    @property
    def transition_count(self) -> int:
        """Total number of recorded transitions."""
        return len(self._history)


# =========================================================================
# Drone Allocation Manager
# =========================================================================

@dataclass
class DroneAssignment:
    """Record of a drone assigned to a mission."""
    drone_id: int
    mission_id: str


class DroneAllocationManager:
    """
    Mission-to-drone assignment tracking.

    Maintains the mapping between drones and missions. Tracks which
    drones are assigned to which mission. Does NOT select or infer
    optimal assignments — the caller explicitly assigns drones.

    No scheduling logic. No optimization logic. No decision-making.
    """

    def __init__(self, fleet: FleetRegistry) -> None:
        self._fleet = fleet
        self._assignments: list[DroneAssignment] = []

    def assign_drone(self, drone_id: int, mission_id: str) -> DroneAssignment:
        """
        Record a drone assignment to a mission.

        Validates the drone exists and is IDLE. Updates the FleetRegistry
        to reflect the assignment. The caller decides which drone to
        assign — this method only records the assignment.
        """
        drone = self._fleet.get_drone(drone_id)

        if drone.availability != DroneAvailability.IDLE:
            raise ValueError(
                f"Drone {drone_id} is not available "
                f"(current state: {drone.availability.value})"
            )

        # Check not already assigned to this mission
        for a in self._assignments:
            if a.drone_id == drone_id and a.mission_id == mission_id:
                raise ValueError(
                    f"Drone {drone_id} already assigned to mission '{mission_id}'"
                )

        assignment = DroneAssignment(drone_id=drone_id, mission_id=mission_id)
        self._assignments.append(assignment)

        self._fleet.update_drone(
            drone_id,
            availability=DroneAvailability.ACTIVE,
            assigned_mission_id=mission_id,
        )

        logger.info(
            "Allocation: drone %d assigned to mission '%s'",
            drone_id, mission_id,
        )
        return assignment

    def release_drone(self, drone_id: int, mission_id: str) -> None:
        """
        Release a drone from a mission assignment.

        Removes the assignment record and sets the drone back to IDLE.
        """
        found = False
        for i, a in enumerate(self._assignments):
            if a.drone_id == drone_id and a.mission_id == mission_id:
                self._assignments.pop(i)
                found = True
                break

        if not found:
            raise ValueError(
                f"Drone {drone_id} is not assigned to mission '{mission_id}'"
            )

        drone = self._fleet.get_drone(drone_id)
        drone.availability = DroneAvailability.IDLE
        drone.assigned_mission_id = None

        logger.info(
            "Allocation: drone %d released from mission '%s'",
            drone_id, mission_id,
        )

    def get_mission_drones(self, mission_id: str) -> list[int]:
        """Return all drone IDs assigned to a mission."""
        return [a.drone_id for a in self._assignments if a.mission_id == mission_id]

    def get_drone_mission(self, drone_id: int) -> Optional[str]:
        """Return the mission ID a drone is assigned to, or None."""
        for a in self._assignments:
            if a.drone_id == drone_id:
                return a.mission_id
        return None

    def get_all_assignments(self) -> list[DroneAssignment]:
        """Return all current assignments."""
        return list(self._assignments)

    @property
    def active_assignment_count(self) -> int:
        """Number of active drone-mission assignments."""
        return len(self._assignments)


# =========================================================================
# Fleet State Updater
# =========================================================================

class FleetStateUpdater:
    """
    Batch state updates for fleet-wide transitions.

    Provides convenience methods for common fleet-wide state changes
    (e.g., release all drones from a completed mission, set drones
    to maintenance). Does NOT make scheduling or optimization decisions.
    """

    def __init__(
        self,
        fleet: FleetRegistry,
        tracker: DroneStatusTracker,
        allocator: DroneAllocationManager,
    ) -> None:
        self._fleet = fleet
        self._tracker = tracker
        self._allocator = allocator

    def release_mission_drones(self, mission_id: str) -> list[int]:
        """
        Release all drones assigned to a completed mission.

        Sets each drone back to IDLE and removes assignments.
        Returns the list of released drone IDs.
        """
        drone_ids = self._allocator.get_mission_drones(mission_id)
        released: list[int] = []

        for drone_id in drone_ids:
            self._allocator.release_drone(drone_id, mission_id)
            self._tracker.transition(
                drone_id,
                DroneAvailability.IDLE,
                reason=f"mission '{mission_id}' completed",
            )
            released.append(drone_id)

        logger.info(
            "FleetUpdater: released %d drones from mission '%s'",
            len(released), mission_id,
        )
        return released

    def set_drones_maintenance(
        self,
        drone_ids: list[int],
        reason: str = "scheduled maintenance",
    ) -> list[int]:
        """
        Set a list of drones to MAINTENANCE state.

        Only transitions IDLE drones. Returns the list of drones
        that were successfully transitioned.
        """
        transitioned: list[int] = []
        for drone_id in drone_ids:
            drone = self._fleet.get_drone(drone_id)
            if drone.availability == DroneAvailability.IDLE:
                self._tracker.transition(
                    drone_id, DroneAvailability.MAINTENANCE, reason=reason,
                )
                transitioned.append(drone_id)

        logger.info(
            "FleetUpdater: %d/%d drones set to maintenance",
            len(transitioned), len(drone_ids),
        )
        return transitioned

    def set_drones_charging(
        self,
        drone_ids: list[int],
        reason: str = "battery low",
    ) -> list[int]:
        """
        Set a list of drones to CHARGING state.

        Only transitions IDLE drones. Returns the list of drones
        that were successfully transitioned.
        """
        transitioned: list[int] = []
        for drone_id in drone_ids:
            drone = self._fleet.get_drone(drone_id)
            if drone.availability == DroneAvailability.IDLE:
                self._tracker.transition(
                    drone_id, DroneAvailability.CHARGING, reason=reason,
                )
                transitioned.append(drone_id)

        logger.info(
            "FleetUpdater: %d/%d drones set to charging",
            len(transitioned), len(drone_ids),
        )
        return transitioned

    def return_drones_idle(
        self,
        drone_ids: list[int],
        reason: str = "ready for service",
    ) -> list[int]:
        """
        Return drones to IDLE state from CHARGING or MAINTENANCE.

        Only transitions drones in CHARGING or MAINTENANCE state.
        Returns the list of drones that were transitioned.
        """
        transitioned: list[int] = []
        for drone_id in drone_ids:
            drone = self._fleet.get_drone(drone_id)
            if drone.availability in (
                DroneAvailability.CHARGING,
                DroneAvailability.MAINTENANCE,
            ):
                self._tracker.transition(
                    drone_id, DroneAvailability.IDLE, reason=reason,
                )
                transitioned.append(drone_id)

        logger.info(
            "FleetUpdater: %d/%d drones returned to idle",
            len(transitioned), len(drone_ids),
        )
        return transitioned

    def fleet_assignment_summary(self) -> dict:
        """
        Return a summary of fleet assignment state.

        Read-only snapshot of current fleet assignment distribution.
        """
        assignments = self._allocator.get_all_assignments()
        missions: dict[str, list[int]] = {}
        for a in assignments:
            missions.setdefault(a.mission_id, []).append(a.drone_id)

        return {
            "total_drones": self._fleet.fleet_size,
            "idle": len(self._fleet.get_available()),
            "active_assignments": self._allocator.active_assignment_count,
            "missions": {
                mid: {"drone_ids": drones, "count": len(drones)}
                for mid, drones in missions.items()
            },
            "by_status": {
                status.value: len(self._fleet.get_by_availability(status))
                for status in DroneAvailability
            },
        }
