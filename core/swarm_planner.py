"""
Swarm Planner Module

Partitions the field into sectors and assigns each sector to a drone,
balancing workload across the swarm.

Supports two partitioning strategies:
- Grid partition (v0.1 compat): for synthetic rectangular fields
- Strip partition (v0.2): for user-drawn polygon fields
"""

import math
from dataclasses import dataclass, field
from typing import Optional

from shapely.geometry import Polygon, box
from shapely.affinity import rotate

from core.geometry import FieldGeometry, compute_polygon_orientation
from core.mission_intake import MissionProfile
from core.environment_analyzer import EnvironmentAssessment
from utils.logger import get_logger

logger = get_logger("swarm_planner")


@dataclass
class Sector:
    id: int
    drone_id: int
    x_start: float
    y_start: float
    x_end: float
    y_end: float
    area_ha: float
    width_m: float
    height_m: float
    boundary: Optional[Polygon] = field(default=None, repr=False)


@dataclass
class SwarmPlan:
    sectors: list[Sector]
    grid_cols: int
    grid_rows: int
    field_width_m: float
    field_height_m: float
    area_per_drone_ha: float
    balance_score: float
    partition_method: str = "grid"


def plan_swarm(
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
) -> SwarmPlan:
    logger.info(
        "Planning swarm: %d drones for %.1f ha",
        profile.num_drones, profile.field_size_ha,
    )

    geometry = profile.field_geometry

    if geometry.is_synthetic:
        return _plan_grid(profile, geometry)
    else:
        return _plan_strips(profile, geometry)


def _plan_grid(profile: MissionProfile, geometry: FieldGeometry) -> SwarmPlan:
    """v0.1-identical grid partition for synthetic rectangular fields."""
    minx, miny, maxx, maxy = geometry.bounds
    field_width_m = maxx - minx
    field_height_m = maxy - miny

    grid_cols, grid_rows = _compute_grid(profile.num_drones)
    sectors = _partition_field_grid(
        profile.num_drones, grid_cols, grid_rows,
        field_width_m, field_height_m,
    )

    area_per_drone = profile.field_size_ha / profile.num_drones
    areas = [s.area_ha for s in sectors]
    balance_score = 1.0 - (max(areas) - min(areas)) / max(areas) if areas else 1.0

    plan = SwarmPlan(
        sectors=sectors,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
        field_width_m=field_width_m,
        field_height_m=field_height_m,
        area_per_drone_ha=round(area_per_drone, 2),
        balance_score=round(balance_score, 3),
        partition_method="grid",
    )

    logger.info(
        "Swarm plan (grid): %dx%d grid, %.2f ha/drone, balance=%.3f",
        grid_cols, grid_rows, area_per_drone, balance_score,
    )
    return plan


def _plan_strips(profile: MissionProfile, geometry: FieldGeometry) -> SwarmPlan:
    """Strip partition for user-drawn polygon fields."""
    num_drones = profile.num_drones
    field_polygon = geometry.boundary

    orientation_deg = compute_polygon_orientation(field_polygon)
    strips = _partition_polygon_strips(field_polygon, num_drones, orientation_deg)

    sectors: list[Sector] = []
    for i, strip_poly in enumerate(strips):
        bx0, by0, bx1, by1 = strip_poly.bounds
        centroid = strip_poly.centroid
        area_ha = round(strip_poly.area / 10000, 2)

        sectors.append(Sector(
            id=i + 1,
            drone_id=i + 1,
            x_start=round(bx0, 1),
            y_start=round(by0, 1),
            x_end=round(bx1, 1),
            y_end=round(by1, 1),
            area_ha=area_ha,
            width_m=round(bx1 - bx0, 1),
            height_m=round(by1 - by0, 1),
            boundary=strip_poly,
        ))

    minx, miny, maxx, maxy = geometry.bounds
    field_width_m = maxx - minx
    field_height_m = maxy - miny

    area_per_drone = geometry.area_ha / num_drones
    areas = [s.area_ha for s in sectors]
    balance_score = 1.0 - (max(areas) - min(areas)) / max(areas) if areas else 1.0

    plan = SwarmPlan(
        sectors=sectors,
        grid_cols=num_drones,
        grid_rows=1,
        field_width_m=round(field_width_m, 1),
        field_height_m=round(field_height_m, 1),
        area_per_drone_ha=round(area_per_drone, 2),
        balance_score=round(balance_score, 3),
        partition_method="strip",
    )

    logger.info(
        "Swarm plan (strip): %d strips, %.2f ha/drone, balance=%.3f, orientation=%.1f deg",
        num_drones, area_per_drone, balance_score, orientation_deg,
    )
    return plan


def _partition_polygon_strips(
    polygon: Polygon,
    num_strips: int,
    orientation_deg: float,
) -> list[Polygon]:
    """
    Partition a polygon into N strips aligned to its MABR orientation.

    1. Rotate polygon so the long axis is horizontal
    2. Divide the bounding box into N vertical strips
    3. Clip each strip to the rotated polygon
    4. Rotate back to original orientation
    """
    centroid = polygon.centroid
    cx, cy = centroid.x, centroid.y

    rotated = rotate(polygon, -orientation_deg, origin=(cx, cy))
    rminx, rminy, rmaxx, rmaxy = rotated.bounds

    strip_width = (rmaxx - rminx) / num_strips

    strips: list[Polygon] = []
    for i in range(num_strips):
        sx0 = rminx + i * strip_width
        sx1 = rminx + (i + 1) * strip_width

        if i == num_strips - 1:
            sx1 = rmaxx

        strip_box = box(sx0, rminy, sx1, rmaxy)
        clipped = rotated.intersection(strip_box)

        if clipped.is_empty or clipped.area < 0.01:
            continue

        if not isinstance(clipped, Polygon):
            if hasattr(clipped, 'geoms'):
                largest = max(clipped.geoms, key=lambda g: g.area)
                if isinstance(largest, Polygon):
                    clipped = largest
                else:
                    continue
            else:
                continue

        original = rotate(clipped, orientation_deg, origin=(cx, cy))
        strips.append(original)

    return strips


def _compute_grid(num_drones: int) -> tuple[int, int]:
    cols = math.ceil(math.sqrt(num_drones))
    rows = math.ceil(num_drones / cols)
    return cols, rows


def _partition_field_grid(
    num_drones: int,
    cols: int,
    rows: int,
    field_w: float,
    field_h: float,
) -> list[Sector]:
    """v0.1-identical grid partition for rectangular fields."""
    sector_w = field_w / cols
    sector_h = field_h / rows
    sectors: list[Sector] = []

    for i in range(num_drones):
        row = i // cols
        col = i % cols

        x_start = col * sector_w
        y_start = row * sector_h
        x_end = x_start + sector_w
        y_end = y_start + sector_h

        if col == cols - 1:
            x_end = field_w
        if row == rows - 1:
            y_end = field_h

        w = x_end - x_start
        h = y_end - y_start
        area_ha = (w * h) / 10000

        boundary = box(x_start, y_start, x_end, y_end)

        sectors.append(Sector(
            id=i + 1,
            drone_id=i + 1,
            x_start=round(x_start, 1),
            y_start=round(y_start, 1),
            x_end=round(x_end, 1),
            y_end=round(y_end, 1),
            area_ha=round(area_ha, 2),
            width_m=round(w, 1),
            height_m=round(h, 1),
            boundary=boundary,
        ))

    return sectors
