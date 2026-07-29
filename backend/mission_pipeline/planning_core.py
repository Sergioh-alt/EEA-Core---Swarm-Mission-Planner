"""
Mission Definition Pipeline — Planning Core integration.

Converts a MissionDefinition into a MissionPackage by orchestrating the
EXISTING core/ planning pipeline. This module contains NO planning, routing,
optimization, or allocation algorithms of its own — it only:

    1. derives the core MissionProfile inputs from the operator's definition,
    2. runs the same chain the Streamlit app already uses, and
    3. serializes the results into a transport-friendly Mission Package.

Chain (identical to app.py):
    create_mission_profile -> analyze_environment -> plan_swarm -> plan_routes
    -> plan_resources -> evaluate_risks -> generate_recommendation
    -> generate_timeline
"""

from __future__ import annotations

import time

from core.decision_engine import MissionRecommendation, generate_recommendation
from core.environment_analyzer import EnvironmentAssessment, analyze_environment
from core.geometry import FieldGeometry
from core.mission_intake import MissionProfile, create_mission_profile
from core.mission_timeline import MissionTimeline, generate_timeline
from core.resource_planner import ResourcePlan, plan_resources
from core.risk_engine import RiskAssessment, evaluate_risks
from core.route_planner import RoutePlan, plan_routes
from core.swarm_planner import plan_swarm
from utils.validators import ValidationResult

from backend.mission_pipeline.models import MissionDefinition, MissionPackage
from backend.serializers import JSONObject

_DEFAULT_BATTERY_MAH = 16000.0
_DEFAULT_LIQUID_L = 10.0
_DEFAULT_FIELD_HA = 10.0


def build_mission_package(definition: MissionDefinition) -> MissionPackage:
    """Run the Planning Core on a definition and assemble a Mission Package."""
    profile = _profile_from_definition(definition)

    assessment = analyze_environment(profile)
    swarm = plan_swarm(profile, assessment)
    routes = plan_routes(swarm, assessment)
    resources = plan_resources(profile, routes)
    risks = evaluate_risks(profile, assessment, resources, routes)
    recommendation = generate_recommendation(
        profile, assessment, swarm, routes, resources, risks
    )
    timeline = generate_timeline(profile, routes, resources)

    return MissionPackage(
        definition_id=definition.id,
        generated_ms=int(time.time() * 1000),
        field_geometry=_geometry_to_json(profile.field_geometry),
        routes=_routes_to_json(routes),
        resources=_resources_to_json(resources),
        timeline=_timeline_to_json(timeline),
        risks=_risks_to_json(risks),
        recommendation=_recommendation_to_json(recommendation),
        environment_assessment=_assessment_to_json(assessment),
        validation=_validation_to_json(profile.validation),
        execution=_execution_to_json(definition, profile, routes),
    )


# ---------------------------------------------------------------------------
# Definition -> core MissionProfile
# ---------------------------------------------------------------------------


def _profile_from_definition(definition: MissionDefinition) -> MissionProfile:
    geometry = _geometry_from_definition(definition)

    if geometry is not None:
        field_size_ha = geometry.area_ha
    elif definition.field.area_ha and definition.field.area_ha > 0:
        field_size_ha = definition.field.area_ha
    else:
        field_size_ha = _DEFAULT_FIELD_HA

    num_drones = (
        len(definition.fleet)
        if definition.fleet
        else max(1, definition.operation.num_drones)
    )
    battery_mah, liquid_l = _representative_capacities(definition)

    return create_mission_profile(
        field_size_ha=field_size_ha,
        crop_type=definition.field.crop_type,
        num_drones=num_drones,
        battery_capacity_mah=battery_mah,
        liquid_capacity_l=liquid_l,
        temperature_c=definition.environment.temperature_c,
        wind_speed_kmh=definition.environment.wind_speed_kmh,
        field_geometry=geometry,
    )


def _geometry_from_definition(definition: MissionDefinition):
    """Real geometry from user-drawn vertices, else None (synthetic fallback)."""
    points = definition.field.boundary_points
    if len(points) >= 3:
        return FieldGeometry.from_points(points)
    return None


def _representative_capacities(definition: MissionDefinition) -> tuple[float, float]:
    """
    Homogeneous representative capacities for the current Planning Core.

    The core assumes a homogeneous fleet, so for a (possibly heterogeneous)
    selection we take the conservative minimum. True per-drone heterogeneity is
    a later sub-phase (10D.5); here we only feed the existing profile shape.
    """
    if not definition.fleet:
        return _DEFAULT_BATTERY_MAH, _DEFAULT_LIQUID_L
    battery = min(item.battery_capacity_mah for item in definition.fleet)
    liquid = min(item.liquid_capacity_l for item in definition.fleet)
    return battery, liquid


# ---------------------------------------------------------------------------
# core dataclasses -> JSON (exact field mirrors; no Any / getattr)
# ---------------------------------------------------------------------------


def _geometry_to_json(geometry: FieldGeometry) -> JSONObject:
    minx, miny, maxx, maxy = geometry.bounds
    exterior = list(geometry.boundary.exterior.coords)
    return {
        "area_m2": round(geometry.area_m2, 2),
        "area_ha": round(geometry.area_ha, 3),
        "perimeter_m": round(geometry.perimeter_m, 2),
        "is_synthetic": geometry.is_synthetic,
        "centroid": [geometry.centroid[0], geometry.centroid[1]],
        "bounds": [minx, miny, maxx, maxy],
        "boundary_points": [[float(x), float(y)] for (x, y) in exterior],
    }


