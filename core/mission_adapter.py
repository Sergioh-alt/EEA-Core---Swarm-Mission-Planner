"""
Mission Adapter (Phase 7.3)

Handles mid-mission condition changes by evaluating triggers and
producing adaptation recommendations. The adapter is strictly
recommendation-based — it never makes autonomous execution decisions.

Supported triggers:
- wind_change: recalculate environment + risk → may recommend abort
- resource_depletion: evaluate remaining capacity → may recommend return
- partial_completion: replan remaining sectors only

This module is purely additive — it does not modify any existing
pipeline module. All recomputation delegates to existing functions:
- analyze_environment()
- plan_swarm()
- plan_routes()
- plan_resources()
- evaluate_risks()
- generate_timeline()

Consumers: UI dashboard (future), operator approval workflow
Dependencies: MissionState (Phase 7.1), existing pipeline modules
"""

from dataclasses import dataclass
from typing import Optional

from config.settings import weather_thresholds
from core.swarm_state import MissionState, DroneStatus
from core.mission_intake import MissionProfile, create_mission_profile
from core.environment_analyzer import EnvironmentAssessment, analyze_environment
from core.swarm_planner import SwarmPlan, plan_swarm
from core.route_planner import RoutePlan, plan_routes
from core.resource_planner import plan_resources
from core.risk_engine import evaluate_risks
from core.mission_timeline import generate_timeline, MissionTimeline
from utils.logger import get_logger

logger = get_logger("mission_adapter")


@dataclass
class AdaptationTrigger:
    """Describes a mid-mission condition change."""
    trigger_type: str       # "wind_change", "resource_depletion", "partial_completion"
    timestamp_min: float
    details: dict


@dataclass
class AdaptationResult:
    """Recommendation produced by the adapter. Requires operator approval."""
    trigger: AdaptationTrigger
    action: str             # "continue", "modify", "abort"
    modified_profile: Optional[MissionProfile]
    modified_plan: Optional[SwarmPlan]
    modified_routes: Optional[RoutePlan]
    modified_timeline: Optional[MissionTimeline]
    explanation: str


def adapt_mission(
    state: MissionState,
    trigger: AdaptationTrigger,
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
) -> AdaptationResult:
    """
    Evaluate a mid-mission condition change and produce a recommendation.

    This function does NOT execute the adaptation — it returns a
    recommendation that the operator must approve before any changes
    take effect. No autonomous execution decisions.

    Delegates all recomputation to existing pipeline functions.
    """
    if trigger.trigger_type == "wind_change":
        return _handle_wind_change(state, trigger, profile, assessment)
    elif trigger.trigger_type == "resource_depletion":
        return _handle_resource_depletion(state, trigger, profile, assessment)
    elif trigger.trigger_type == "partial_completion":
        return _handle_partial_completion(state, trigger, profile, assessment)
    else:
        raise ValueError(f"Unknown trigger type: {trigger.trigger_type}")


