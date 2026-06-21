"""
Route Planner Module

Generates simplified boustrophedon (back-and-forth) route plans
for each drone sector, avoiding overlapping coverage.
"""

from dataclasses import dataclass

from config.settings import drone_spec
from core.swarm_planner import Sector, SwarmPlan
from core.environment_analyzer import EnvironmentAssessment
from utils.logger import get_logger

logger = get_logger("route_planner")


@dataclass
class Waypoint:
    x: float
    y: float
    sequence: int


@dataclass
class DroneRoute:
    drone_id: int
    sector_id: int
    waypoints: list[Waypoint]
    num_passes: int
    total_distance_m: float
    estimated_time_min: float
    overlap_pct: float


@dataclass
class RoutePlan:
    routes: list[DroneRoute]
    total_distance_m: float
    total_flight_time_min: float
    efficiency_score: float


def plan_routes(
    swarm: SwarmPlan,
    assessment: EnvironmentAssessment,
) -> RoutePlan:
    logger.info("Planning routes for %d sectors", len(swarm.sectors))

    speed_kmh = assessment.recommended_speed_kmh
    spray_width = assessment.effective_spray_width_m
    routes: list[DroneRoute] = []

    for sector in swarm.sectors:
        route = _generate_sector_route(sector, spray_width, speed_kmh)
        routes.append(route)

    total_dist = sum(r.total_distance_m for r in routes)
    total_time = sum(r.estimated_time_min for r in routes)
    max_time = max(r.estimated_time_min for r in routes) if routes else 0

    covered_area = sum(
        r.num_passes * spray_width * _sector_pass_length(swarm.sectors[i])
        for i, r in enumerate(routes)
    )
    field_area = swarm.field_width_m * swarm.field_height_m
    efficiency = min(covered_area / field_area, 1.0) if field_area > 0 else 0

    plan = RoutePlan(
        routes=routes,
        total_distance_m=round(total_dist, 1),
        total_flight_time_min=round(max_time, 1),
        efficiency_score=round(efficiency, 3),
    )

    logger.info(
        "Route plan: total_dist=%.0f m, parallel_time=%.1f min, efficiency=%.1f%%",
        total_dist, max_time, efficiency * 100,
    )
    return plan


def _generate_sector_route(
    sector: Sector,
    spray_width: float,
    speed_kmh: float,
) -> DroneRoute:
    num_passes = max(1, int(sector.width_m / spray_width))
    overlap_pct = 0.0
    actual_spacing = sector.width_m / num_passes

    if actual_spacing < spray_width:
        overlap_pct = (spray_width - actual_spacing) / spray_width * 100

    waypoints: list[Waypoint] = []
    seq = 0
    for p in range(num_passes):
        x = sector.x_start + actual_spacing * p + actual_spacing / 2
        if p % 2 == 0:
            waypoints.append(Waypoint(x=round(x, 1), y=round(sector.y_start, 1), sequence=seq))
            seq += 1
            waypoints.append(Waypoint(x=round(x, 1), y=round(sector.y_end, 1), sequence=seq))
        else:
            waypoints.append(Waypoint(x=round(x, 1), y=round(sector.y_end, 1), sequence=seq))
            seq += 1
            waypoints.append(Waypoint(x=round(x, 1), y=round(sector.y_start, 1), sequence=seq))
        seq += 1

    pass_length = sector.height_m
    total_distance = num_passes * pass_length
    turn_distance = (num_passes - 1) * actual_spacing
    total_distance += turn_distance

    speed_ms = speed_kmh / 3.6
    flight_time_s = total_distance / speed_ms if speed_ms > 0 else 0
    turn_time_s = (num_passes - 1) * drone_spec.turn_time_s
    takeoff_landing_s = drone_spec.takeoff_landing_s
    total_time_min = (flight_time_s + turn_time_s + takeoff_landing_s) / 60

    return DroneRoute(
        drone_id=sector.drone_id,
        sector_id=sector.id,
        waypoints=waypoints,
        num_passes=num_passes,
        total_distance_m=round(total_distance, 1),
        estimated_time_min=round(total_time_min, 1),
        overlap_pct=round(overlap_pct, 1),
    )


def _sector_pass_length(sector: Sector) -> float:
    return sector.height_m
