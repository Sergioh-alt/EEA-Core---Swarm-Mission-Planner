"""
Phase 10A — Failure Injection System.

Simulates controlled hardware failures for testing system resilience:
- Battery degradation
- GPS loss
- Link (communication) loss
- Wind disturbance (basic model)

All failures are configurable and activatable/deactivatable.

Architecture rules:
- Failure injection modifies SIMULATION state only
- Does NOT modify Hive state
- Does NOT make decisions
- Does NOT trigger autonomous responses
- Failures are detected by HAL safety layer (existing)
- Hive decides all responses to failures
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("eea.failure_injection")


# =========================================================================
# Failure Types
# =========================================================================

class FailureType(Enum):
    """Types of injectable failures."""
    BATTERY_DEGRADATION = "battery_degradation"
    GPS_LOSS = "gps_loss"
    LINK_LOSS = "link_loss"
    WIND_DISTURBANCE = "wind_disturbance"


class FailureSeverity(Enum):
    """Severity levels for failures."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FailureConfig:
    """Configuration for a single failure type."""
    failure_type: FailureType
    enabled: bool = False
    severity: FailureSeverity = FailureSeverity.MEDIUM
    target_drone_ids: Optional[list[int]] = None
    params: dict = field(default_factory=dict)


@dataclass
class FailureEvent:
    """Record of a failure that occurred."""
    failure_type: FailureType
    drone_id: int
    severity: FailureSeverity
    description: str
    timestamp_ms: int
    active: bool = True


@dataclass
class DroneFailureState:
    """Current failure state for a single drone."""
    drone_id: int
    battery_degradation_rate: float = 0.0
    gps_available: bool = True
    gps_accuracy_m: float = 1.0
    link_available: bool = True
    link_quality_pct: float = 100.0
    wind_speed_m_s: float = 0.0
    wind_direction_deg: float = 0.0


# =========================================================================
# Failure Injection Engine
# =========================================================================