def _handle_wind_change(
    state: MissionState,
    trigger: AdaptationTrigger,
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
) -> AdaptationResult:
    """
    Handle wind speed change during mission.

    Strategy:
    1. Create modified profile with new wind speed
    2. Re-evaluate environment via analyze_environment()
    3. Re-evaluate risks via evaluate_risks()
    4. If NO-GO conditions: recommend abort
    5. If degraded but viable: recommend modify with replanned routes
    6. If still optimal: recommend continue
    """
    new_wind = trigger.details.get("new_wind_kmh", profile.wind_speed_kmh)
    old_wind = profile.wind_speed_kmh

    logger.info(
        "Wind change trigger: %.1f → %.1f km/h at t=%.1f min",
        old_wind, new_wind, trigger.timestamp_min,
    )

    # Abort threshold: wind exceeds no-fly limit
    if new_wind >= weather_thresholds.max_wind_kmh:
        return AdaptationResult(
            trigger=trigger,
            action="abort",
            modified_profile=None,
            modified_plan=None,
            modified_routes=None,
            modified_timeline=None,
            explanation=(
                f"Wind increased to {new_wind:.1f} km/h — exceeds "
                f"no-fly threshold ({weather_thresholds.max_wind_kmh:.1f} km/h). "
                f"Recommend immediate mission abort."
            ),
        )

    # Recompute with new wind using existing pipeline functions
    modified_profile = create_mission_profile(
        field_size_ha=profile.field_size_ha,
        crop_type=profile.crop_type,
        num_drones=profile.num_drones,
        battery_capacity_mah=profile.battery_capacity_mah,
        liquid_capacity_l=profile.liquid_capacity_l,
        temperature_c=profile.temperature_c,
        wind_speed_kmh=new_wind,
        field_geometry=profile.field_geometry,
    )
    new_assessment = analyze_environment(modified_profile)
    new_swarm = plan_swarm(modified_profile, new_assessment)
    new_routes = plan_routes(new_swarm, new_assessment)
    new_resources = plan_resources(modified_profile, new_routes)
    new_risks = evaluate_risks(
        modified_profile, new_assessment, new_resources, new_routes,
    )

    # Check if the mission is still viable after wind change
    if not new_risks.mission_viable:
        return AdaptationResult(
            trigger=trigger,
            action="abort",
            modified_profile=modified_profile,
            modified_plan=new_swarm,
            modified_routes=new_routes,
            modified_timeline=None,
            explanation=(
                f"Wind changed {old_wind:.1f} → {new_wind:.1f} km/h. "
                f"Risk assessment: mission no longer viable "
                f"(risk score {new_risks.overall_score:.2f}). "
                f"Recommend mission abort."
            ),
        )

    # Wind changed but mission still viable — recommend modification
    new_timeline = generate_timeline(modified_profile, new_routes, new_resources)

    # Determine if this is significant enough to require modification
    wind_delta = abs(new_wind - old_wind)
    if wind_delta < 5.0 and new_assessment.flight_conditions == assessment.flight_conditions:
        return AdaptationResult(
            trigger=trigger,
            action="continue",
            modified_profile=None,
            modified_plan=None,
            modified_routes=None,
            modified_timeline=None,
            explanation=(
                f"Wind changed {old_wind:.1f} → {new_wind:.1f} km/h "
                f"(Δ{wind_delta:.1f}). Change is within tolerance. "
                f"Recommend continue with current plan."
            ),
        )

    return AdaptationResult(
        trigger=trigger,
        action="modify",
        modified_profile=modified_profile,
        modified_plan=new_swarm,
        modified_routes=new_routes,
        modified_timeline=new_timeline,
        explanation=(
            f"Wind changed {old_wind:.1f} → {new_wind:.1f} km/h "
            f"(Δ{wind_delta:.1f}). Mission still viable but plan "
            f"should be updated. New duration: "
            f"{new_timeline.mission_duration_formatted}. "
            f"Recommend plan modification."
        ),
    )


def _handle_resource_depletion(
    state: MissionState,
    trigger: AdaptationTrigger,
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
) -> AdaptationResult:
    """
    Handle resource depletion (battery or liquid) during mission.

    Strategy:
    1. Identify which drones are critically low
    2. If all drones critically low: recommend abort
    3. If some drones low: recommend modify (return low drones, continue rest)
    4. If depletion is manageable: recommend continue
    """
    battery_threshold_pct = trigger.details.get("battery_threshold_pct", 15.0)
    liquid_threshold_l = trigger.details.get("liquid_threshold_l", 1.0)

    critical_drones = []
    for drone in state.drones:
        if drone.status == DroneStatus.FAILED:
            continue
        battery_low = drone.battery_remaining_pct <= battery_threshold_pct
        liquid_low = drone.liquid_remaining_l <= liquid_threshold_l
        if battery_low or liquid_low:
            reasons = []
            if battery_low:
                reasons.append(f"battery {drone.battery_remaining_pct:.1f}%")
            if liquid_low:
                reasons.append(f"liquid {drone.liquid_remaining_l:.1f}L")
            critical_drones.append((drone, reasons))

    if not critical_drones:
        return AdaptationResult(
            trigger=trigger,
            action="continue",
            modified_profile=None,
            modified_plan=None,
            modified_routes=None,
            modified_timeline=None,
            explanation=(
                f"Resource check at t={trigger.timestamp_min:.1f} min: "
                f"all drones within acceptable thresholds. "
                f"Recommend continue."
            ),
        )

    # Count active (non-failed, non-critical) drones
    active_non_critical = [
        d for d in state.drones
        if d.status not in (DroneStatus.FAILED, DroneStatus.COMPLETED)
        and d.drone_id not in {cd.drone_id for cd, _ in critical_drones}
    ]

    critical_ids = [d.drone_id for d, _ in critical_drones]
    critical_details = "; ".join(
        f"Drone {d.drone_id}: {', '.join(r)}" for d, r in critical_drones
    )

    if not active_non_critical:
        return AdaptationResult(
            trigger=trigger,
            action="abort",
            modified_profile=None,
            modified_plan=None,
            modified_routes=None,
            modified_timeline=None,
            explanation=(
                f"All active drones critically depleted: {critical_details}. "
                f"No drones available to continue. "
                f"Recommend mission abort."
            ),
        )

    return AdaptationResult(
        trigger=trigger,
        action="modify",
        modified_profile=None,
        modified_plan=None,
        modified_routes=None,
        modified_timeline=None,
        explanation=(
            f"Resource depletion detected: {critical_details}. "
            f"Recommend returning drones {critical_ids} for "
            f"refill/swap. {len(active_non_critical)} drone(s) "
            f"can continue operations."
        ),
    )


