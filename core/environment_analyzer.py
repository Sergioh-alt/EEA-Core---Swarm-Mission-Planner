"""
Environment Analyzer Module

Evaluates field and weather conditions to produce an operational
assessment used by downstream planners and the risk engine.
"""

from dataclasses import dataclass

from config.settings import weather_thresholds
from core.mission_intake import MissionProfile
from utils.logger import get_logger

logger = get_logger("environment_analyzer")


@dataclass
class EnvironmentAssessment:
    area_category: str
    operational_complexity: str
    weather_status: str
    weather_details: str
    wind_assessment: str
    temperature_assessment: str
    flight_conditions: str
    recommended_speed_kmh: float
    effective_spray_width_m: float


def analyze_environment(profile: MissionProfile) -> EnvironmentAssessment:
    logger.info("Analyzing environment for %.1f ha mission", profile.field_size_ha)

    area_category = _categorize_area(profile.field_size_ha)
    op_complexity = _assess_operational_complexity(profile)
    wind_assessment, wind_detail = _assess_wind(profile.wind_speed_kmh)
    temp_assessment, temp_detail = _assess_temperature(profile.temperature_c)
    weather_status = _overall_weather_status(wind_assessment, temp_assessment)
    flight_conditions = _determine_flight_conditions(weather_status, op_complexity)
    recommended_speed = _recommend_speed(profile)
    effective_spray_width = _effective_spray_width(profile)

    weather_details = f"Wind: {wind_detail}. Temperature: {temp_detail}."

    assessment = EnvironmentAssessment(
        area_category=area_category,
        operational_complexity=op_complexity,
        weather_status=weather_status,
        weather_details=weather_details,
        wind_assessment=wind_assessment,
        temperature_assessment=temp_assessment,
        flight_conditions=flight_conditions,
        recommended_speed_kmh=recommended_speed,
        effective_spray_width_m=effective_spray_width,
    )

    logger.info(
        "Environment: area=%s, complexity=%s, weather=%s, conditions=%s",
        area_category, op_complexity, weather_status, flight_conditions,
    )
    return assessment


def _categorize_area(ha: float) -> str:
    if ha <= 5:
        return "Small (< 5 ha)"
    if ha <= 50:
        return "Medium (5-50 ha)"
    if ha <= 200:
        return "Large (50-200 ha)"
    return "Industrial (> 200 ha)"


def _assess_operational_complexity(profile: MissionProfile) -> str:
    score = 0
    if profile.field_size_ha > 100:
        score += 2
    elif profile.field_size_ha > 30:
        score += 1

    complexity_scores = {"low": 0, "medium": 1, "high": 2}
    score += complexity_scores.get(profile.crop_complexity, 1)

    if profile.wind_speed_kmh > weather_thresholds.warning_wind_kmh:
        score += 1
    if profile.wind_speed_kmh > weather_thresholds.max_wind_kmh:
        score += 2

    if score <= 1:
        return "Low"
    if score <= 3:
        return "Moderate"
    if score <= 5:
        return "High"
    return "Critical"


def _assess_wind(wind_kmh: float) -> tuple[str, str]:
    wt = weather_thresholds
    if wind_kmh <= 10:
        return "Optimal", f"{wind_kmh:.0f} km/h — calm conditions"
    if wind_kmh <= wt.warning_wind_kmh:
        return "Acceptable", f"{wind_kmh:.0f} km/h — light wind"
    if wind_kmh <= wt.max_wind_kmh:
        return "Warning", f"{wind_kmh:.0f} km/h — moderate wind, spray drift risk"
    return "Critical", f"{wind_kmh:.0f} km/h — exceeds safe operating limit"


def _assess_temperature(temp_c: float) -> tuple[str, str]:
    wt = weather_thresholds
    if wt.warning_temp_low_c <= temp_c <= wt.warning_temp_high_c:
        return "Optimal", f"{temp_c:.0f} C — within operational range"
    if wt.min_temp_c <= temp_c < wt.warning_temp_low_c:
        return "Warning", f"{temp_c:.0f} C — cold conditions, battery efficiency reduced"
    if wt.warning_temp_high_c < temp_c <= wt.max_temp_c:
        return "Warning", f"{temp_c:.0f} C — high temperature, monitor electronics"
    return "Critical", f"{temp_c:.0f} C — outside safe operating range"


def _overall_weather_status(wind: str, temp: str) -> str:
    levels = {"Optimal": 0, "Acceptable": 1, "Warning": 2, "Critical": 3}
    worst = max(levels.get(wind, 0), levels.get(temp, 0))
    return {0: "Optimal", 1: "Acceptable", 2: "Warning", 3: "Critical"}[worst]


def _determine_flight_conditions(weather: str, complexity: str) -> str:
    if weather == "Critical":
        return "No-Fly"
    if weather == "Warning" and complexity in ("High", "Critical"):
        return "Restricted"
    if weather == "Warning" or complexity in ("High", "Critical"):
        return "Caution"
    return "Clear"


def _recommend_speed(profile: MissionProfile) -> float:
    base_speed = 25.0
    if profile.wind_speed_kmh > weather_thresholds.warning_wind_kmh:
        base_speed *= 0.75
    if profile.crop_complexity == "high":
        base_speed *= 0.85
    return round(max(15.0, min(base_speed, 40.0)), 1)


def _effective_spray_width(profile: MissionProfile) -> float:
    from config.settings import drone_spec
    width = drone_spec.spray_width_m
    if profile.wind_speed_kmh > weather_thresholds.warning_wind_kmh:
        drift_factor = 1 - (profile.wind_speed_kmh - weather_thresholds.warning_wind_kmh) / 100
        width *= max(drift_factor, 0.6)
    return round(width, 2)
