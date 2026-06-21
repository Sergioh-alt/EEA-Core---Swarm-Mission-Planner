"""
Swarm Planner Module

Partitions the field into sectors and assigns each sector to a drone,
balancing workload across the swarm.
"""

import math
from dataclasses import dataclass

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


@dataclass
class SwarmPlan:
    sectors: list[Sector]
    grid_cols: int
    grid_rows: int
    field_width_m: float
    field_height_m: float
    area_per_drone_ha: float
    balance_score: float


def plan_swarm(
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
) -> SwarmPlan:
    logger.info(
        "Planning swarm: %d drones for %.1f ha",
        profile.num_drones, profile.field_size_ha,
    )

    field_width_m, field_height_m = _estimate_field_dimensions(profile.field_size_m2)
    grid_cols, grid_rows = _compute_grid(profile.num_drones)
    sectors = _partition_field(
        profile.num_drones, grid_cols, grid_rows,
        field_width_m, field_height_m, profile.field_size_ha,
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
    )

    logger.info(
        "Swarm plan: %dx%d grid, %.2f ha/drone, balance=%.3f",
        grid_cols, grid_rows, area_per_drone, balance_score,
    )
    return plan


def _estimate_field_dimensions(area_m2: float) -> tuple[float, float]:
    side = math.sqrt(area_m2)
    width = side * 1.2
    height = area_m2 / width
    return round(width, 1), round(height, 1)


def _compute_grid(num_drones: int) -> tuple[int, int]:
    cols = math.ceil(math.sqrt(num_drones))
    rows = math.ceil(num_drones / cols)
    return cols, rows


def _partition_field(
    num_drones: int,
    cols: int,
    rows: int,
    field_w: float,
    field_h: float,
    total_ha: float,
) -> list[Sector]:
    sector_w = field_w / cols
    sector_h = field_h / rows
    total_cells = cols * rows
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
        ))

    return sectors
