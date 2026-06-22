"""
Phase 9.3 — Telemetry Stream System.

Real-time standardized telemetry streaming from hardware adapters
to Hive-consumable format. Pure state streaming only.

NO storage layer, NO historical inference, NO aggregation
intelligence, NO predictive behavior, NO decision logic.

Telemetry is forwarded and normalized — never interpreted.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.hal_interfaces import (
    BaseDroneInterface,
    FlightState,
    GPSPosition,
    TelemetrySchema,
)

logger = logging.getLogger("eea.hal_telemetry")


# =========================================================================
# Task State — Drone-Level Activity State
# =========================================================================

class TaskState(Enum):
    """Drone task state as required by telemetry contract."""
    IDLE = "idle"
    EN_ROUTE = "en_route"
    WORKING = "working"
    RETURNING = "returning"
    EMERGENCY = "emergency"
    LANDED = "landed"


# =========================================================================
# GPS Fix Quality
# =========================================================================

class GPSFixQuality(Enum):
    """GPS fix quality levels."""
    NO_FIX = "no_fix"
    FIX_2D = "2d"
    FIX_3D = "3d"
    DGPS = "dgps"
    RTK_FLOAT = "rtk_float"
    RTK_FIXED = "rtk_fixed"


# =========================================================================
# Velocity Vector
# =========================================================================

@dataclass
class Velocity3D:
    """3D velocity in m/s."""
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0


# =========================================================================
# DroneTelemetryFrame — Per-Drone Telemetry Snapshot
# =========================================================================

@dataclass
class DroneTelemetryFrame:
    """
    Complete telemetry frame for a single drone.

    Satisfies the mandatory telemetry contract. Each frame is an
    independent snapshot — no historical state, no inference.
    """
    drone_id: int
    position: GPSPosition
    velocity: Velocity3D
    heading_deg: float
    battery_level_pct: float
    power_draw_w: float
    mission_id: Optional[str]
    task_state: TaskState
    gps_fix_quality: GPSFixQuality
    signal_strength_pct: float
    timestamp_ms: int


# =========================================================================
# FleetTelemetrySnapshot — Fleet-Wide Aggregation
# =========================================================================

@dataclass
class FleetTelemetrySnapshot:
    """
    Fleet-wide telemetry snapshot.

    Pure aggregation of current drone counts by state. No
    intelligence, no inference, no prediction.
    """
    total_drones: int
    active_drones: int
    idle_drones: int
    charging_drones: int
    faulty_drones: int
    global_timestamp_ms: int
    frames: list[DroneTelemetryFrame] = field(default_factory=list)


# =========================================================================
# Flight State → Task State Mapping
# =========================================================================

FLIGHT_STATE_TO_TASK: dict[FlightState, TaskState] = {
    FlightState.GROUNDED: TaskState.LANDED,
    FlightState.ARMING: TaskState.IDLE,
    FlightState.ARMED: TaskState.IDLE,
    FlightState.TAKING_OFF: TaskState.EN_ROUTE,
    FlightState.IN_FLIGHT: TaskState.WORKING,
    FlightState.LANDING: TaskState.RETURNING,
    FlightState.RETURNING: TaskState.RETURNING,
    FlightState.EMERGENCY: TaskState.EMERGENCY,
    FlightState.UNKNOWN: TaskState.IDLE,
}


# =========================================================================
# TelemetryStreamProcessor — Normalize Adapter Telemetry
# =========================================================================

class TelemetryStreamProcessor:
    """
    Processes raw adapter telemetry into standardized frames.

    Reads from any BaseDroneInterface adapter and produces
    DroneTelemetryFrame objects. Pure normalization — no
    storage, no inference, no decisions.
    """

    def __init__(self, adapter: BaseDroneInterface) -> None:
        self._adapter = adapter
        self._drone_ids: list[int] = []
        self._mission_map: dict[int, Optional[str]] = {}
        logger.info(
            "TelemetryStreamProcessor: initialized with %s",
            adapter.get_adapter_name(),
        )

    def register_drone(self, drone_id: int, mission_id: Optional[str] = None) -> None:
        """Register a drone for telemetry streaming."""
        if drone_id not in self._drone_ids:
            self._drone_ids.append(drone_id)
        self._mission_map[drone_id] = mission_id
        logger.info(
            "TelemetryStreamProcessor: drone %d registered (mission=%s)",
            drone_id, mission_id,
        )

    def set_mission(self, drone_id: int, mission_id: Optional[str]) -> None:
        """Update the mission assignment for a drone."""
        self._mission_map[drone_id] = mission_id

    def read_frame(self, drone_id: int) -> DroneTelemetryFrame:
        """
        Read a single telemetry frame from the adapter.

        Normalizes the adapter's TelemetrySchema into a
        DroneTelemetryFrame. No interpretation.
        """
        raw = self._adapter.get_telemetry(drone_id)
        return self._normalize(raw)

    def read_all_frames(self) -> list[DroneTelemetryFrame]:
        """Read telemetry frames for all registered drones."""
        frames = []
        for drone_id in self._drone_ids:
            if self._adapter.is_connected(drone_id):
                frame = self.read_frame(drone_id)
                frames.append(frame)
        return frames

    def build_fleet_snapshot(self) -> FleetTelemetrySnapshot:
        """
        Build a fleet-wide telemetry snapshot.

        Counts drones by state. Pure aggregation — no intelligence.
        """
        frames = self.read_all_frames()
        now_ms = int(time.monotonic() * 1000)

        active = 0
        idle = 0
        charging = 0
        faulty = 0

        for f in frames:
            if f.task_state == TaskState.EMERGENCY:
                faulty += 1
            elif f.task_state in (TaskState.EN_ROUTE, TaskState.WORKING, TaskState.RETURNING):
                active += 1
            elif f.task_state == TaskState.LANDED:
                idle += 1
            else:
                idle += 1

        snapshot = FleetTelemetrySnapshot(
            total_drones=len(self._drone_ids),
            active_drones=active,
            idle_drones=idle,
            charging_drones=charging,
            faulty_drones=faulty,
            global_timestamp_ms=now_ms,
            frames=frames,
        )

        logger.info(
            "TelemetryStreamProcessor: fleet snapshot — "
            "%d total, %d active, %d idle, %d faulty",
            snapshot.total_drones, active, idle, faulty,
        )
        return snapshot

    def _normalize(self, raw: TelemetrySchema) -> DroneTelemetryFrame:
        """Normalize adapter telemetry into DroneTelemetryFrame."""
        pos = raw.position or GPSPosition(0.0, 0.0, 0.0)
        task = FLIGHT_STATE_TO_TASK.get(raw.flight_state, TaskState.IDLE)

        speed = raw.speed_m_s or 0.0
        heading = raw.heading_deg or 0.0
        velocity = Velocity3D(
            vx=speed * _cos_deg(heading),
            vy=speed * _sin_deg(heading),
            vz=0.0,
        )

        sat_count = raw.satellite_count or 0
        if sat_count >= 8:
            gps_quality = GPSFixQuality.FIX_3D
        elif sat_count >= 4:
            gps_quality = GPSFixQuality.FIX_2D
        else:
            gps_quality = GPSFixQuality.NO_FIX

        return DroneTelemetryFrame(
            drone_id=raw.drone_id,
            position=GPSPosition(pos.latitude, pos.longitude, pos.altitude_m),
            velocity=velocity,
            heading_deg=heading,
            battery_level_pct=raw.battery_pct if raw.battery_pct is not None else 0.0,
            power_draw_w=0.0,
            mission_id=self._mission_map.get(raw.drone_id),
            task_state=task,
            gps_fix_quality=gps_quality,
            signal_strength_pct=raw.signal_strength_pct if raw.signal_strength_pct is not None else 0.0,
            timestamp_ms=raw.timestamp_ms,
        )


# =========================================================================
# Helpers
# =========================================================================

import math


def _cos_deg(degrees: float) -> float:
    return math.cos(math.radians(degrees))


def _sin_deg(degrees: float) -> float:
    return math.sin(math.radians(degrees))
