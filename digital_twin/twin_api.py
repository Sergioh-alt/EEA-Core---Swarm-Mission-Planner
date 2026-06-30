"""
Phase 10B — Digital Twin API.

Read-only API exposing the Digital Twin state.
No write operations from external layers.

Available methods:
- get_swarm_state()
- get_drone_state(drone_id)
- get_snapshot(snapshot_id)
- list_snapshots()
- replay_timeline(...)
- replay_drone(...)

Architecture rules:
- ALL methods are READ-ONLY
- No state mutation through API
- No command generation
- No decision-making
- External layers cannot write to Digital Twin
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from digital_twin.state_models import (
    DroneState,
    DroneStateUpdate,
    EnvironmentCondition,
    FailureCategory,
    SwarmState,
    SwarmStateUpdate,
)
from digital_twin.sync_engine import SyncEngine
from digital_twin.snapshot_engine import Snapshot, SnapshotEngine
from digital_twin.replay_engine import (
    DroneReplayTimeline,
    ReplayEngine,
    ReplayTimeline,
)
from digital_twin.state_validation import StateValidator, ValidationResult

logger = logging.getLogger("eea.digital_twin.api")


class DigitalTwin:
    """
    Digital Twin — Single Source of Truth API.

    The unified interface for all Digital Twin operations.
    External layers interact with the Digital Twin ONLY through this class.

    READ-ONLY for consumers. State is updated only through
    internal sync from Simulation/ROS2 layer.
    """

    def __init__(self, swarm_id: str = "swarm-default") -> None:
        self._sync_engine = SyncEngine(swarm_id=swarm_id)
        self._snapshot_engine = SnapshotEngine()
        self._replay_engine = ReplayEngine(self._snapshot_engine)
        self._validator = StateValidator()
        self._swarm_id = swarm_id

        logger.info("DigitalTwin: initialized for '%s'", swarm_id)

    # =====================================================================
    # READ-ONLY API (external consumers)
    # =====================================================================

    def get_swarm_state(self) -> SwarmState:
        """
        Get the current immutable swarm state.

        This is the Single Source of Truth for the entire system.
        Returns a frozen SwarmState — cannot be modified.
        """
        return self._sync_engine.get_swarm_state()

    def get_drone_state(self, drone_id: int) -> Optional[DroneState]:
        """
        Get the current state of a specific drone.

        Returns None if drone is not registered.
        """
        return self._sync_engine.get_drone_state(drone_id)

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Retrieve a stored snapshot by ID."""
        return self._snapshot_engine.get_snapshot(snapshot_id)

    def get_latest_snapshot(self) -> Optional[Snapshot]:
        """Get the most recent snapshot."""
        return self._snapshot_engine.get_latest_snapshot()

    def list_snapshots(self) -> list[Snapshot]:
        """List all stored snapshots."""
        return self._snapshot_engine.list_snapshots()

    def replay_timeline(
        self,
        start_version: Optional[int] = None,
        end_version: Optional[int] = None,
        description: str = "",
    ) -> ReplayTimeline:
        """
        Replay the swarm timeline from stored snapshots.

        Deterministic — same inputs always produce same replay.
        """
        return self._replay_engine.replay_timeline(
            start_version=start_version,
            end_version=end_version,
            description=description,
        )

    def replay_drone(
        self,
        drone_id: int,
        start_version: Optional[int] = None,
        end_version: Optional[int] = None,
    ) -> DroneReplayTimeline:
        """Replay state history for a specific drone."""
        return self._replay_engine.replay_drone(
            drone_id=drone_id,
            start_version=start_version,
            end_version=end_version,
        )

    def replay_at_version(self, version: int) -> Optional[SwarmState]:
        """Reconstruct exact swarm state at a given snapshot version."""
        return self._replay_engine.replay_swarm_at_version(version)

    @property
    def version(self) -> int:
        """Current state version."""
        return self._sync_engine.version

    @property
    def snapshot_count(self) -> int:
        """Total stored snapshots."""
        return self._snapshot_engine.snapshot_count

    # =====================================================================
    # INTERNAL SYNC (called by simulation/ROS2 layer only)
    # =====================================================================

    def sync_drone_state(self, update: DroneStateUpdate) -> ValidationResult:
        """
        Sync a drone state update from ROS2/simulation.

        Internal method — NOT for external consumers.
        Validates and applies the update.
        """
        return self._sync_engine.apply_drone_update(update)

    def sync_swarm_state(self, update: SwarmStateUpdate) -> ValidationResult:
        """
        Sync a swarm-level update from ROS2/simulation.

        Internal method — NOT for external consumers.
        """
        return self._sync_engine.apply_swarm_update(update)

    def sync_failures(self, failures: list[FailureCategory]) -> None:
        """Sync active failure list from simulation."""
        self._sync_engine.apply_failure_update(failures)

    def sync_environment(
        self,
        wind_speed_m_s: float = 0.0,
        wind_direction_deg: float = 0.0,
        condition: EnvironmentCondition = EnvironmentCondition.NOMINAL,
    ) -> None:
        """Sync environment state."""
        self._sync_engine.apply_environment_update(
            wind_speed_m_s=wind_speed_m_s,
            wind_direction_deg=wind_direction_deg,
            condition=condition,
        )

    def register_drone(self, drone_id: int) -> None:
        """Register a drone in the Digital Twin."""
        self._sync_engine.register_drone(drone_id)

    def create_snapshot(self, description: str = "") -> Snapshot:
        """
        Create an immutable snapshot of the current state.

        Captures the complete SwarmState at this moment.
        """
        state = self._sync_engine.get_swarm_state()
        return self._snapshot_engine.create_snapshot(state, description)

    # =====================================================================
    # PROPERTIES
    # =====================================================================

    @property
    def sync_events(self):
        """Access sync event log (read-only)."""
        return self._sync_engine.sync_events

    @property
    def swarm_id(self) -> str:
        """The swarm ID this twin represents."""
        return self._swarm_id
