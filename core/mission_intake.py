"""
Mission Intake Module

Receives, validates, and structures raw mission parameters into
a canonical MissionProfile consumed by downstream modules.
"""

from dataclasses import dataclass
from typing import Optional

from config.settings import CROP_PROFILES, COMPLEXITY_MULTIPLIER
from core.geometry import FieldGeometry
from utils.logger import get_logger
from utils.validators import validate_mission_inputs, ValidationResult

logger = get_logger("mission_intake")


@dataclass
class MissionProfile:
    field_size_ha: float
    crop_type: str
    num_drones: int
    battery_capacity_mah: float
    liquid_capacity_l: float
    temperature_c: float
    wind_speed_kmh: float
    spray_rate_l_per_ha: float
    flight_altitude_m: float
    crop_complexity: str
    complexity_multiplier: float
    crop_notes: str
    field_size_m2: float
    field_geometry: FieldGeometry
    validation: ValidationResult


def create_mission_profile(
    field_size_ha: float,
    crop_type: str,
    num_drones: int,
    battery_capacity_mah: float,
    liquid_capacity_l: float,
    temperature_c: float,
    wind_speed_kmh: float,
    field_geometry: Optional[FieldGeometry] = None,
) -> MissionProfile:
    logger.info(
        "Creating mission profile: %.1f ha, %s, %d drones",
        field_size_ha, crop_type, num_drones,
    )

    validation = validate_mission_inputs(
        field_size_ha, crop_type, num_drones,
        battery_capacity_mah, liquid_capacity_l,
        temperature_c, wind_speed_kmh,
    )

    if not validation.valid:
        logger.error("Validation failed: %s", validation.errors)

    for w in validation.warnings:
        logger.warning(w)

    crop = CROP_PROFILES.get(crop_type, CROP_PROFILES["generic"])
    complexity = crop["complexity"]

    if field_geometry is None:
        field_geometry = FieldGeometry.from_hectares(field_size_ha)

    profile = MissionProfile(
        field_size_ha=field_size_ha,
        crop_type=crop_type,
        num_drones=num_drones,
        battery_capacity_mah=battery_capacity_mah,
        liquid_capacity_l=liquid_capacity_l,
        temperature_c=temperature_c,
        wind_speed_kmh=wind_speed_kmh,
        spray_rate_l_per_ha=crop["spray_rate_l_per_ha"],
        flight_altitude_m=crop["flight_altitude_m"],
        crop_complexity=complexity,
        complexity_multiplier=COMPLEXITY_MULTIPLIER[complexity],
        crop_notes=crop["notes"],
        field_size_m2=field_size_ha * 10000,
        field_geometry=field_geometry,
        validation=validation,
    )

    logger.info("Mission profile created — complexity=%s", complexity)
    return profile