def _routes_to_json(plan: RoutePlan) -> list[JSONObject]:
    return [
        {
            "drone_id": route.drone_id,
            "sector_id": route.sector_id,
            "num_passes": route.num_passes,
            "total_distance_m": route.total_distance_m,
            "estimated_time_min": route.estimated_time_min,
            "overlap_pct": route.overlap_pct,
            "waypoints": [
                {"x": wp.x, "y": wp.y, "sequence": wp.sequence}
                for wp in route.waypoints
            ],
        }
        for route in plan.routes
    ]


def _resources_to_json(plan: ResourcePlan) -> JSONObject:
    return {
        "total_battery_cycles": plan.total_battery_cycles,
        "total_liquid_l": plan.total_liquid_l,
        "total_refills": plan.total_refills,
        "mission_duration_min": plan.mission_duration_min,
        "mission_duration_formatted": plan.mission_duration_formatted,
        "bottleneck": plan.bottleneck,
        "drone_resources": [
            {
                "drone_id": dr.drone_id,
                "battery_consumption_pct": dr.battery_consumption_pct,
                "battery_flights_possible": dr.battery_flights_possible,
                "liquid_needed_l": dr.liquid_needed_l,
                "liquid_refills": dr.liquid_refills,
                "flight_time_min": dr.flight_time_min,
                "refill_time_min": dr.refill_time_min,
                "total_time_min": dr.total_time_min,
            }
            for dr in plan.drone_resources
        ],
    }


def _timeline_to_json(timeline: MissionTimeline) -> JSONObject:
    return {
        "mission_duration_min": timeline.mission_duration_min,
        "mission_duration_formatted": timeline.mission_duration_formatted,
        "total_events": timeline.total_events,
        "summary": timeline.summary,
        "drone_timelines": [
            {
                "drone_id": dt.drone_id,
                "total_duration_min": dt.total_duration_min,
                "total_duration_formatted": dt.total_duration_formatted,
                "spray_time_min": dt.spray_time_min,
                "transit_time_min": dt.transit_time_min,
                "idle_time_min": dt.idle_time_min,
                "events": [
                    {
                        "timestamp_min": ev.timestamp_min,
                        "timestamp_formatted": ev.timestamp_formatted,
                        "drone_id": ev.drone_id,
                        "event_type": ev.event_type,
                        "description": ev.description,
                        "duration_min": ev.duration_min,
                    }
                    for ev in dt.events
                ],
            }
            for dt in timeline.drone_timelines
        ],
    }


def _risks_to_json(risks: RiskAssessment) -> JSONObject:
    return {
        "overall_risk": risks.overall_risk,
        "overall_score": risks.overall_score,
        "mission_viable": risks.mission_viable,
        "critical_risks": list(risks.critical_risks),
        "risks": [
            {
                "category": r.category,
                "level": r.level,
                "score": r.score,
                "description": r.description,
                "mitigation": r.mitigation,
            }
            for r in risks.risks
        ],
    }


def _recommendation_to_json(rec: MissionRecommendation) -> JSONObject:
    return {
        "feasible": rec.feasible,
        "confidence_pct": rec.confidence_pct,
        "coverage_pct": rec.coverage_pct,
        "estimated_duration": rec.estimated_duration,
        "recommended_drones": rec.recommended_drones,
        "operational_notes": list(rec.operational_notes),
        "optimization_suggestions": list(rec.optimization_suggestions),
        "go_no_go": rec.go_no_go,
        "summary": rec.summary,
    }


def _assessment_to_json(assessment: EnvironmentAssessment) -> JSONObject:
    return {
        "area_category": assessment.area_category,
        "operational_complexity": assessment.operational_complexity,
        "weather_status": assessment.weather_status,
        "weather_details": assessment.weather_details,
        "wind_assessment": assessment.wind_assessment,
        "temperature_assessment": assessment.temperature_assessment,
        "flight_conditions": assessment.flight_conditions,
        "recommended_speed_kmh": assessment.recommended_speed_kmh,
        "effective_spray_width_m": assessment.effective_spray_width_m,
    }


def _validation_to_json(validation: ValidationResult) -> JSONObject:
    return {
        "valid": validation.valid,
        "errors": list(validation.errors),
        "warnings": list(validation.warnings),
    }


def _execution_to_json(
    definition: MissionDefinition,
    profile: MissionProfile,
    routes: RoutePlan,
) -> JSONObject:
    """
    Execution-ready view for the Digital Twin (metric coordinate space).

    Georeferencing of these local metric routes onto the live map is a later
    sub-phase (10D.6, definition-driven runtime); here we hand off geometry +
    routes + parameters so nothing must be recomputed downstream.
    """
    exterior = list(profile.field_geometry.boundary.exterior.coords)
    return {
        "operation_type": definition.operation.operation_type,
        "num_drones": profile.num_drones,
        "flight_altitude_m": (
            definition.operation.flight_altitude_m
            if definition.operation.flight_altitude_m is not None
            else profile.flight_altitude_m
        ),
        "field_polygon_m": [[float(x), float(y)] for (x, y) in exterior],
        "routes_m": [
            {
                "drone_id": route.drone_id,
                "waypoints": [
                    {"x": wp.x, "y": wp.y, "sequence": wp.sequence}
                    for wp in route.waypoints
                ],
            }
            for route in routes.routes
        ],
    }
