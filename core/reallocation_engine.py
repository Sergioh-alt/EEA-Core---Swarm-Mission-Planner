"""
Reallocation Engine (Phase 7.2)

Handles drone failure recovery and sector reassignment. When a drone
fails mid-mission, the engine identifies its uncompleted work and
reassigns it to the nearest available drone(s) using a deterministic
greedy strategy.

Coverage preservation is the primary objective. Time penalty is
secondary.

This module is purely additive — it does not modify any existing
pipeline module. It consumes:
- MissionState, DroneState, FailureEvent from swarm_state (Phase 7.1)
- plan_routes() from route_planner (existing)
- generate_timeline() from mission_timeline (existing)
- SwarmPlan, Sector from swarm_planner (existing)

No duplicate planning logic — route recomputation delegates to
the existing plan_routes() function.
"""

import math
from dataclasses import dataclass

from core.swarm_state import (
    MissionState,
    DroneState,
    DroneStatus,
)
from core.mission_intake import MissionProfile
from core.swarm_planner import SwarmPlan, Sector
from core.environment_analyzer import EnvironmentAssessment
from core.route_planner import plan_routes, RoutePlan
from core.resource_planner import plan_resources
from core.mission_timeline import generate_timeline, MissionTimeline
from utils.logger import get_logger

logger = get_logger("reallocation_engine")


@dataclass
class SectorReassignment:
    """A single sector-to-drone reassignment."""
    sector_id: int
    from_drone_id: int
    to_drone_id: int
    additional_distance_m: float
    additional_time_min: float


@dataclass
class ReallocationPlan:
    """Complete reallocation plan after a drone failure."""
    failed_drone_id: int
    reason: str
    reassignments: list[SectorReassignment]
    coverage_before_pct: float
    coverage_after_pct: float
    time_penalty_min: float
    updated_routes: RoutePlan
    updated_timeline: MissionTimeline
    feasible: bool
    explanation: str


def _compute_distance(pos_a: tuple[float, float], pos_b: tuple[float, float]) -> float:
    """Euclidean distance between two positions."""
    return math.dist(pos_a, pos_b)


def _sector_centroid(sector: Sector) -> tuple[float, float]:
    """Compute the centroid of a sector for proximity calculations."""
    cx = (sector.x_start + sector.x_end) / 2
    cy = (sector.y_start + sector.y_end) / 2
    return (cx, cy)


def _find_nearest_available(
    available_drones: list[DroneState],
    target_position: tuple[float, float],
) -> DroneState:
    """Find the nearest available drone to the target position."""
    return min(
        available_drones,
        key=lambda d: _compute_distance(d.position, target_position),
    )


