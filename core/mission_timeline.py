"""
Mission Timeline Engine (Phase 6)

Generates a human-readable mission execution timeline per drone:
- Launch (takeoff + climb)
- Transit (to sector start)
- Spraying (passes, split by refills)
- Refill (liquid reload events)
- Battery swap (if consumption > 100%)
- Return (descent + landing)
- Mission complete

Output is structured for UI rendering and export.

Assumptions:
- Transit to sector: 30 seconds (short-range, same-field)
- Spray time derived from route distance / effective speed
- Refills split spraying into segments
- Battery swaps occur at end of spray phase (conservative)
- Return descent ~20% slower than climb
"""

from dataclasses import dataclass

from core.mission_intake import MissionProfile
from core.route_planner import RoutePlan, DroneRoute
from core.resource_planner import ResourcePlan
from core.battery_model import BatteryEstimate, estimate_battery
from core.liquid_model import LiquidEstimate, estimate_liquid
from core.drone_physics import (
    DronePhysicsResult,
    analyze_drone_physics,
    physics_config,
)
from utils.logger import get_logger

logger = get_logger("mission_timeline")

TRANSIT_DURATION_MIN = 0.5


@dataclass
class TimelineEvent:
    """A single event in the mission timeline."""
    timestamp_min: float
    timestamp_formatted: str
    drone_id: int
    event_type: str
    description: str
    duration_min: float


@dataclass
class DroneTimeline:
    """Complete timeline for a single drone."""
    drone_id: int
    events: list[TimelineEvent]
    total_duration_min: float
    total_duration_formatted: str
    spray_time_min: float
    transit_time_min: float
    idle_time_min: float
    physics: DronePhysicsResult
    battery: BatteryEstimate
    liquid: LiquidEstimate


@dataclass
class MissionTimeline:
    """Complete mission timeline for all drones."""
    drone_timelines: list[DroneTimeline]
    mission_duration_min: float
    mission_duration_formatted: str
    total_events: int
    summary: str


