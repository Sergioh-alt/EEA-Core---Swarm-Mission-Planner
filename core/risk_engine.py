"""
Risk Engine Module

Evaluates weather, battery, coverage, and operational risks.
Returns structured risk levels following EEA Core's Guardian principles.
"""

from dataclasses import dataclass

from config.settings import weather_thresholds, risk_thresholds, drone_spec
from core.mission_intake import MissionProfile
from core.environment_analyzer import EnvironmentAssessment
from core.resource_planner import ResourcePlan
from core.route_planner import RoutePlan
from utils.logger import get_logger

logger = get_logger("risk_engine")


@dataclass
class RiskItem:
    category: str
    level: str
    score: float
    description: str
    mitigation: str


@dataclass
class RiskAssessment:
    risks: list[RiskItem]
    overall_risk: str
    overall_score: float
    mission_viable: bool
    critical_risks: list[str]


def evaluate_risks(
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
    resource_plan: ResourcePlan,
    route_plan: RoutePlan,
) -> RiskAssessment:
    logger.info("Evaluating mission risks")

    risks: list[RiskItem] = []
    risks.append(_weather_risk(profile, assessment))
    risks.append(_battery_risk(profile, resource_plan))
    risks.append(_coverage_risk(route_plan, resource_plan))
    risks.append(_operational_risk(profile, assessment, resource_plan))

    scores = [r.score for r in risks]
    overall_score = max(scores)
    overall_risk = _score_to_level(overall_score)
    critical_risks = [r.category for r in risks if r.level == "Critical"]
    mission_viable = overall_score < 0.9

    result = RiskAssessment(
        risks=risks,
        overall_risk=overall_risk,
        overall_score=round(overall_score, 2),
        mission_viable=mission_viable,
        critical_risks=critical_risks,
    )

    logger.info(
        "Risk assessment: overall=%s (%.2f), viable=%s, critical=%s",
        overall_risk, overall_score, mission_viable, critical_risks,
    )
    return result


def _weather_risk(
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
) -> RiskItem:
    score = 0.0
    issues: list[str] = []
    mitigations: list[str] = []

    wind = profile.wind_speed_kmh
    if wind > weather_thresholds.max_wind_kmh:
        score = max(score, 1.0)
        issues.append(f"Wind {wind:.0f} km/h exceeds max {weather_thresholds.max_wind_kmh:.0f} km/h")
        mitigations.append("Postpone mission until wind subsides")
    elif wind > weather_thresholds.warning_wind_kmh:
        score = max(score, 0.6)
        issues.append(f"Wind {wind:.0f} km/h — spray drift risk")
        mitigations.append("Reduce flight altitude and speed")

    temp = profile.temperature_c
    if temp > weather_thresholds.max_temp_c or temp < weather_thresholds.min_temp_c:
        score = max(score, 0.9)
        issues.append(f"Temperature {temp:.0f} C outside operational range")
        mitigations.append("Schedule mission for different time window")
    elif temp > weather_thresholds.warning_temp_high_c:
        score = max(score, 0.5)
        issues.append(f"High temperature {temp:.0f} C — reduced electronics lifespan")
        mitigations.append("Schedule early morning operations")
    elif temp < weather_thresholds.warning_temp_low_c:
        score = max(score, 0.5)
        issues.append(f"Low temperature {temp:.0f} C — reduced battery performance")
        mitigations.append("Pre-warm batteries before flight")

    if not issues:
        issues.append("Weather conditions within safe parameters")
        mitigations.append("No action required")

    return RiskItem(
        category="Weather",
        level=_score_to_level(score),
        score=round(score, 2),
        description="; ".join(issues),
        mitigation="; ".join(mitigations),
    )


