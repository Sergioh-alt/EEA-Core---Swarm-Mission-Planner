"""
Phase 10B — Replay Engine.

Supports deterministic replay from stored snapshots.
Replay is READ-ONLY — never modifies live state.

Capabilities:
- Replay timeline (full mission)
- Replay individual drone
- Replay complete swarm
- Deterministic replay (same input → same output)

Architecture rules:
- Read-only replay
- No state modification
- No decision-making
- No command generation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from digital_twin.state_models import DroneState, SwarmState
from digital_twin.snapshot_engine import Snapshot, SnapshotEngine

logger = logging.getLogger("eea.digital_twin.replay_engine")


# =========================================================================
# Replay Types
# =========================================================================

@dataclass(frozen=True)
class ReplayFrame:
    """A single frame in a replay timeline."""
    frame_index: int
    timestamp_ms: int
    swarm_state: SwarmState


@dataclass(frozen=True)
class DroneReplayFrame:
    """A single frame for a specific drone replay."""
    frame_index: int
    timestamp_ms: int
    drone_state: DroneState


@dataclass(frozen=True)
class ReplayTimeline:
    """A complete replay timeline (immutable)."""
    timeline_id: str
    start_ms: int
    end_ms: int
    frames: tuple[ReplayFrame, ...] = ()
    total_frames: int = 0
    description: str = ""


@dataclass(frozen=True)
class DroneReplayTimeline:
    """Replay timeline for a single drone."""
    drone_id: int
    timeline_id: str
    start_ms: int
    end_ms: int
    frames: tuple[DroneReplayFrame, ...] = ()
    total_frames: int = 0


# =========================================================================
# Replay Engine
# =========================================================================

class ReplayEngine:
    """
    Deterministic replay engine for the Digital Twin.

    Reconstructs state from snapshots for analysis and visualization.
    Replay is strictly read-only — never modifies live twin state.
    """

    def __init__(self, snapshot_engine: SnapshotEngine) -> None:
        self._snapshot_engine = snapshot_engine
        self._replay_counter: int = 0
        logger.info("ReplayEngine: initialized")

    def replay_timeline(
        self,
        start_version: Optional[int] = None,
        end_version: Optional[int] = None,
        description: str = "",
    ) -> ReplayTimeline:
        """
        Replay the full swarm timeline from stored snapshots.

        Args:
            start_version: Starting snapshot version (inclusive, default: first)
            end_version: Ending snapshot version (inclusive, default: last)
            description: Human-readable description

        Returns:
            Immutable ReplayTimeline with ordered frames.
        """
        snapshots = self._snapshot_engine.list_snapshots()
        if not snapshots:
            return ReplayTimeline(
                timeline_id=self._next_timeline_id(),
                start_ms=0,
                end_ms=0,
                total_frames=0,
                description=description or "empty",
            )

        # Filter by version range
        if start_version is not None:
            snapshots = [s for s in snapshots if s.version >= start_version]
        if end_version is not None:
            snapshots = [s for s in snapshots if s.version <= end_version]

        if not snapshots:
            return ReplayTimeline(
                timeline_id=self._next_timeline_id(),
                start_ms=0,
                end_ms=0,
                total_frames=0,
                description=description or "no matching snapshots",
            )

        frames = tuple(
            ReplayFrame(
                frame_index=idx,
                timestamp_ms=snap.timestamp_ms,
                swarm_state=snap.swarm_state,
            )
            for idx, snap in enumerate(snapshots)
        )

        timeline = ReplayTimeline(
            timeline_id=self._next_timeline_id(),
            start_ms=frames[0].timestamp_ms,
            end_ms=frames[-1].timestamp_ms,
            frames=frames,
            total_frames=len(frames),
            description=description,
        )

        logger.info(
            "ReplayEngine: created timeline %s (%d frames)",
            timeline.timeline_id, timeline.total_frames,
        )
        return timeline

    def replay_drone(
        self,
        drone_id: int,
        start_version: Optional[int] = None,
        end_version: Optional[int] = None,
    ) -> DroneReplayTimeline:
        """
        Replay state for a specific drone across snapshots.

        Extracts drone-specific state from each snapshot frame.
        Returns empty timeline if drone not found.
        """
        snapshots = self._snapshot_engine.list_snapshots()

        if start_version is not None:
            snapshots = [s for s in snapshots if s.version >= start_version]
        if end_version is not None:
            snapshots = [s for s in snapshots if s.version <= end_version]

        frames: list[DroneReplayFrame] = []
        for idx, snap in enumerate(snapshots):
            drone_state = _find_drone_in_state(
                snap.swarm_state, drone_id,
            )
            if drone_state:
                frames.append(DroneReplayFrame(
                    frame_index=idx,
                    timestamp_ms=snap.timestamp_ms,
                    drone_state=drone_state,
                ))

        start_ms = frames[0].timestamp_ms if frames else 0
        end_ms = frames[-1].timestamp_ms if frames else 0

        timeline = DroneReplayTimeline(
            drone_id=drone_id,
            timeline_id=self._next_timeline_id(),
            start_ms=start_ms,
            end_ms=end_ms,
            frames=tuple(frames),
            total_frames=len(frames),
        )

        logger.info(
            "ReplayEngine: drone %d timeline %s (%d frames)",
            drone_id, timeline.timeline_id, timeline.total_frames,
        )
        return timeline

    def replay_swarm_at_version(self, version: int) -> Optional[SwarmState]:
        """
        Reconstruct exact swarm state at a given version.

        Deterministic — same version always produces same state.
        """
        snap = self._snapshot_engine.get_snapshot_by_version(version)
        if snap:
            return snap.swarm_state
        return None

    def get_frame_at_index(
        self, timeline: ReplayTimeline, index: int,
    ) -> Optional[ReplayFrame]:
        """Get a specific frame from a replay timeline."""
        if 0 <= index < timeline.total_frames:
            return timeline.frames[index]
        return None

    def _next_timeline_id(self) -> str:
        """Generate next timeline ID."""
        self._replay_counter += 1
        return f"replay-{self._replay_counter:06d}"


# =========================================================================
# Internal Helpers
# =========================================================================

def _find_drone_in_state(
    state: SwarmState, drone_id: int,
) -> Optional[DroneState]:
    """Extract a specific drone's state from SwarmState."""
    for drone in state.drone_states:
        if drone.drone_id == drone_id:
            return drone
    return None
