"""
Phase 10B — Snapshot Engine.

Creates and manages immutable snapshots of the Digital Twin state.
Snapshots are versioned, timestamped, and NEVER modified after creation.

Capabilities:
- Create snapshot from current state
- Retrieve snapshot by ID or version
- List all snapshots
- Timestamp and version snapshots

Architecture rules:
- Snapshots are IMMUTABLE after creation
- Read-only access only
- No decision-making
- No state modification
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

from digital_twin.state_models import SwarmState

logger = logging.getLogger("eea.digital_twin.snapshot_engine")


# =========================================================================
# Snapshot Model
# =========================================================================

@dataclass(frozen=True)
class Snapshot:
    """
    An immutable snapshot of the Digital Twin state.

    Once created, a snapshot is NEVER modified.
    """
    snapshot_id: str
    version: int
    timestamp_ms: int
    swarm_state: SwarmState
    description: str = ""


# =========================================================================
# Snapshot Engine
# =========================================================================

class SnapshotEngine:
    """
    Manages immutable state snapshots.

    Snapshots capture the complete SwarmState at a point in time.
    They are stored in-memory and are never modified.
    """

    def __init__(self) -> None:
        self._snapshots: list[Snapshot] = []
        self._lock = threading.Lock()
        self._snapshot_counter: int = 0
        logger.info("SnapshotEngine: initialized")

    def create_snapshot(
        self,
        state: SwarmState,
        description: str = "",
    ) -> Snapshot:
        """
        Create an immutable snapshot from the current state.

        The snapshot is stored and can be retrieved later.
        """
        with self._lock:
            self._snapshot_counter += 1
            snapshot = Snapshot(
                snapshot_id=f"snap-{self._snapshot_counter:06d}",
                version=self._snapshot_counter,
                timestamp_ms=int(time.monotonic() * 1000),
                swarm_state=state,
                description=description,
            )
            self._snapshots.append(snapshot)

        logger.info(
            "SnapshotEngine: created %s (v%d, %d drones)",
            snapshot.snapshot_id,
            snapshot.version,
            len(state.drone_states),
        )
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Retrieve a snapshot by ID."""
        with self._lock:
            for snap in self._snapshots:
                if snap.snapshot_id == snapshot_id:
                    return snap
        return None

    def get_snapshot_by_version(self, version: int) -> Optional[Snapshot]:
        """Retrieve a snapshot by version number."""
        with self._lock:
            for snap in self._snapshots:
                if snap.version == version:
                    return snap
        return None

    def get_latest_snapshot(self) -> Optional[Snapshot]:
        """Get the most recent snapshot."""
        with self._lock:
            if self._snapshots:
                return self._snapshots[-1]
        return None

    def list_snapshots(self) -> list[Snapshot]:
        """List all snapshots (ordered by version)."""
        with self._lock:
            return list(self._snapshots)

    @property
    def snapshot_count(self) -> int:
        """Total number of stored snapshots."""
        with self._lock:
            return len(self._snapshots)
