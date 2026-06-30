"""
Phase 10A — ROS2 Swarm Bus (State Only).

Pub/sub state transport layer using ROS2-compatible topic naming.
Publishes drone and swarm state for consumption by Digital Twin.

CRITICAL RULE: ROS2 bus contains NO decision logic.
It is purely a state transport layer.

Topics:
- /drone_{id}/state
- /drone_{id}/battery
- /drone_{id}/position
- /swarm/global_state
- /swarm/task_allocation

Architecture rules:
- State transport ONLY — no logic
- No Hive imports
- No planning imports
- No command execution
- Read-only state publication
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("eea.ros2_swarm_bus")


# =========================================================================
# ROS2-Compatible Message Types (State Only)
# =========================================================================

class DroneHealthStatus(Enum):
    """Drone health status — mirrors ROS2 DroneState.health."""
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class DroneActivityState(Enum):
    """Drone activity state — mirrors ROS2 DroneState.state."""
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    RETURNING = "RETURNING"
    CHARGING = "CHARGING"
    FAIL = "FAIL"


@dataclass(frozen=True)
class DroneStateMessage:
    """
    ROS2 DroneState.msg equivalent.

    Per-drone state snapshot. Pure data — no methods that modify state.
    """
    drone_id: int
    timestamp_ms: int
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    velocity_z: float = 0.0
    battery_pct: float = 100.0
    battery_voltage: float = 12.6
    state: DroneActivityState = DroneActivityState.IDLE
    health: DroneHealthStatus = DroneHealthStatus.OK


@dataclass(frozen=True)
class BatteryMessage:
    """Per-drone battery state."""
    drone_id: int
    timestamp_ms: int
    percentage: float = 100.0
    voltage: float = 12.6


@dataclass(frozen=True)
class PositionMessage:
    """Per-drone position state."""
    drone_id: int
    timestamp_ms: int
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0


@dataclass(frozen=True)
class SwarmGlobalState:
    """
    ROS2 SwarmState.msg equivalent.

    Fleet-wide state snapshot. Pure aggregation — no decision logic.
    """
    mission_id: Optional[str] = None
    active_drone_ids: tuple[int, ...] = ()
    total_drones: int = 0
    active_count: int = 0
    idle_count: int = 0
    fail_count: int = 0
    global_coverage_pct: float = 0.0
    timestamp_ms: int = 0


@dataclass(frozen=True)
class TaskAllocationMessage:
    """
    Task allocation state (read-only mirror of Hive allocations).

    This is a READ-ONLY snapshot — the bus does NOT allocate tasks.
    """
    mission_id: Optional[str] = None
    allocations: tuple[tuple[int, str], ...] = ()
    timestamp_ms: int = 0


# =========================================================================
# Topic Registry
# =========================================================================

# Subscriber callback type
SubscriberCallback = Callable[[str, object], None]


@dataclass
class TopicSubscription:
    """A subscriber registered to a topic."""
    callback: SubscriberCallback
    subscriber_id: str


class SwarmBus:
    """
    ROS2-compatible pub/sub state bus.

    Provides topic-based state publication and subscription.
    All topics are state-only — no command or decision channels.

    Topic naming follows ROS2 convention:
    - /drone_{id}/state
    - /drone_{id}/battery
    - /drone_{id}/position
    - /swarm/global_state
    - /swarm/task_allocation
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[TopicSubscription]] = {}
        self._latest_messages: dict[str, object] = {}
        self._lock = threading.Lock()
        self._message_count: int = 0
        logger.info("SwarmBus: initialized")

    @staticmethod
    def drone_state_topic(drone_id: int) -> str:
        return f"/drone_{drone_id}/state"

    @staticmethod
    def drone_battery_topic(drone_id: int) -> str:
        return f"/drone_{drone_id}/battery"

    @staticmethod
    def drone_position_topic(drone_id: int) -> str:
        return f"/drone_{drone_id}/position"

    @staticmethod
    def global_state_topic() -> str:
        return "/swarm/global_state"

    @staticmethod
    def task_allocation_topic() -> str:
        return "/swarm/task_allocation"

    def subscribe(
        self, topic: str, callback: SubscriberCallback,
        subscriber_id: str = "",
    ) -> None:
        """Subscribe to a topic. Callback receives (topic, message)."""
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(
                TopicSubscription(callback=callback, subscriber_id=subscriber_id)
            )
        logger.debug("SwarmBus: subscribed to %s", topic)

    def publish(self, topic: str, message: object) -> None:
        """
        Publish a state message to a topic.

        This is a state broadcast — no command execution.
        All subscribers receive the message asynchronously.
        """
        with self._lock:
            self._latest_messages[topic] = message
            self._message_count += 1
            subscribers = list(self._subscribers.get(topic, []))

        for sub in subscribers:
            try:
                sub.callback(topic, message)
            except Exception:
                logger.exception(
                    "SwarmBus: subscriber error on topic %s", topic,
                )

    def get_latest(self, topic: str) -> Optional[object]:
        """Get the latest message published on a topic."""
        with self._lock:
            return self._latest_messages.get(topic)

    def publish_drone_state(self, msg: DroneStateMessage) -> None:
        """Convenience: publish drone state to all per-drone topics."""
        self.publish(self.drone_state_topic(msg.drone_id), msg)
        self.publish(
            self.drone_battery_topic(msg.drone_id),
            BatteryMessage(
                drone_id=msg.drone_id,
                timestamp_ms=msg.timestamp_ms,
                percentage=msg.battery_pct,
                voltage=msg.battery_voltage,
            ),
        )
        self.publish(
            self.drone_position_topic(msg.drone_id),
            PositionMessage(
                drone_id=msg.drone_id,
                timestamp_ms=msg.timestamp_ms,
                latitude=msg.latitude,
                longitude=msg.longitude,
                altitude_m=msg.altitude_m,
            ),
        )

    def publish_global_state(self, msg: SwarmGlobalState) -> None:
        """Publish global swarm state."""
        self.publish(self.global_state_topic(), msg)

    def publish_task_allocation(self, msg: TaskAllocationMessage) -> None:
        """Publish task allocation state (read-only mirror)."""
        self.publish(self.task_allocation_topic(), msg)

    @property
    def message_count(self) -> int:
        """Total messages published."""
        return self._message_count

    @property
    def active_topics(self) -> list[str]:
        """List of topics with published messages."""
        with self._lock:
            return list(self._latest_messages.keys())