def _battery_risk(
    profile: MissionProfile,
    resource_plan: ResourcePlan,
) -> RiskItem:
    max_consumption = max(
        (dr.battery_consumption_pct for dr in resource_plan.drone_resources),
        default=0,
    )

    if max_consumption > 100:
        score = 0.8
        desc = f"Battery consumption {max_consumption:.0f}% — requires battery swap"
        mitigation = "Prepare spare batteries; consider adding drones to reduce per-drone load"
    elif max_consumption > 85 - drone_spec.min_battery_reserve_pct:
        score = 0.6
        desc = f"Battery consumption {max_consumption:.0f}% — near capacity"
        mitigation = "Monitor battery levels; have spares on standby"
    elif max_consumption > 60:
        score = 0.3
        desc = f"Battery consumption {max_consumption:.0f}% — moderate usage"
        mitigation = "Standard monitoring sufficient"
    else:
        score = 0.1
        desc = f"Battery consumption {max_consumption:.0f}% — comfortable margin"
        mitigation = "No action required"

    return RiskItem(
        category="Battery",
        level=_score_to_level(score),
        score=round(score, 2),
        description=desc,
        mitigation=mitigation,
    )


def _coverage_risk(
    route_plan: RoutePlan,
    resource_plan: ResourcePlan,
) -> RiskItem:
    efficiency = route_plan.efficiency_score * 100

    if efficiency >= 98:
        score = 0.05
        desc = f"Coverage {efficiency:.0f}% — full field coverage"
        mitigation = "No action required"
    elif efficiency >= risk_thresholds.coverage_acceptable_pct:
        score = 0.2
        desc = f"Coverage {efficiency:.0f}% — acceptable with minor gaps"
        mitigation = "Review boundary areas for potential missed strips"
    elif efficiency >= 85:
        score = 0.5
        desc = f"Coverage {efficiency:.0f}% — gaps in coverage"
        mitigation = "Increase overlap or add additional passes"
    else:
        score = 0.8
        desc = f"Coverage {efficiency:.0f}% — significant gaps"
        mitigation = "Reconfigure spray width or add drones"

    return RiskItem(
        category="Coverage",
        level=_score_to_level(score),
        score=round(score, 2),
        description=desc,
        mitigation=mitigation,
    )


def _operational_risk(
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
    resource_plan: ResourcePlan,
) -> RiskItem:
    score = 0.0
    issues: list[str] = []
    mitigations: list[str] = []

    duration_h = resource_plan.mission_duration_min / 60
    if duration_h > risk_thresholds.max_mission_duration_h:
        score = max(score, 0.7)
        issues.append(f"Mission duration {duration_h:.1f}h exceeds {risk_thresholds.max_mission_duration_h:.0f}h limit")
        mitigations.append("Split into multiple mission windows or add drones")
    elif duration_h > risk_thresholds.max_mission_duration_h * 0.75:
        score = max(score, 0.4)
        issues.append(f"Mission duration {duration_h:.1f}h — extended operation")
        mitigations.append("Ensure operator availability for full duration")

    if resource_plan.total_refills > profile.num_drones * 2:
        score = max(score, 0.5)
        issues.append(f"{resource_plan.total_refills} total refills — logistics intensive")
        mitigations.append("Pre-stage refill stations; consider larger tanks")

    if profile.num_drones < 2 and profile.field_size_ha > 20:
        score = max(score, 0.4)
        issues.append("Single drone for large area — no redundancy")
        mitigations.append("Add backup drone for operational safety")

    if assessment.flight_conditions == "No-Fly":
        score = 1.0
        issues.append("Flight conditions prohibit operations")
        mitigations.append("Mission cannot proceed — postpone")
    elif assessment.flight_conditions == "Restricted":
        score = max(score, 0.7)
        issues.append("Restricted flight conditions — limited operations")
        mitigations.append("Reduce operational scope or wait for conditions to improve")

    if not issues:
        issues.append("Operational parameters within normal limits")
        mitigations.append("Standard procedures apply")

    return RiskItem(
        category="Operational",
        level=_score_to_level(score),
        score=round(score, 2),
        description="; ".join(issues),
        mitigation="; ".join(mitigations),
    )


def _score_to_level(score: float) -> str:
    if score >= 0.8:
        return "Critical"
    if score >= 0.5:
        return "High"
    if score >= 0.3:
        return "Medium"
    if score >= 0.1:
        return "Low"
    return "Minimal"
