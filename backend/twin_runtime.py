"""
Phase 10C.4 — Digital Twin Runtime.

Drives the existing Simulation Core and mirrors its output into the
Digital Twin (the Single Source of Truth), then exposes read-only,
serialized views for the REST/WebSocket API layer.

STRICT BOUNDARIES (enforced by design):
- No decision-making, planning, optimization, scheduling, routing, or
  resource allocation happens here.
- The demonstration mission uses FIXED, pre-defined geometry (a static
  lawnmower pattern). It is NOT generated/optimized. Drones are driven
  ONLY through the CommandSchema single entry point of the Simulation
  Core (Hive → CommandSchema → MAVLink Bridge → SITL), exactly like the
  existing Phase 10A mission execution.
- Mission lifecycle (IDLE/RUNNING/PAUSED/COMPLETED) is operator-intent
  bookkeeping only — no autonomous behavior.
- The Digital Twin itself is never modified; this layer only feeds it
  via the existing internal sync API and reads it back.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from core.hal_interfaces import CommandSchema, CommandType
from digital_twin.state_models import (
    DroneStateUpdate,
    EnvironmentCondition,
    FailureCategory,
    HealthLevel,
    MissionStatus,
    SwarmStateUpdate,
)
from digital_twin.twin_api import DigitalTwin
from simulation.failure_injection import (
    FailureConfig,
    FailureSeverity,
    FailureType,
)
from simulation.ros2_swarm_bus import SwarmBus
from simulation.sim_core import SimulationCore
from backend import serializers
from backend.serializers import JSONObject

# =========================================================================
# Fixed demonstration mission geometry (static — NOT generated/optimized)
# =========================================================================

FIELD_CENTER = {"lat": 38.7223, "lng": -9.1393}
FIELD_HALF_LAT = 0.004
FIELD_HALF_LNG = 0.005
CRUISE_ALT_M = 25.0
ROUTE_ROWS = 24
ROUTE_COL_SPAN = 0.004


def _field_polygon() -> list[dict[str, float]]:
    c = FIELD_CENTER
    return [
        {"lat": c["lat"] - FIELD_HALF_LAT, "lng": c["lng"] - FIELD_HALF_LNG},
        {"lat": c["lat"] - FIELD_HALF_LAT, "lng": c["lng"] + FIELD_HALF_LNG},
        {"lat": c["lat"] + FIELD_HALF_LAT, "lng": c["lng"] + FIELD_HALF_LNG},
        {"lat": c["lat"] + FIELD_HALF_LAT, "lng": c["lng"] - FIELD_HALF_LNG},
    ]


def _planned_route(drone_id: int) -> list[dict[str, float]]:
    """Fixed lawnmower coverage path for a drone (static geometry)."""
    offset = (drone_id - 1) * 0.002
    route: list[dict[str, float]] = []
    for r in range(ROUTE_ROWS):
        start_lng = FIELD_CENTER["lng"] - ROUTE_COL_SPAN / 2 + offset
        end_lng = FIELD_CENTER["lng"] + ROUTE_COL_SPAN / 2 + offset
        lat = FIELD_CENTER["lat"] - 0.003 + r * 0.001
        if r % 2 == 0:
            route.append({"lat": lat, "lng": start_lng})
            route.append({"lat": lat, "lng": end_lng})
        else:
            route.append({"lat": lat, "lng": end_lng})
            route.append({"lat": lat, "lng": start_lng})
    return route


# =========================================================================
# Failure type → Digital Twin failure category (identical wire values)
# =========================================================================

_FAILURE_TYPE_TO_CATEGORY = {
    FailureType.BATTERY_DEGRADATION: FailureCategory.BATTERY_DEGRADATION,
    FailureType.GPS_LOSS: FailureCategory.GPS_LOSS,
    FailureType.LINK_LOSS: FailureCategory.LINK_LOSS,
    FailureType.WIND_DISTURBANCE: FailureCategory.WIND_DISTURBANCE,
}

_HEALTH_RANK = {HealthLevel.OK: 0, HealthLevel.WARNING: 1, HealthLevel.CRITICAL: 2}


@dataclass
class _DroneMissionState:
    """Per-drone scripted-mission bookkeeping (position stepping only)."""
    route: list[dict[str, float]]
    index: int = 0
    prev_lat: float = 0.0
    prev_lng: float = 0.0
    prev_health: HealthLevel = HealthLevel.OK


class TwinRuntime:
    """
    Owns the Simulation Core + Digital Twin and advances them in lockstep.

    All public read methods return JSON-safe dicts already matching the UI
    TypeScript contracts. Thread-safe via a single re-entrant lock.
    """

    SNAPSHOT_INTERVAL_TICKS = 5

    def __init__(
        self,
        num_drones: int = 3,
        failure_seed: int = 42,
        swarm_id: str = "swarm-orion-001",
        mission_id: str = "mission-alpha-001",
    ) -> None:
        self._lock = threading.RLock()
        self._sim = SimulationCore(num_drones=num_drones, failure_seed=failure_seed)
        self._twin = DigitalTwin(swarm_id=swarm_id)
        self._mission_id = mission_id

        for did in self._sim.drone_ids:
            self._twin.register_drone(did)

        self._configure_failures()

        self._drone_missions: dict[int, _DroneMissionState] = {
            did: _DroneMissionState(route=_planned_route(did))
            for did in self._sim.drone_ids
        }

        self._mission_status = MissionStatus.IDLE
        self._mission_start_ms: Optional[int] = None
        self._mission_end_ms: Optional[int] = None
        self._progress = 0.0
        self._tick_count = 0

        self._alerts: list[JSONObject] = []
        self._alert_counter = 0
        self._mission_events: list[JSONObject] = []
        self._prev_active_failures: set[FailureType] = set()

    # -----------------------------------------------------------------
    # Failure configuration (available for on-demand injection)
    # -----------------------------------------------------------------

    def _configure_failures(self) -> None:
        inj = self._sim.failure_injector
        inj.configure(FailureConfig(
            failure_type=FailureType.BATTERY_DEGRADATION,
            severity=FailureSeverity.HIGH,
        ))
        inj.configure(FailureConfig(
            failure_type=FailureType.GPS_LOSS,
            severity=FailureSeverity.HIGH,
        ))
        inj.configure(FailureConfig(
            failure_type=FailureType.LINK_LOSS,
            severity=FailureSeverity.HIGH,
        ))
        inj.configure(FailureConfig(
            failure_type=FailureType.WIND_DISTURBANCE,
            severity=FailureSeverity.MEDIUM,
        ))

    # -----------------------------------------------------------------
    # Mission lifecycle (operator-intent bookkeeping only)
    # -----------------------------------------------------------------

    def start_mission(self) -> bool:
        with self._lock:
            if self._mission_status == MissionStatus.RUNNING:
                return True
            for did in self._sim.drone_ids:
                self._arm_and_takeoff(did)
                self._drone_missions[did].index = 0
            self._mission_status = MissionStatus.RUNNING
            self._mission_start_ms = _now_ms()
            self._mission_end_ms = None
            self._add_mission_event(
                "START", f"Mission {self._mission_id} started — "
                f"{len(self._sim.drone_ids)} drones deployed",
            )
            return True

    def pause_mission(self) -> bool:
        with self._lock:
            if self._mission_status != MissionStatus.RUNNING:
                return False
            self._mission_status = MissionStatus.PAUSED
            self._add_mission_event("PAUSE", "Mission paused by operator")
            return True

    def resume_mission(self) -> bool:
        with self._lock:
            if self._mission_status != MissionStatus.PAUSED:
                return False
            self._mission_status = MissionStatus.RUNNING
            self._add_mission_event("RESUME", "Mission resumed by operator")
            return True

    def stop_mission(self) -> bool:
        with self._lock:
            if self._mission_status in (MissionStatus.IDLE, MissionStatus.COMPLETED):
                return False
            self._mission_status = MissionStatus.COMPLETED
            self._mission_end_ms = _now_ms()
            self._add_mission_event("STOP", "Mission stopped by operator")
            return True

    def request_snapshot(self) -> str:
        with self._lock:
            snap = self._twin.create_snapshot("operator-requested snapshot")
            return snap.snapshot_id

    # -----------------------------------------------------------------
    # Command helpers (single execution path: CommandSchema → bridge)
    # -----------------------------------------------------------------

    def _arm_and_takeoff(self, drone_id: int) -> None:
        self._sim.execute_command(CommandSchema(
            command_id=f"arm-{drone_id}-{self._tick_count}",
            drone_id=drone_id,
            command_type=CommandType.ARM,
        ))
        self._sim.execute_command(CommandSchema(
            command_id=f"takeoff-{drone_id}-{self._tick_count}",
            drone_id=drone_id,
            command_type=CommandType.TAKEOFF,
            params={"altitude_m": CRUISE_ALT_M},
        ))
        wp = self._drone_missions[drone_id].route[0]
        self._goto(drone_id, wp)

    def _goto(self, drone_id: int, wp: dict[str, float]) -> None:
        self._sim.execute_command(CommandSchema(
            command_id=f"goto-{drone_id}-{self._tick_count}",
            drone_id=drone_id,
            command_type=CommandType.GOTO,
            params={
                "latitude": wp["lat"],
                "longitude": wp["lng"],
                "altitude_m": CRUISE_ALT_M,
                "speed_m_s": 5.0,
            },
            mission_id=self._mission_id,
        ))

    # -----------------------------------------------------------------
    # Tick: advance sim → mirror into Digital Twin → return events
    # -----------------------------------------------------------------

    def tick(self) -> JSONObject:
        """
        Advance one step. Returns {swarm, alerts, mission} where `alerts`
        contains only alerts newly raised on this tick.
        """
        with self._lock:
            self._tick_count += 1
            running = self._mission_status == MissionStatus.RUNNING

            if running:
                self._advance_mission_positions()

            self._sim.tick()
            new_alerts = self._sync_from_bus()
            self._sync_environment_and_failures(new_alerts)

            if running:
                self._twin.sync_swarm_state(SwarmStateUpdate(
                    timestamp_ms=_now_ms(),
                    mission_id=self._mission_id,
                    total_drones=len(self._sim.drone_ids),
                ))
                self._update_progress()

            if self._tick_count % self.SNAPSHOT_INTERVAL_TICKS == 0:
                self._twin.create_snapshot(
                    f"auto snapshot tick={self._tick_count}"
                )

            return {
                "swarm": self._swarm_payload_locked(),
                "alerts": new_alerts,
                "mission": self._mission_payload_locked(),
            }

    def _advance_mission_positions(self) -> None:
        inj = self._sim.failure_injector
        for did in self._sim.drone_ids:
            ms = self._drone_missions[did]
            wp = ms.route[ms.index]
            # A comm-lost drone cannot receive commands; hold position.
            if inj.get_drone_failure_state(did).link_available:
                self._goto(did, wp)
                if ms.index < len(ms.route) - 1:
                    ms.index += 1
        if all(
            ms.index >= len(ms.route) - 1
            for ms in self._drone_missions.values()
        ):
            self._mission_status = MissionStatus.COMPLETED
            self._mission_end_ms = _now_ms()
            self._add_mission_event("STOP", "Mission coverage complete")

    def _sync_from_bus(self) -> list[JSONObject]:
        bus = self._sim.bus
        inj = self._sim.failure_injector
        new_alerts: list[JSONObject] = []

        for did in self._sim.drone_ids:
            state_msg = bus.get_latest(SwarmBus.drone_state_topic(did))
            if state_msg is None:
                continue
            fstate = inj.get_drone_failure_state(did)
            ms = self._drone_missions[did]

            vx = (state_msg.longitude - ms.prev_lng) * 111000.0
            vy = (state_msg.latitude - ms.prev_lat) * 111000.0
            ms.prev_lat = state_msg.latitude
            ms.prev_lng = state_msg.longitude

            health = _map_health(state_msg.health.value)
            comm_active = fstate.link_available

            update = DroneStateUpdate(
                drone_id=did,
                timestamp_ms=_now_ms(),
                latitude=state_msg.latitude,
                longitude=state_msg.longitude,
                altitude_m=state_msg.altitude_m,
                velocity_x=vx,
                velocity_y=vy,
                velocity_z=0.0,
                battery_pct=state_msg.battery_pct,
                battery_voltage=state_msg.battery_voltage,
                armed=self._mission_status == MissionStatus.RUNNING,
                mode="AUTO" if self._mission_status == MissionStatus.RUNNING else "STANDBY",
                gps_available=fstate.gps_available,
                gps_accuracy_m=fstate.gps_accuracy_m,
                communication_active=comm_active,
                health=health.value,
                current_task=(
                    "IN_PROGRESS"
                    if self._mission_status == MissionStatus.RUNNING
                    else "NONE"
                ),
            )
            self._twin.sync_drone_state(update)

            if _HEALTH_RANK[health] > _HEALTH_RANK[ms.prev_health]:
                new_alerts.append(self._raise_alert(
                    severity="CRITICAL" if health == HealthLevel.CRITICAL else "WARNING",
                    source=f"drone_{did}",
                    message=f"Drone {did} health degraded to {health.value}",
                    category="SYSTEM",
                ))
            ms.prev_health = health

        return new_alerts

    def _sync_environment_and_failures(
        self, new_alerts: list[JSONObject],
    ) -> None:
        inj = self._sim.failure_injector
        active_types = inj.active_failure_types

        categories = [
            _FAILURE_TYPE_TO_CATEGORY[ft]
            for ft in active_types
            if ft in _FAILURE_TYPE_TO_CATEGORY
        ]
        self._twin.sync_failures(categories)

        # Environment (wind) — take max wind across drones' failure state
        wind_speed = 0.0
        wind_dir = 0.0
        for did in self._sim.drone_ids:
            fs = inj.get_drone_failure_state(did)
            if fs.wind_speed_m_s > wind_speed:
                wind_speed = fs.wind_speed_m_s
                wind_dir = fs.wind_direction_deg
        condition = (
            EnvironmentCondition.SEVERE if wind_speed > 20
            else EnvironmentCondition.DEGRADED if wind_speed > 8
            else EnvironmentCondition.NOMINAL
        )
        self._twin.sync_environment(
            wind_speed_m_s=wind_speed,
            wind_direction_deg=wind_dir,
            condition=condition,
        )

        newly_active = active_types - self._prev_active_failures
        for ft in newly_active:
            new_alerts.append(self._raise_alert(
                severity="CRITICAL",
                source="simulation",
                message=f"Failure active: {ft.value}",
                category=_FAILURE_TYPE_TO_CATEGORY[ft].value
                if ft in _FAILURE_TYPE_TO_CATEGORY else "SYSTEM",
            ))
        self._prev_active_failures = set(active_types)

    def _update_progress(self) -> None:
        totals = []
        for ms in self._drone_missions.values():
            last = max(1, len(ms.route) - 1)
            totals.append(min(1.0, ms.index / last))
        self._progress = sum(totals) / len(totals) if totals else 0.0

    # -----------------------------------------------------------------
    # Failure injection (on-demand, operator/testing)
    # -----------------------------------------------------------------

    _FAILURE_SEVERITY = {
        FailureType.BATTERY_DEGRADATION: FailureSeverity.HIGH,
        FailureType.GPS_LOSS: FailureSeverity.HIGH,
        FailureType.LINK_LOSS: FailureSeverity.HIGH,
        FailureType.WIND_DISTURBANCE: FailureSeverity.MEDIUM,
    }

    def inject_failure(self, failure: str, drone_ids: Optional[list[int]] = None) -> bool:
        with self._lock:
            try:
                ft = FailureType(failure)
            except ValueError:
                return False
            inj = self._sim.failure_injector
            inj.configure(FailureConfig(
                failure_type=ft,
                severity=self._FAILURE_SEVERITY.get(ft, FailureSeverity.MEDIUM),
                target_drone_ids=drone_ids,
            ))
            inj.activate(ft)
            return True

    def clear_failures(self) -> None:
        with self._lock:
            self._sim.failure_injector.deactivate_all()

    # -----------------------------------------------------------------
    # Read-only serialized views
    # -----------------------------------------------------------------

    def get_swarm_payload(self) -> JSONObject:
        with self._lock:
            return self._swarm_payload_locked()

    def _swarm_payload_locked(self) -> JSONObject:
        payload = serializers.serialize_swarm_state(self._twin.get_swarm_state())
        # Compose operator-intent mission lifecycle (twin is unmodified).
        payload["mission_status"] = self._mission_status.value
        payload["mission_id"] = (
            self._mission_id
            if self._mission_status != MissionStatus.IDLE
            else None
        )
        return payload

    def get_drone_payload(self, drone_id: int) -> Optional[JSONObject]:
        with self._lock:
            drone = self._twin.get_drone_state(drone_id)
            if drone is None:
                return None
            return serializers.serialize_drone_state(drone)

    def list_snapshots_payload(self) -> list[JSONObject]:
        with self._lock:
            return [
                serializers.serialize_snapshot_metadata(s)
                for s in self._twin.list_snapshots()
            ]

    def get_snapshot_payload(self, snapshot_id: str) -> Optional[JSONObject]:
        with self._lock:
            snap = self._twin.get_snapshot(snapshot_id)
            return serializers.serialize_snapshot(snap) if snap else None

    def replay_timeline_payload(
        self,
        start_version: Optional[int] = None,
        end_version: Optional[int] = None,
    ) -> JSONObject:
        with self._lock:
            tl = self._twin.replay_timeline(
                start_version=start_version,
                end_version=end_version,
                description="UI replay request",
            )
            return serializers.serialize_replay_timeline(tl)

    def replay_drone_payload(self, drone_id: int) -> JSONObject:
        with self._lock:
            tl = self._twin.replay_drone(drone_id)
            return serializers.serialize_drone_replay_timeline(tl)

    def mission_geometry(self) -> JSONObject:
        return {
            "field_center": FIELD_CENTER,
            "field_polygon": _field_polygon(),
            "planned_routes": {
                str(did): _planned_route(did) for did in self._sim.drone_ids
            },
        }

    def get_mission_payload(self) -> JSONObject:
        with self._lock:
            return self._mission_payload_locked()

    def _mission_payload_locked(self) -> JSONObject:
        return {
            "mission_id": (
                self._mission_id
                if self._mission_status != MissionStatus.IDLE
                else None
            ),
            "status": self._mission_status.value,
            "progress": self._progress,
            "start_ms": self._mission_start_ms,
            "end_ms": self._mission_end_ms,
            "events": list(self._mission_events[-100:]),
        }

    def get_alerts(self) -> list[JSONObject]:
        with self._lock:
            return list(self._alerts[-200:])

    # -----------------------------------------------------------------
    # Analytics — aggregations of REAL Digital Twin data (no invention)
    # -----------------------------------------------------------------

    def analytics(self) -> JSONObject:
        with self._lock:
            snapshots = self._twin.list_snapshots()

            battery_trends: dict[str, list[dict[str, float]]] = {}
            fleet_utilization: list[JSONObject] = []
            for snap in snapshots:
                st = snap.swarm_state
                fleet_utilization.append({
                    "version": snap.version,
                    "timestamp_ms": snap.timestamp_ms,
                    "active_drones": st.active_drones,
                    "failed_drones": st.failed_drones,
                    "total_drones": st.total_drones,
                })
                for d in st.drone_states:
                    battery_trends.setdefault(str(d.drone_id), []).append({
                        "version": snap.version,
                        "timestamp_ms": snap.timestamp_ms,
                        "battery_pct": d.battery_pct,
                    })

            alert_frequency: dict[str, int] = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}
            for a in self._alerts:
                alert_frequency[a["severity"]] = alert_frequency.get(a["severity"], 0) + 1

            duration_ms = 0
            if self._mission_start_ms is not None:
                end = self._mission_end_ms or _now_ms()
                duration_ms = max(0, end - self._mission_start_ms)

            return {
                "snapshot_count": len(snapshots),
                "battery_trends": battery_trends,
                "fleet_utilization": fleet_utilization,
                "alert_frequency": alert_frequency,
                "mission": {
                    "mission_id": self._mission_id,
                    "status": self._mission_status.value,
                    "progress": self._progress,
                    "duration_ms": duration_ms,
                },
            }

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _raise_alert(
        self, severity: str, source: str, message: str, category: str,
    ) -> JSONObject:
        self._alert_counter += 1
        alert = {
            "id": f"alert-{self._alert_counter}",
            "severity": severity,
            "source": source,
            "message": message,
            "category": category,
            "timestamp_ms": _now_ms(),
            "active": True,
            "resolved_ms": None,
        }
        self._alerts.append(alert)
        return alert

    def _add_mission_event(self, event_type: str, message: str) -> None:
        self._mission_events.append({
            "id": f"evt-{len(self._mission_events) + 1}",
            "timestamp_ms": _now_ms(),
            "type": event_type,
            "message": message,
        })

    @property
    def drone_ids(self) -> list[int]:
        return self._sim.drone_ids


def _now_ms() -> int:
    return int(time.time() * 1000)


def _map_health(value: str) -> HealthLevel:
    try:
        return HealthLevel(value)
    except ValueError:
        return HealthLevel.OK