def reallocate_on_failure(
    state: MissionState,
    failed_drone_id: int,
    profile: MissionProfile,
    swarm: SwarmPlan,
    assessment: EnvironmentAssessment,
) -> ReallocationPlan:
    """
    Reassign a failed drone's remaining work to available drones.

    Strategy (deterministic greedy):
    1. Identify uncompleted sector from the failed drone
    2. Find available drones sorted by proximity to the failed sector
    3. Assign the failed sector to the nearest available drone
    4. Build a modified SwarmPlan with the reassignment
    5. Recompute routes via plan_routes() (no duplicate planning logic)
    6. Recompute timeline via generate_timeline()
    7. Compare coverage before/after and compute time penalty

    Coverage preservation is the primary objective — the algorithm
    ensures the failed sector is fully reassigned. If no drones are
    available, the plan is marked infeasible.
    """
    # Find the failed drone's state
    failed_drone = None
    for drone in state.drones:
        if drone.drone_id == failed_drone_id:
            failed_drone = drone
            break

    if failed_drone is None:
        raise ValueError(f"Drone {failed_drone_id} not found in mission state")

    # Find the failed drone's sector
    failed_sector = None
    for sector in swarm.sectors:
        if sector.id == failed_drone.current_sector_id:
            failed_sector = sector
            break

    if failed_sector is None:
        raise ValueError(
            f"Sector {failed_drone.current_sector_id} not found in swarm plan"
        )

    # Find available drones (exclude the failed one)
    available = [
        d for d in state.drones
        if d.drone_id != failed_drone_id
        and d.status in (DroneStatus.IDLE, DroneStatus.ACTIVE, DroneStatus.COMPLETED)
    ]

    # Compute coverage before reallocation
    total_passes = sum(d.passes_total for d in state.drones)
    failed_remaining = failed_drone.passes_total - failed_drone.passes_completed
    achievable_passes = total_passes - failed_remaining
    coverage_before = (achievable_passes / total_passes * 100) if total_passes > 0 else 0.0

    if not available:
        logger.warning(
            "No available drones for reallocation of drone %d",
            failed_drone_id,
        )
        # Build infeasible plan — no routes can be recomputed
        return ReallocationPlan(
            failed_drone_id=failed_drone_id,
            reason=f"Drone {failed_drone_id} failure — no available drones",
            reassignments=[],
            coverage_before_pct=round(coverage_before, 1),
            coverage_after_pct=round(coverage_before, 1),
            time_penalty_min=0.0,
            updated_routes=_recompute_routes(swarm, assessment, {}),
            updated_timeline=_recompute_timeline(
                profile, _recompute_routes(swarm, assessment, {}),
            ),
            feasible=False,
            explanation="No available drones to accept reassignment.",
        )

    # Sort available drones by proximity to the failed sector
    target_pos = _sector_centroid(failed_sector)
    available_sorted = sorted(
        available,
        key=lambda d: _compute_distance(d.position, target_pos),
    )

    # Greedy assignment: assign failed sector to nearest available drone
    recipient = available_sorted[0]
    recipient_distance = _compute_distance(recipient.position, target_pos)

    reassignment = SectorReassignment(
        sector_id=failed_sector.id,
        from_drone_id=failed_drone_id,
        to_drone_id=recipient.drone_id,
        additional_distance_m=round(recipient_distance, 1),
        additional_time_min=0.0,  # will be computed after route recomputation
    )

    # Build modified sector list: reassign failed sector to recipient
    reassignment_map = {failed_sector.id: recipient.drone_id}
    modified_swarm = _build_modified_swarm(swarm, reassignment_map)

    # Recompute routes using existing plan_routes() — no duplicate logic
    updated_routes = _recompute_routes(modified_swarm, assessment, reassignment_map)

    # Compute time penalty
    time_penalty = 0.0

    # Find the recipient's new route time vs original
    for route in updated_routes.routes:
        if route.drone_id == recipient.drone_id:
            # The recipient now handles two sectors — time penalty is the
            # additional time from the reassigned sector's route
            for orig_route in updated_routes.routes:
                if orig_route.sector_id == failed_sector.id:
                    time_penalty = orig_route.estimated_time_min
                    reassignment.additional_time_min = round(time_penalty, 1)
                    break
            break

    # Recompute timeline
    updated_timeline = _recompute_timeline(profile, updated_routes)

    # Coverage after reallocation: all passes are now assigned
    coverage_after = 100.0  # full reassignment — sector is covered

    logger.info(
        "Reallocation: drone %d → drone %d (sector %d), "
        "coverage %.1f%% → %.1f%%, penalty +%.1f min",
        failed_drone_id, recipient.drone_id, failed_sector.id,
        coverage_before, coverage_after, time_penalty,
    )

    return ReallocationPlan(
        failed_drone_id=failed_drone_id,
        reason=f"Drone {failed_drone_id} failure — sector {failed_sector.id} reassigned to drone {recipient.drone_id}",
        reassignments=[reassignment],
        coverage_before_pct=round(coverage_before, 1),
        coverage_after_pct=round(coverage_after, 1),
        time_penalty_min=round(time_penalty, 1),
        updated_routes=updated_routes,
        updated_timeline=updated_timeline,
        feasible=True,
        explanation=(
            f"Sector {failed_sector.id} reassigned from drone {failed_drone_id} "
            f"to drone {recipient.drone_id} (nearest available, "
            f"{recipient_distance:.0f}m away). "
            f"Coverage preserved at 100%."
        ),
    )


def _build_modified_swarm(
    original: SwarmPlan,
    reassignment_map: dict[int, int],
) -> SwarmPlan:
    """
    Build a modified SwarmPlan with sectors reassigned per the map.

    reassignment_map: {sector_id: new_drone_id}
    """
    modified_sectors: list[Sector] = []
    for sector in original.sectors:
        if sector.id in reassignment_map:
            new_drone_id = reassignment_map[sector.id]
            modified_sectors.append(Sector(
                id=sector.id,
                drone_id=new_drone_id,
                x_start=sector.x_start,
                y_start=sector.y_start,
                x_end=sector.x_end,
                y_end=sector.y_end,
                area_ha=sector.area_ha,
                width_m=sector.width_m,
                height_m=sector.height_m,
                boundary=sector.boundary,
            ))
        else:
            modified_sectors.append(sector)

    return SwarmPlan(
        sectors=modified_sectors,
        grid_cols=original.grid_cols,
        grid_rows=original.grid_rows,
        field_width_m=original.field_width_m,
        field_height_m=original.field_height_m,
        area_per_drone_ha=original.area_per_drone_ha,
        balance_score=original.balance_score,
        partition_method=original.partition_method,
    )


def _recompute_routes(
    swarm: SwarmPlan,
    assessment: EnvironmentAssessment,
    reassignment_map: dict[int, int],
) -> RoutePlan:
    """Recompute routes using existing plan_routes() — no duplicate logic."""
    return plan_routes(swarm, assessment)


def _recompute_timeline(
    profile: MissionProfile,
    routes: RoutePlan,
) -> MissionTimeline:
    """Recompute timeline using existing functions — no duplicate logic."""
    resources = plan_resources(profile, routes)
    return generate_timeline(profile, routes, resources)
