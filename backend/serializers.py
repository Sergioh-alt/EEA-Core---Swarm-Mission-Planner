"""
Phase 10C.4 — Digital Twin JSON serializers.

Converts immutable Digital Twin dataclasses / enums into plain JSON-safe
dicts that match the UI TypeScript contracts 1:1
(orion-ui/src/contracts/types.ts).

Pure functions. No logic, no mutation, no decision-making.
"""

from __future__ import annotations

from enum import Enum
from typing import Union

from digital_twin.replay_engine import (
    DroneReplayFrame,
    DroneReplayTimeline,
    ReplayFrame,
    ReplayTimeline,
)
from digital_twin.snapshot_engine import Snapshot
from digital_twin.state_models import (
    DroneState,
    EnvironmentState,
    Position,
    SwarmState,
    Velocity,
)

# JSON-serializable value / object aliases (used instead of `Any`).
JSONValue = Union[
    None, bool, int, float, str, list["JSONValue"], dict[str, "JSONValue"]
]
JSONObject = dict[str, "JSONValue"]


def _enum(value: Enum) -> str:
    """Return the string wire value of an enum member."""
    return str(value.value)


def serialize_position(pos: Position) -> dict[str, float]:
    return {
        "latitude": pos.latitude,
        "longitude": pos.longitude,
        "altitude_m": pos.altitude_m,
    }


def serialize_velocity(vel: Velocity) -> dict[str, float]:
    return {"vx": vel.vx, "vy": vel.vy, "vz": vel.vz}


def serialize_drone_state(drone: DroneState) -> JSONObject:
    return {
        "drone_id": drone.drone_id,
        "armed": drone.armed,
        "mode": _enum(drone.mode),
        "position": serialize_position(drone.position),
        "velocity": serialize_velocity(drone.velocity),
        "heading_deg": drone.heading_deg,
        "battery_pct": drone.battery_pct,
        "battery_voltage": drone.battery_voltage,
        "gps_available": drone.gps_available,
        "gps_accuracy_m": drone.gps_accuracy_m,
        "communication_active": drone.communication_active,
        "health": _enum(drone.health),
        "current_task": _enum(drone.current_task),
        "last_update_ms": drone.last_update_ms,
    }


def serialize_environment(env: EnvironmentState) -> JSONObject:
    return {
        "wind_speed_m_s": env.wind_speed_m_s,
        "wind_direction_deg": env.wind_direction_deg,
        "condition": _enum(env.condition),
        "timestamp_ms": env.timestamp_ms,
    }


def serialize_swarm_state(state: SwarmState) -> JSONObject:
    return {
        "swarm_id": state.swarm_id,
        "timestamp_ms": state.timestamp_ms,
        "mission_status": _enum(state.mission_status),
        "mission_id": state.mission_id,
        "simulation_time_ms": state.simulation_time_ms,
        "drone_states": [serialize_drone_state(d) for d in state.drone_states],
        "global_health": _enum(state.global_health),
        "active_failures": [_enum(f) for f in state.active_failures],
        "environment_state": serialize_environment(state.environment_state),
        "total_drones": state.total_drones,
        "active_drones": state.active_drones,
        "failed_drones": state.failed_drones,
        "version": state.version,
    }


def serialize_snapshot(snap: Snapshot) -> JSONObject:
    return {
        "snapshot_id": snap.snapshot_id,
        "version": snap.version,
        "timestamp_ms": snap.timestamp_ms,
        "swarm_state": serialize_swarm_state(snap.swarm_state),
        "description": snap.description,
    }


def serialize_snapshot_metadata(snap: Snapshot) -> JSONObject:
    return {
        "snapshot_id": snap.snapshot_id,
        "version": snap.version,
        "timestamp_ms": snap.timestamp_ms,
        "description": snap.description,
    }


def serialize_replay_frame(frame: ReplayFrame) -> JSONObject:
    return {
        "frame_index": frame.frame_index,
        "timestamp_ms": frame.timestamp_ms,
        "swarm_state": serialize_swarm_state(frame.swarm_state),
    }


def serialize_replay_timeline(timeline: ReplayTimeline) -> JSONObject:
    return {
        "timeline_id": timeline.timeline_id,
        "start_ms": timeline.start_ms,
        "end_ms": timeline.end_ms,
        "frames": [serialize_replay_frame(f) for f in timeline.frames],
        "total_frames": timeline.total_frames,
        "description": timeline.description,
    }


def serialize_drone_replay_frame(frame: DroneReplayFrame) -> JSONObject:
    return {
        "frame_index": frame.frame_index,
        "timestamp_ms": frame.timestamp_ms,
        "drone_state": serialize_drone_state(frame.drone_state),
    }


def serialize_drone_replay_timeline(
    timeline: DroneReplayTimeline,
) -> JSONObject:
    return {
        "drone_id": timeline.drone_id,
        "timeline_id": timeline.timeline_id,
        "start_ms": timeline.start_ms,
        "end_ms": timeline.end_ms,
        "frames": [serialize_drone_replay_frame(f) for f in timeline.frames],
        "total_frames": timeline.total_frames,
    }