def _format_time(minutes: float) -> str:
    """Format minutes into human-readable string."""
    h = int(minutes // 60)
    m = int(minutes % 60)
    s = int((minutes % 1) * 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"


def generate_timeline(
    profile: MissionProfile,
    route_plan: RoutePlan,
    resource_plan: ResourcePlan,
) -> MissionTimeline:
    """Generate mission execution timeline for all drones."""
    logger.info("Generating mission timeline for %d drones", len(route_plan.routes))

    drone_timelines: list[DroneTimeline] = []

    for i, route in enumerate(route_plan.routes):
        physics = analyze_drone_physics(
            recommended_speed_kmh=25.0,
            wind_speed_kmh=profile.wind_speed_kmh,
            liquid_capacity_l=profile.liquid_capacity_l,
            num_passes=route.num_passes,
        )

        battery = estimate_battery(
            drone_id=route.drone_id,
            distance_m=route.total_distance_m,
            flight_time_min=route.estimated_time_min,
            wind_speed_kmh=profile.wind_speed_kmh,
            liquid_capacity_l=profile.liquid_capacity_l,
            battery_capacity_mah=profile.battery_capacity_mah,
            complexity_multiplier=profile.complexity_multiplier,
        )

        sector_area_ha = profile.field_size_ha / profile.num_drones
        liquid = estimate_liquid(
            drone_id=route.drone_id,
            sector_area_ha=sector_area_ha,
            spray_rate_l_per_ha=profile.spray_rate_l_per_ha,
            tank_capacity_l=profile.liquid_capacity_l,
            crop_type=profile.crop_type,
        )

        timeline = _build_drone_timeline(route, physics, battery, liquid, profile)
        drone_timelines.append(timeline)

    mission_duration = max(dt.total_duration_min for dt in drone_timelines) if drone_timelines else 0
    total_events = sum(len(dt.events) for dt in drone_timelines)
    duration_formatted = _format_time(mission_duration)

    summary_lines = [
        f"Mission Duration: {duration_formatted}",
        f"Drones: {len(drone_timelines)}",
        f"Total Events: {total_events}",
    ]

    logger.info(
        "Timeline: duration=%s, drones=%d, events=%d",
        duration_formatted, len(drone_timelines), total_events,
    )

    return MissionTimeline(
        drone_timelines=drone_timelines,
        mission_duration_min=round(mission_duration, 1),
        mission_duration_formatted=duration_formatted,
        total_events=total_events,
        summary="\n".join(summary_lines),
    )


def _build_drone_timeline(
    route: DroneRoute,
    physics: DronePhysicsResult,
    battery: BatteryEstimate,
    liquid: LiquidEstimate,
    profile: MissionProfile,
) -> DroneTimeline:
    """Build event timeline for a single drone."""
    events: list[TimelineEvent] = []
    t = 0.0
    spray_time = 0.0
    transit_time = 0.0
    idle_time = 0.0

    # 1. Launch
    climb_time_min = (profile.flight_altitude_m / physics_config.climb_rate_ms) / 60
    events.append(TimelineEvent(
        timestamp_min=round(t, 2),
        timestamp_formatted=_format_time(t),
        drone_id=route.drone_id,
        event_type="launch",
        description=f"Takeoff and climb to {profile.flight_altitude_m:.0f}m",
        duration_min=round(climb_time_min, 2),
    ))
    t += climb_time_min
    idle_time += climb_time_min

    # 2. Transit to sector
    events.append(TimelineEvent(
        timestamp_min=round(t, 2),
        timestamp_formatted=_format_time(t),
        drone_id=route.drone_id,
        event_type="transit",
        description="Transit to sector start position",
        duration_min=TRANSIT_DURATION_MIN,
    ))
    t += TRANSIT_DURATION_MIN
    transit_time += TRANSIT_DURATION_MIN

    # 3. Spraying passes (split by refill events)
    total_spray_min = route.estimated_time_min

    if liquid.refill_events:
        passes_per_load = route.num_passes / liquid.loads_needed if liquid.loads_needed > 0 else route.num_passes

        for load_idx in range(liquid.loads_needed):
            if load_idx == liquid.loads_needed - 1:
                segment_passes = route.num_passes - int(passes_per_load) * (liquid.loads_needed - 1)
            else:
                segment_passes = int(passes_per_load)

            spray_segment = (total_spray_min / route.num_passes) * segment_passes if route.num_passes > 0 else 0

            events.append(TimelineEvent(
                timestamp_min=round(t, 2),
                timestamp_formatted=_format_time(t),
                drone_id=route.drone_id,
                event_type="spraying",
                description=f"Spraying load {load_idx + 1}/{liquid.loads_needed} (~{segment_passes} passes)",
                duration_min=round(spray_segment, 2),
            ))
            t += spray_segment
            spray_time += spray_segment

            if load_idx < liquid.loads_needed - 1:
                refill = liquid.refill_events[load_idx]
                events.append(TimelineEvent(
                    timestamp_min=round(t, 2),
                    timestamp_formatted=_format_time(t),
                    drone_id=route.drone_id,
                    event_type="refill",
                    description=f"Liquid refill #{refill.event_number} ({profile.liquid_capacity_l:.0f}L)",
                    duration_min=refill.refill_duration_min,
                ))
                t += refill.refill_duration_min
                idle_time += refill.refill_duration_min
    else:
        events.append(TimelineEvent(
            timestamp_min=round(t, 2),
            timestamp_formatted=_format_time(t),
            drone_id=route.drone_id,
            event_type="spraying",
            description=f"Spraying ({route.num_passes} passes, continuous)",
            duration_min=round(total_spray_min, 2),
        ))
        t += total_spray_min
        spray_time += total_spray_min

    # 4. Battery swap if needed
    for swap_idx in range(battery.battery_swaps_needed):
        events.append(TimelineEvent(
            timestamp_min=round(t, 2),
            timestamp_formatted=_format_time(t),
            drone_id=route.drone_id,
            event_type="battery_swap",
            description=f"Battery swap #{swap_idx + 1}",
            duration_min=3.0,
        ))
        t += 3.0
        idle_time += 3.0

    # 5. Return transit
    descend_time_min = (profile.flight_altitude_m / physics_config.descend_rate_ms) / 60
    events.append(TimelineEvent(
        timestamp_min=round(t, 2),
        timestamp_formatted=_format_time(t),
        drone_id=route.drone_id,
        event_type="return",
        description="Return to base and descend",
        duration_min=round(descend_time_min + TRANSIT_DURATION_MIN, 2),
    ))
    t += descend_time_min + TRANSIT_DURATION_MIN
    transit_time += descend_time_min + TRANSIT_DURATION_MIN

    # 6. Mission complete
    events.append(TimelineEvent(
        timestamp_min=round(t, 2),
        timestamp_formatted=_format_time(t),
        drone_id=route.drone_id,
        event_type="complete",
        description="Mission complete",
        duration_min=0,
    ))

    return DroneTimeline(
        drone_id=route.drone_id,
        events=events,
        total_duration_min=round(t, 1),
        total_duration_formatted=_format_time(t),
        spray_time_min=round(spray_time, 1),
        transit_time_min=round(transit_time, 1),
        idle_time_min=round(idle_time, 1),
        physics=physics,
        battery=battery,
        liquid=liquid,
    )
