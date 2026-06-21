"""
Liquid Consumption Model (Phase 6)

Consumption based on:
- Field area per drone
- Crop type and spray rate
- Tank capacity
- Refill event estimation

Assumptions:
- Spray rate is uniform across the sector
- Refill time: 5 minutes per event
- Liquid consumption = area * spray_rate
- Refills triggered when tank runs empty
"""

import math
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger("liquid_model")

REFILL_DURATION_MIN = 5.0


@dataclass
class RefillEvent:
    """A single refill event during the mission."""
    event_number: int
    trigger_after_ha: float
    liquid_consumed_l: float
    refill_duration_min: float


@dataclass
class LiquidEstimate:
    """Detailed liquid consumption estimate for a single drone."""
    drone_id: int
    sector_area_ha: float
    spray_rate_l_per_ha: float
    total_liquid_needed_l: float
    tank_capacity_l: float
    loads_needed: int
    refill_events: list[RefillEvent]
    total_refill_time_min: float
    ha_per_load: float
    assumptions: list[str]


def estimate_liquid(
    drone_id: int,
    sector_area_ha: float,
    spray_rate_l_per_ha: float,
    tank_capacity_l: float,
    crop_type: str = "generic",
) -> LiquidEstimate:
    """Estimate liquid consumption and refill events for a drone."""
    total_liquid = sector_area_ha * spray_rate_l_per_ha
    loads_needed = math.ceil(total_liquid / tank_capacity_l) if tank_capacity_l > 0 else 1
    num_refills = max(0, loads_needed - 1)

    ha_per_load = tank_capacity_l / spray_rate_l_per_ha if spray_rate_l_per_ha > 0 else sector_area_ha

    refill_events: list[RefillEvent] = []
    for i in range(num_refills):
        trigger_ha = ha_per_load * (i + 1)
        refill_events.append(RefillEvent(
            event_number=i + 1,
            trigger_after_ha=round(trigger_ha, 2),
            liquid_consumed_l=round(tank_capacity_l, 1),
            refill_duration_min=REFILL_DURATION_MIN,
        ))

    total_refill_time = num_refills * REFILL_DURATION_MIN

    assumptions = [
        f"Spray rate: {spray_rate_l_per_ha} L/ha ({crop_type})",
        f"Tank capacity: {tank_capacity_l} L",
        f"Coverage per load: {ha_per_load:.2f} ha",
        f"Refill time: {REFILL_DURATION_MIN} min per event",
    ]

    logger.info(
        "Liquid drone %d: %.1f ha, %.1f L needed, %d loads, %d refills",
        drone_id, sector_area_ha, total_liquid, loads_needed, num_refills,
    )

    return LiquidEstimate(
        drone_id=drone_id,
        sector_area_ha=round(sector_area_ha, 2),
        spray_rate_l_per_ha=spray_rate_l_per_ha,
        total_liquid_needed_l=round(total_liquid, 1),
        tank_capacity_l=tank_capacity_l,
        loads_needed=loads_needed,
        refill_events=refill_events,
        total_refill_time_min=round(total_refill_time, 1),
        ha_per_load=round(ha_per_load, 2),
        assumptions=assumptions,
    )
