"""
Route Planner Module

Generates simplified boustrophedon (back-and-forth) route plans
for each drone sector, avoiding overlapping coverage.

Supports two strategies:
- Rectangular route (v0.1 compat): for grid-partitioned sectors
- Polygon sweep route (v0.2): for strip-partitioned polygon sectors
"""

import math
from dataclasses import dataclass

from shapely.geometry import LineString
from shapely.affinity import rotate

from config.settings import drone_spec
from core.geometry import compute_polygon_orientation
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

    use_polygon = swarm.partition_method == "strip"

    for sector in swarm.sectors:
        if use_polygon and sector.boundary is not None:
            route = _generate_polygon_route(sector, spray_width, speed_kmh)
        else:
            route = _generate_sector_route(sector, spray_width, speed_kmh)
        routes.append(route)

    total_dist = sum(r.total_distance_m for r in routes)
    max_time = max(r.estimated_time_min for r in routes) if routes else 0

    if use_polygon:
        field_area = sum(s.area_ha * 10000 for s in swarm.sectors)
        covered_area = sum(
            r.num_passes * spray_width * _sector_polygon_pass_length(swarm.sectors[i])
            for i, r in enumerate(routes)
        )
    else:
        field_area = swarm.field_width_m * swarm.field_height_m
        covered_area = sum(
            r.num_passes * spray_width * _sector_pass_length(swarm.sectors[i])
            for i, r in enumerate(routes)
        )

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


# ---------------------------------------------------------------------------
# v0.1-compatible rectangular route generation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# v0.2 polygon-aware sweep-line route generation
# ---------------------------------------------------------------------------

def _generate_polygon_route(
    sector: Sector,
    spray_width: float,
    speed_kmh: float,
) -> DroneRoute:
    """Generate boustrophedon route within a convex polygon sector."""
    polygon = sector.boundary
    orientation_deg = compute_polygon_orientation(polygon)

    centroid = polygon.centroid
    cx, cy = centroid.x, centroid.y
    rotated = rotate(polygon, -orientation_deg, origin=(cx, cy))

    rminx, rminy, rmaxx, rmaxy = rotated.bounds
    sweep_width = rmaxx - rminx

    num_passes = max(1, int(sweep_width / spray_width))
    actual_spacing = sweep_width / num_passes

    overlap_pct = 0.0
    if actual_spacing < spray_width:
        overlap_pct = (spray_width - actual_spacing) / spray_width * 100

    waypoints_rotated: list[tuple[float, float]] = []
    pass_lengths: list[float] = []

    for p in range(num_passes):
        sweep_x = rminx + actual_spacing * p + actual_spacing / 2

        sweep_line = LineString([(sweep_x, rminy - 1), (sweep_x, rmaxy + 1)])
        intersection = rotated.intersection(sweep_line)

        if intersection.is_empty:
            continue

        if intersection.geom_type == "LineString":
            coords = list(intersection.coords)
            y_vals = sorted([c[1] for c in coords])
            y_bottom = y_vals[0]
            y_top = y_vals[-1]
        elif intersection.geom_type == "Point":
            y_bottom = intersection.y
            y_top = intersection.y
        else:
            bounds = intersection.bounds
            y_bottom = bounds[1]
            y_top = bounds[3]

        pass_length = y_top - y_bottom
        pass_lengths.append(pass_length)

        if p % 2 == 0:
            waypoints_rotated.append((sweep_x, y_bottom))
            waypoints_rotated.append((sweep_x, y_top))
        else:
            waypoints_rotated.append((sweep_x, y_top))
            waypoints_rotated.append((sweep_x, y_bottom))

    actual_passes = len(pass_lengths)

    waypoints: list[Waypoint] = []
    angle_rad = math.radians(orientation_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    for seq, (rx, ry) in enumerate(waypoints_rotated):
        dx = rx - cx
        dy = ry - cy
        ox = cx + dx * cos_a - dy * sin_a
        oy = cy + dx * sin_a + dy * cos_a
        waypoints.append(Waypoint(x=round(ox, 1), y=round(oy, 1), sequence=seq))

    total_pass_distance = sum(pass_lengths)
    turn_distance = (actual_passes - 1) * actual_spacing if actual_passes > 1 else 0
    total_distance = total_pass_distance + turn_distance

    speed_ms = speed_kmh / 3.6
    flight_time_s = total_distance / speed_ms if speed_ms > 0 else 0
    turn_time_s = (actual_passes - 1) * drone_spec.turn_time_s if actual_passes > 1 else 0
    takeoff_landing_s = drone_spec.takeoff_landing_s
    total_time_min = (flight_time_s + turn_time_s + takeoff_landing_s) / 60

    return DroneRoute(
        drone_id=sector.drone_id,
        sector_id=sector.id,
        waypoints=waypoints,
        num_passes=actual_passes,
        total_distance_m=round(total_distance, 1),
        estimated_time_min=round(total_time_min, 1),
        overlap_pct=round(overlap_pct, 1),
    )


def _sector_polygon_pass_length(sector: Sector) -> float:
    """Average pass length for polygon sectors."""
    if sector.boundary is None:
        return sector.height_m

    polygon = sector.boundary
    mabr = polygon.minimum_rotated_rectangle
    coords = list(mabr.exterior.coords)

    edge1_len = math.dist(coords[0], coords[1])
    edge2_len = math.dist(coords[1], coords[2])

    return min(edge1_len, edge2_len)
