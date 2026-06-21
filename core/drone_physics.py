"""
Drone Physics Layer (Phase 6)

Provides deterministic physics calculations for drone operations:
- Speed constraints (min/max bounds)
- Turn penalties (deceleration + arc + acceleration)
- Payload impact (weight reduces speed and increases power)
- Wind impact (drag reduces ground speed, increases power)

No advanced aerodynamics. All models are explainable and deterministic.

Assumptions:
- Wind modeled as average headwind (worst-case direction)
- Payload approximated as 1 kg per liter of liquid
- Turn modeled as half-circle at reduced speed
- Power impact from wind follows simplified drag model
"""

from dataclasses import dataclass

from config.settings import drone_spec
from utils.logger import get_logger

logger = get_logger("drone_physics")


@dataclass
class PhysicsConfig:
    """Drone physics parameters (Phase 6 constants)."""
    drone_empty_weight_kg: float = 5.0
    max_payload_kg: float = 15.0
    min_speed_ms: float = 3.0
    max_speed_ms: float = 12.0
    turn_deceleration_factor: float = 0.6
    turn_radius_m: float = 2.0
    wind_drag_coefficient: float = 0.15
    payload_speed_penalty_per_kg: float = 0.02
    payload_power_penalty_per_kg: float = 0.03
    hover_power_w: float = 150.0
    climb_rate_ms: float = 2.0
    descend_rate_ms: float = 1.5
    liquid_density_kg_per_l: float = 1.0


physics_config = PhysicsConfig()


@dataclass
class DronePhysicsResult:
    """Physics analysis result for a drone mission segment."""
    effective_speed_ms: float
    effective_speed_kmh: float
    speed_reduction_wind_pct: float
    speed_reduction_payload_pct: float
    turn_penalty_s: float
    total_turn_time_s: float
    payload_weight_kg: float
    wind_power_factor: float
    payload_power_factor: float


def compute_effective_speed(
    base_speed_kmh: float,
    wind_speed_kmh: float,
    payload_kg: float,
) -> tuple[float, float, float]:
    """
    Compute effective ground speed considering wind and payload.

    Returns: (effective_speed_ms, wind_reduction_pct, payload_reduction_pct)
    """
    base_ms = base_speed_kmh / 3.6

    wind_ms = wind_speed_kmh / 3.6
    wind_reduction = wind_ms * physics_config.wind_drag_coefficient
    wind_reduction_pct = (wind_reduction / base_ms * 100) if base_ms > 0 else 0

    payload_reduction_pct = payload_kg * physics_config.payload_speed_penalty_per_kg * 100
    payload_reduction = base_ms * (payload_reduction_pct / 100)

    effective = base_ms - wind_reduction - payload_reduction
    effective = max(physics_config.min_speed_ms, min(effective, physics_config.max_speed_ms))

    return effective, round(wind_reduction_pct, 1), round(payload_reduction_pct, 1)


def compute_turn_penalty(num_turns: int, speed_ms: float) -> tuple[float, float]:
    """
    Compute time penalty for boustrophedon turns.

    Returns: (penalty_per_turn_s, total_penalty_s)
    """
    if num_turns <= 0 or speed_ms <= 0:
        return 0.0, 0.0

    speed_diff = speed_ms * (1 - physics_config.turn_deceleration_factor)
    decel_time = speed_diff / speed_ms if speed_ms > 0 else 0
    turn_speed = speed_ms * physics_config.turn_deceleration_factor
    turn_arc = 3.14159 * physics_config.turn_radius_m
    turn_time = turn_arc / turn_speed if turn_speed > 0 else drone_spec.turn_time_s
    accel_time = decel_time

    penalty_per_turn = decel_time + turn_time + accel_time
    return round(penalty_per_turn, 3), round(penalty_per_turn * num_turns, 1)


def compute_payload_power_factor(payload_kg: float) -> float:
    """Power consumption multiplier due to payload weight."""
    return 1.0 + payload_kg * physics_config.payload_power_penalty_per_kg


def compute_wind_power_factor(wind_speed_kmh: float) -> float:
    """Power consumption multiplier due to wind resistance."""
    wind_ms = wind_speed_kmh / 3.6
    drag_term = wind_ms * physics_config.wind_drag_coefficient
    return 1.0 + drag_term ** 2 * 0.01


def compute_climb_time_s(altitude_m: float) -> float:
    """Time in seconds to climb to altitude."""
    return altitude_m / physics_config.climb_rate_ms


def compute_descend_time_s(altitude_m: float) -> float:
    """Time in seconds to descend from altitude."""
    return altitude_m / physics_config.descend_rate_ms


def analyze_drone_physics(
    recommended_speed_kmh: float,
    wind_speed_kmh: float,
    liquid_capacity_l: float,
    num_passes: int,
) -> DronePhysicsResult:
    """Full physics analysis for a drone mission segment."""
    payload_kg = liquid_capacity_l * physics_config.liquid_density_kg_per_l

    eff_speed_ms, wind_red, payload_red = compute_effective_speed(
        recommended_speed_kmh, wind_speed_kmh, payload_kg
    )

    num_turns = max(0, num_passes - 1)
    turn_penalty, total_turn_time = compute_turn_penalty(num_turns, eff_speed_ms)

    wind_pf = compute_wind_power_factor(wind_speed_kmh)
    payload_pf = compute_payload_power_factor(payload_kg)

    logger.info(
        "Physics: eff_speed=%.1f km/h, wind_red=%.1f%%, payload=%.1f kg, turns=%d (%.1f s)",
        eff_speed_ms * 3.6, wind_red, payload_kg, num_turns, total_turn_time,
    )

    return DronePhysicsResult(
        effective_speed_ms=round(eff_speed_ms, 2),
        effective_speed_kmh=round(eff_speed_ms * 3.6, 1),
        speed_reduction_wind_pct=wind_red,
        speed_reduction_payload_pct=payload_red,
        turn_penalty_s=turn_penalty,
        total_turn_time_s=total_turn_time,
        payload_weight_kg=round(payload_kg, 1),
        wind_power_factor=round(wind_pf, 4),
        payload_power_factor=round(payload_pf, 4),
    )
