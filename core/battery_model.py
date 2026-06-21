"""
Realistic Battery Model (Phase 6)

Deterministic battery consumption based on:
- Route distance (base energy = distance * Wh/km)
- Payload weight (heavier payload = more lift power)
- Wind conditions (drag increases energy consumption)
- Mission duration (hover/idle drain during non-cruise phases)

All factors are explainable and reproducible.

Assumptions:
- Base power: 15.0 Wh/km (from DroneSpec)
- Battery voltage: 22.2 V (6S LiPo)
- Reserve: 15% minimum
- Payload: 1 kg per liter of liquid
- Hover power: 150 W during idle/turn phases (~10% of mission)
- Battery swap time: 3 minutes
"""

from dataclasses import dataclass

from config.settings import drone_spec, BATTERY_SWAP_TIME_MIN
from core.drone_physics import (
    physics_config,
    compute_payload_power_factor,
    compute_wind_power_factor,
)
from utils.logger import get_logger

logger = get_logger("battery_model")


def compute_battery_wh(battery_capacity_mah: float) -> tuple[float, float]:
    """Convert mAh capacity to (total_wh, usable_wh) using DroneSpec constants."""
    total_wh = battery_capacity_mah * drone_spec.battery_voltage / 1000
    usable_wh = total_wh * (1 - drone_spec.min_battery_reserve_pct / 100)
    return total_wh, usable_wh


@dataclass
class BatteryEstimate:
    """Detailed battery consumption estimate for a single drone."""
    drone_id: int
    base_consumption_wh: float
    wind_penalty_wh: float
    payload_penalty_wh: float
    hover_consumption_wh: float
    total_consumption_wh: float
    battery_capacity_wh: float
    usable_capacity_wh: float
    consumption_pct: float
    flights_per_charge: int
    battery_swaps_needed: int
    swap_time_min: float
    assumptions: list[str]


def estimate_battery(
    drone_id: int,
    distance_m: float,
    flight_time_min: float,
    wind_speed_kmh: float,
    liquid_capacity_l: float,
    battery_capacity_mah: float,
    complexity_multiplier: float = 1.0,
) -> BatteryEstimate:
    """Estimate battery consumption with physics-based factors."""
    battery_wh, usable_wh = compute_battery_wh(battery_capacity_mah)

    distance_km = distance_m / 1000
    base_wh = distance_km * drone_spec.power_consumption_wh_per_km

    payload_kg = liquid_capacity_l * physics_config.liquid_density_kg_per_l
    payload_factor = compute_payload_power_factor(payload_kg)
    payload_penalty_wh = base_wh * (payload_factor - 1.0)

    wind_factor = compute_wind_power_factor(wind_speed_kmh)
    wind_penalty_wh = base_wh * (wind_factor - 1.0)

    non_flight_min = max(0, flight_time_min * 0.1)
    hover_wh = physics_config.hover_power_w * (non_flight_min / 60)

    total_wh = (base_wh + payload_penalty_wh + wind_penalty_wh + hover_wh) * complexity_multiplier

    consumption_pct = (total_wh / battery_wh * 100) if battery_wh > 0 else 100
    flights_per_charge = max(1, int(usable_wh / total_wh)) if total_wh > 0 else 1
    swaps = max(0, int(consumption_pct / 100) - 1) if consumption_pct > 100 else 0
    swap_time = swaps * BATTERY_SWAP_TIME_MIN

    assumptions = [
        f"Base power: {drone_spec.power_consumption_wh_per_km} Wh/km",
        f"Battery: {battery_wh:.0f} Wh ({drone_spec.min_battery_reserve_pct}% reserve)",
        f"Payload: {payload_kg:.1f} kg (+{(payload_factor - 1) * 100:.1f}% power)",
        f"Wind: {wind_speed_kmh:.0f} km/h (+{(wind_factor - 1) * 100:.1f}% power)",
        f"Hover drain: {hover_wh:.1f} Wh ({non_flight_min:.1f} min idle)",
        f"Complexity: x{complexity_multiplier}",
    ]

    logger.info(
        "Battery drone %d: base=%.1f Wh, wind=+%.1f, payload=+%.1f, hover=+%.1f, total=%.1f Wh (%.0f%%)",
        drone_id, base_wh, wind_penalty_wh, payload_penalty_wh, hover_wh, total_wh, consumption_pct,
    )

    return BatteryEstimate(
        drone_id=drone_id,
        base_consumption_wh=round(base_wh, 1),
        wind_penalty_wh=round(wind_penalty_wh, 1),
        payload_penalty_wh=round(payload_penalty_wh, 1),
        hover_consumption_wh=round(hover_wh, 1),
        total_consumption_wh=round(total_wh, 1),
        battery_capacity_wh=round(battery_wh, 1),
        usable_capacity_wh=round(usable_wh, 1),
        consumption_pct=round(min(consumption_pct, 999), 1),
        flights_per_charge=flights_per_charge,
        battery_swaps_needed=swaps,
        swap_time_min=round(swap_time, 1),
        assumptions=assumptions,
    )
