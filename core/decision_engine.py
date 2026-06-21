"""
Decision Engine Module

Synthesizes outputs from all modules into a final mission recommendation.
Follows EEA Core's Observe → Analyze → Decide pattern.
"""

from dataclasses import dataclass

from core.mission_intake import MissionProfile
from core.environment_analyzer import EnvironmentAssessment
from core.swarm_planner import SwarmPlan
from core.route_planner import RoutePlan
from core.resource_planner import ResourcePlan
from core.risk_engine import RiskAssessment
from utils.logger import get_logger

logger = get_logger("decision_engine")


@dataclass
class MissionRecommendation:
    feasible: bool
    confidence_pct: float
    coverage_pct: float
    estimated_duration: str
    recommended_drones: int
    operational_notes: list[str]
    optimization_suggestions: list[str]
    go_no_go: str
    summary: str


def generate_recommendation(
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
    swarm: SwarmPlan,
    routes: RoutePlan,
    resources: ResourcePlan,
    risks: RiskAssessment,
) -> MissionRecommendation:
    logger.info("Generating mission recommendation")

    feasible = risks.mission_viable and assessment.flight_conditions != "No-Fly"
    confidence = _calculate_confidence(risks, routes, assessment)
    coverage = routes.efficiency_score * 100
    recommended_drones = _recommend_drone_count(profile, resources, risks)
    notes = _generate_notes(profile, assessment, resources, risks)
    suggestions = _generate_suggestions(profile, assessment, resources, risks, recommended_drones)
    go_no_go = _go_no_go_decision(feasible, confidence, risks)

    summary = _build_summary(
        feasible, confidence, coverage,
        resources.mission_duration_formatted,
        recommended_drones, risks, go_no_go,
    )

    recommendation = MissionRecommendation(
        feasible=feasible,
        confidence_pct=round(confidence, 1),
        coverage_pct=round(coverage, 1),
        estimated_duration=resources.mission_duration_formatted,
        recommended_drones=recommended_drones,
        operational_notes=notes,
        optimization_suggestions=suggestions,
        go_no_go=go_no_go,
        summary=summary,
    )

    logger.info(
        "Recommendation: %s, confidence=%.1f%%, drones=%d, duration=%s",
        go_no_go, confidence, recommended_drones, resources.mission_duration_formatted,
    )
    return recommendation


def _calculate_confidence(
    risks: RiskAssessment,
    routes: RoutePlan,
    assessment: EnvironmentAssessment,
) -> float:
    base = 100.0

    risk_penalty = risks.overall_score * 40
    base -= risk_penalty

    coverage_penalty = max(0, (100 - routes.efficiency_score * 100)) * 0.3
    base -= coverage_penalty

    if assessment.flight_conditions == "No-Fly":
        base = 0
    elif assessment.flight_conditions == "Restricted":
        base -= 20
    elif assessment.flight_conditions == "Caution":
        base -= 10

    return max(0, min(100, base))


def _recommend_drone_count(
    profile: MissionProfile,
    resources: ResourcePlan,
    risks: RiskAssessment,
) -> int:
    recommended = profile.num_drones

    max_time_min = max(
        (dr.total_time_min for dr in resources.drone_resources), default=0,
    )

    if max_time_min > 240:
        scale = max_time_min / 180
        recommended = max(recommended, int(profile.num_drones * scale))
    elif max_time_min > 120:
        recommended = max(recommended, profile.num_drones + 1)

    if risks.overall_score >= 0.8:
        recommended = max(recommended, profile.num_drones + 2)
    elif risks.overall_score > 0.5:
        recommended = max(recommended, profile.num_drones + 1)

    max_cap = max(profile.num_drones * 3, 20)
    return min(recommended, max_cap)


def _generate_notes(
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
    resources: ResourcePlan,
    risks: RiskAssessment,
) -> list[str]:
    notes: list[str] = []

    if assessment.flight_conditions == "No-Fly":
        notes.append("MISSION ABORT — conditions prohibit flight operations.")
        return notes

    if assessment.flight_conditions == "Restricted":
        notes.append("Restricted conditions — reduced operational scope.")

    for risk in risks.risks:
        if risk.level in ("Critical", "High"):
            notes.append(f"{risk.category} risk ({risk.level}): {risk.mitigation}")

    if resources.bottleneck != "None — resources within operational limits":
        notes.append(f"Bottleneck: {resources.bottleneck}")

    if profile.wind_speed_kmh > 20:
        notes.append(
            f"Increase drone count if wind exceeds "
            f"{profile.wind_speed_kmh:.0f} km/h threshold."
        )

    if not notes:
        notes.append("All systems nominal — standard operations apply.")

    return notes


def _generate_suggestions(
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
    resources: ResourcePlan,
    risks: RiskAssessment,
    recommended_drones: int,
) -> list[str]:
    suggestions: list[str] = []

    if recommended_drones > profile.num_drones:
        suggestions.append(
            f"Increase drone count from {profile.num_drones} to "
            f"{recommended_drones} for optimal performance."
        )

    max_battery = max(
        (dr.battery_consumption_pct for dr in resources.drone_resources),
        default=0,
    )
    if max_battery > 80:
        suggestions.append("Consider higher-capacity batteries to reduce swap frequency.")

    if resources.total_refills > profile.num_drones:
        suggestions.append(
            "Pre-position refill stations at field midpoints to reduce transit time."
        )

    if assessment.recommended_speed_kmh < 20:
        suggestions.append(
            "Weather is limiting speed — schedule operation for calmer conditions."
        )

    if profile.field_size_ha > 100 and profile.num_drones < 4:
        suggestions.append(
            "Large field with few drones — consider swarm expansion for efficiency."
        )

    return suggestions


def _go_no_go_decision(
    feasible: bool,
    confidence: float,
    risks: RiskAssessment,
) -> str:
    if not feasible:
        return "NO-GO"
    if confidence >= 80 and risks.overall_score < 0.3:
        return "GO"
    if confidence >= 60:
        return "GO WITH CAUTION"
    return "CONDITIONAL — Review risks before proceeding"


def _build_summary(
    feasible: bool,
    confidence: float,
    coverage: float,
    duration: str,
    drones: int,
    risks: RiskAssessment,
    go_no_go: str,
) -> str:
    lines = [
        f"Mission Feasible: {'YES' if feasible else 'NO'}",
        f"Decision: {go_no_go}",
        f"Confidence: {confidence:.0f}%",
        f"Coverage: {coverage:.0f}%",
        f"Estimated Duration: {duration}",
        f"Recommended Drones: {drones}",
        f"Overall Risk: {risks.overall_risk} ({risks.overall_score:.2f})",
    ]
    if risks.critical_risks:
        lines.append(f"Critical Risks: {', '.join(risks.critical_risks)}")
    return "\n".join(lines)