class FailureInjector:
    """
    Controlled failure injection for simulation testing.

    Manages failure configurations and applies them to simulated
    drone states. All modifications affect simulation state only.

    Usage:
        injector = FailureInjector()
        injector.configure(FailureConfig(
            failure_type=FailureType.BATTERY_DEGRADATION,
            enabled=True,
            severity=FailureSeverity.HIGH,
            target_drone_ids=[1, 2],
            params={"rate_pct_per_sec": 5.0},
        ))
        injector.activate(FailureType.BATTERY_DEGRADATION)

        # Apply failures to drone state each simulation tick
        state = injector.apply_failures(drone_id=1, current_state=state)
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._configs: dict[FailureType, FailureConfig] = {}
        self._active_failures: set[FailureType] = set()
        self._drone_states: dict[int, DroneFailureState] = {}
        self._event_log: list[FailureEvent] = []
        self._rng = random.Random(seed)
        logger.info("FailureInjector: initialized (seed=%s)", seed)

    def configure(self, config: FailureConfig) -> None:
        """Configure a failure type. Does not activate it."""
        self._configs[config.failure_type] = config
        logger.info(
            "FailureInjector: configured %s (severity=%s, enabled=%s)",
            config.failure_type.value, config.severity.value, config.enabled,
        )

    def activate(self, failure_type: FailureType) -> None:
        """Activate a configured failure type."""
        if failure_type not in self._configs:
            raise ValueError(
                f"Failure type {failure_type.value} not configured"
            )
        config = self._configs[failure_type]
        config.enabled = True
        self._active_failures.add(failure_type)
        logger.info("FailureInjector: activated %s", failure_type.value)

    def deactivate(self, failure_type: FailureType) -> None:
        """Deactivate a failure type."""
        if failure_type in self._active_failures:
            self._active_failures.discard(failure_type)
            if failure_type in self._configs:
                self._configs[failure_type].enabled = False
        logger.info("FailureInjector: deactivated %s", failure_type.value)

    def deactivate_all(self) -> None:
        """Deactivate all failures."""
        for ft in list(self._active_failures):
            self.deactivate(ft)

    def register_drone(self, drone_id: int) -> None:
        """Register a drone for failure tracking."""
        self._drone_states[drone_id] = DroneFailureState(drone_id=drone_id)

    def get_drone_failure_state(self, drone_id: int) -> DroneFailureState:
        """Get current failure state for a drone."""
        if drone_id not in self._drone_states:
            raise ValueError(f"Drone {drone_id} not registered")
        return self._drone_states[drone_id]

    def apply_failures(
        self,
        drone_id: int,
        battery_pct: float,
        position_lat: float,
        position_lon: float,
        position_alt: float,
        dt_seconds: float = 1.0,
    ) -> dict:
        """
        Apply active failures to drone state for one simulation tick.

        Returns a dict of modified values. Does NOT make decisions —
        just modifies the physical simulation state.
        """
        if drone_id not in self._drone_states:
            self.register_drone(drone_id)

        state = self._drone_states[drone_id]
        result: dict = {
            "battery_pct": battery_pct,
            "position_lat": position_lat,
            "position_lon": position_lon,
            "position_alt": position_alt,
            "gps_available": True,
            "gps_accuracy_m": 1.0,
            "link_available": True,
            "link_quality_pct": 100.0,
            "wind_speed_m_s": 0.0,
            "wind_direction_deg": 0.0,
        }

        now_ms = int(time.monotonic() * 1000)

        for failure_type in self._active_failures:
            config = self._configs.get(failure_type)
            if not config or not config.enabled:
                continue

            if (
                config.target_drone_ids is not None
                and drone_id not in config.target_drone_ids
            ):
                continue

            if failure_type == FailureType.BATTERY_DEGRADATION:
                result = self._apply_battery_degradation(
                    drone_id, result, config, dt_seconds, now_ms,
                )
            elif failure_type == FailureType.GPS_LOSS:
                result = self._apply_gps_loss(
                    drone_id, result, config, now_ms,
                )
            elif failure_type == FailureType.LINK_LOSS:
                result = self._apply_link_loss(
                    drone_id, result, config, now_ms,
                )
            elif failure_type == FailureType.WIND_DISTURBANCE:
                result = self._apply_wind_disturbance(
                    drone_id, result, config, dt_seconds, now_ms,
                )

        state.battery_degradation_rate = (
            battery_pct - result["battery_pct"]
        ) / max(dt_seconds, 0.001)
        state.gps_available = result["gps_available"]
        state.gps_accuracy_m = result["gps_accuracy_m"]
        state.link_available = result["link_available"]
        state.link_quality_pct = result["link_quality_pct"]
        state.wind_speed_m_s = result["wind_speed_m_s"]
        state.wind_direction_deg = result["wind_direction_deg"]

        return result

    def _apply_battery_degradation(
        self, drone_id: int, result: dict,
        config: FailureConfig, dt_seconds: float, now_ms: int,
    ) -> dict:
        """Apply battery degradation. Severity controls rate."""
        rate_map = {
            FailureSeverity.LOW: 0.5,
            FailureSeverity.MEDIUM: 2.0,
            FailureSeverity.HIGH: 5.0,
            FailureSeverity.CRITICAL: 10.0,
        }
        rate = config.params.get(
            "rate_pct_per_sec", rate_map.get(config.severity, 2.0),
        )
        degradation = rate * dt_seconds
        new_battery = max(0.0, result["battery_pct"] - degradation)
        result["battery_pct"] = new_battery

        if new_battery < 10.0:
            self._log_event(
                FailureType.BATTERY_DEGRADATION, drone_id,
                config.severity,
                f"Battery critically low: {new_battery:.1f}%",
                now_ms,
            )

        return result

    def _apply_gps_loss(
        self, drone_id: int, result: dict,
        config: FailureConfig, now_ms: int,
    ) -> dict:
        """Apply GPS loss. Severity controls loss type."""
        if config.severity in (FailureSeverity.CRITICAL, FailureSeverity.HIGH):
            result["gps_available"] = False
            result["gps_accuracy_m"] = 999.0
            self._log_event(
                FailureType.GPS_LOSS, drone_id, config.severity,
                "GPS signal lost", now_ms,
            )
        else:
            accuracy = config.params.get("accuracy_m", 15.0)
            result["gps_accuracy_m"] = accuracy
            offset_m = self._rng.gauss(0, accuracy / 111000.0)
            result["position_lat"] += offset_m
            result["position_lon"] += offset_m

        return result

    def _apply_link_loss(
        self, drone_id: int, result: dict,
        config: FailureConfig, now_ms: int,
    ) -> dict:
        """Apply communication link loss."""
        if config.severity in (FailureSeverity.CRITICAL, FailureSeverity.HIGH):
            result["link_available"] = False
            result["link_quality_pct"] = 0.0
            self._log_event(
                FailureType.LINK_LOSS, drone_id, config.severity,
                "Communication link lost", now_ms,
            )
        else:
            quality = config.params.get("quality_pct", 30.0)
            result["link_quality_pct"] = quality

        return result

    def _apply_wind_disturbance(
        self, drone_id: int, result: dict,
        config: FailureConfig, dt_seconds: float, now_ms: int,
    ) -> dict:
        """Apply wind disturbance. Basic model: constant wind + gusts."""
        base_speed_map = {
            FailureSeverity.LOW: 3.0,
            FailureSeverity.MEDIUM: 8.0,
            FailureSeverity.HIGH: 15.0,
            FailureSeverity.CRITICAL: 25.0,
        }
        base_speed = config.params.get(
            "wind_speed_m_s",
            base_speed_map.get(config.severity, 8.0),
        )
        gust = self._rng.gauss(0, base_speed * 0.3)
        wind_speed = max(0.0, base_speed + gust)
        wind_dir = config.params.get(
            "wind_direction_deg",
            self._rng.uniform(0, 360),
        )

        result["wind_speed_m_s"] = wind_speed
        result["wind_direction_deg"] = wind_dir

        if result["position_alt"] > 0:
            drift_m = wind_speed * dt_seconds / 111000.0
            rad = math.radians(wind_dir)
            result["position_lat"] += drift_m * math.cos(rad)
            result["position_lon"] += drift_m * math.sin(rad)

        if wind_speed > 20.0:
            self._log_event(
                FailureType.WIND_DISTURBANCE, drone_id, config.severity,
                f"Severe wind: {wind_speed:.1f} m/s", now_ms,
            )

        return result

    def _log_event(
        self, failure_type: FailureType, drone_id: int,
        severity: FailureSeverity, description: str, now_ms: int,
    ) -> None:
        self._event_log.append(FailureEvent(
            failure_type=failure_type,
            drone_id=drone_id,
            severity=severity,
            description=description,
            timestamp_ms=now_ms,
        ))

    @property
    def event_log(self) -> list[FailureEvent]:
        """Read-only access to failure events."""
        return list(self._event_log)

    @property
    def active_failure_types(self) -> set[FailureType]:
        """Currently active failure types."""
        return set(self._active_failures)

    def is_active(self, failure_type: FailureType) -> bool:
        """Check if a failure type is active."""
        return failure_type in self._active_failures