def _handle_partial_completion(
    state: MissionState,
    trigger: AdaptationTrigger,
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
) -> AdaptationResult:
    """
    Handle partial mission completion — replan remaining sectors.

    Strategy:
    1. Identify completed vs remaining sectors
    2. If all sectors done: recommend continue (mission wrapping up)
    3. Build a plan for remaining sectors only using existing pipeline
    4. Recommend modification with replanned routes
    """
    completed_sector_ids = set(state.sectors_completed)
    remaining_sector_ids = state.sectors_remaining

    if not remaining_sector_ids:
        return AdaptationResult(
            trigger=trigger,
            action="continue",
            modified_profile=None,
            modified_plan=None,
            modified_routes=None,
            modified_timeline=None,
            explanation=(
                f"All sectors completed at t={trigger.timestamp_min:.1f} min. "
                f"Coverage: {state.coverage_pct:.1f}%. "
                f"Recommend continue to mission completion."
            ),
        )

    # Count available drones for remaining work
    available_drones = [
        d for d in state.drones
        if d.status in (DroneStatus.IDLE, DroneStatus.ACTIVE, DroneStatus.COMPLETED)
    ]

    if not available_drones:
        return AdaptationResult(
            trigger=trigger,
            action="abort",
            modified_profile=None,
            modified_plan=None,
            modified_routes=None,
            modified_timeline=None,
            explanation=(
                f"Partial completion at t={trigger.timestamp_min:.1f} min. "
                f"{len(remaining_sector_ids)} sector(s) remaining but "
                f"no drones available. Recommend mission abort."
            ),
        )

    # Replan with available drone count for remaining work
    remaining_drone_count = min(len(available_drones), len(remaining_sector_ids))

    modified_profile = create_mission_profile(
        field_size_ha=profile.field_size_ha,
        crop_type=profile.crop_type,
        num_drones=remaining_drone_count,
        battery_capacity_mah=profile.battery_capacity_mah,
        liquid_capacity_l=profile.liquid_capacity_l,
        temperature_c=profile.temperature_c,
        wind_speed_kmh=profile.wind_speed_kmh,
        field_geometry=profile.field_geometry,
    )
    new_assessment = analyze_environment(modified_profile)
    new_swarm = plan_swarm(modified_profile, new_assessment)
    new_routes = plan_routes(new_swarm, new_assessment)
    new_resources = plan_resources(modified_profile, new_routes)
    new_timeline = generate_timeline(modified_profile, new_routes, new_resources)

    return AdaptationResult(
        trigger=trigger,
        action="modify",
        modified_profile=modified_profile,
        modified_plan=new_swarm,
        modified_routes=new_routes,
        modified_timeline=new_timeline,
        explanation=(
            f"Partial completion at t={trigger.timestamp_min:.1f} min. "
            f"{len(completed_sector_ids)} sector(s) done, "
            f"{len(remaining_sector_ids)} remaining. "
            f"Replanned with {remaining_drone_count} drone(s). "
            f"Estimated remaining time: "
            f"{new_timeline.mission_duration_formatted}."
        ),
    )
