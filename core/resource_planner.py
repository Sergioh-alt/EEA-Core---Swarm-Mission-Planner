"""
Resource Planner Module

Estimates battery consumption, liquid usage, refill cycles,
and total mission duration for each drone and the overall swarm.
"""

import math
from dataclasses import dataclass

from config.settings import drone_spec, REFILL_TIME_MIN, BATTERY_SWAP_TIME_MIN
from core.battery_model import compute_battery_wh
from core.mission_intake import MissionProfile
from core.route_planner import RoutePlan, DroneRoute
from utils.logger import get_logger

logger = get_logger("resource_planner")


@dataclass
class DroneResources:
    drone_id: int
    battery_consumption_pct: float
    battery_flights_possible: int
    liquid_needed_l: float
    liquid_refills: int
    flight_time_min: float
    refill_time_min: float
    total_time_min: float


@dataclass
class ResourcePlan:
    drone_resources: list[DroneResources]
    total_battery_cycles: int
    total_liquid_l: float
    total_refills: int
    mission_duration_min: float
    mission_duration_formatted: str
    bottleneck: str



def plan_resources(
    profile: MissionProfile,
    route_plan: RoutePlan,
) -> ResourcePlan:
    logger.info("Planning resources for %d drones", profile.num_drones)

    drone_resources: list[DroneResources] = []

    for route in route_plan.routes:
        dr = _compute_drone_resources(route, profile)
        drone_resources.append(dr)

    total_battery_cycles = sum(dr.battery_flights_possible for dr in drone_resources)
    total_liquid = sum(dr.liquid_needed_l for dr in drone_resources)
    total_refills = sum(dr.liquid_refills for dr in drone_resources)
    max_drone_time = max(dr.total_time_min for dr in drone_resources) if drone_resources else 0

    duration_h = int(max_drone_time // 60)
    duration_m = int(max_drone_time % 60)
    formatted = f"{duration_h}h {duration_m:02d}m"

    bottleneck = _identify_bottleneck(drone_resources, profile)

    plan = ResourcePlan(
        drone_resources=drone_resources,
        total_battery_cycles=total_battery_cycles,
        total_liquid_l=round(total_liquid, 1),
        total_refills=total_refills,
        mission_duration_min=round(max_drone_time, 1),
        mission_duration_formatted=formatted,
        bottleneck=bottleneck,
    )

    logger.info(
        "Resources: duration=%s, liquid=%.1f L, refills=%d, bottleneck=%s",
        formatted, total_liquid, total_refills, bottleneck,
    )
    return plan


def _compute_drone_resources(
    route: DroneRoute,
    profile: MissionProfile,
) -> DroneResources:
    battery_wh, usable_battery_wh = compute_battery_wh(profile.battery_capacity_mah)
    distance_km = route.total_distance_m / 1000
    energy_needed_wh = distance_km * drone_spec.power_consumption_wh_per_km
    energy_needed_wh *= profile.complexity_multiplier

    battery_pct = (energy_needed_wh / battery_wh * 100) if battery_wh > 0 else 100
    battery_flights = max(1, int(1 / (battery_pct / 100))) if battery_pct > 0 else 1

    sector_area_ha = profile.field_size_ha / profile.num_drones
    liquid_needed = sector_area_ha * profile.spray_rate_l_per_ha
    loads_needed = math.ceil(liquid_needed / profile.liquid_capacity_l)
    liquid_refills = max(0, loads_needed - 1)

    battery_swaps = max(0, int(battery_pct / 100) - 1) if battery_pct > 100 else 0
    refill_time = liquid_refills * REFILL_TIME_MIN + battery_swaps * BATTERY_SWAP_TIME_MIN
    total_time = route.estimated_time_min + refill_time

    return DroneResources(
        drone_id=route.drone_id,
        battery_consumption_pct=round(min(battery_pct, 999), 1),
        battery_flights_possible=battery_flights,
        liquid_needed_l=round(liquid_needed, 1),
        liquid_refills=liquid_refills,
        flight_time_min=round(route.estimated_time_min, 1),
        refill_time_min=round(refill_time, 1),
        total_time_min=round(total_time, 1),
    )


def _identify_bottleneck(
    resources: list[DroneResources],
    profile: MissionProfile,
) -> str:
    if not resources:
        return "None"

    max_battery = max(dr.battery_consumption_pct for dr in resources)
    max_refills = max(dr.liquid_refills for dr in resources)

    if max_battery > 100 and max_refills > 2:
        return "Battery and Liquid — both require multiple cycles"
    if max_battery > 100:
        return "Battery — requires swap mid-mission"
    if max_refills > 2:
        return "Liquid — multiple refill cycles needed"
    if max_battery > 80:
        return "Battery — operating near capacity limit"
    return "None — resources within operational limits"
