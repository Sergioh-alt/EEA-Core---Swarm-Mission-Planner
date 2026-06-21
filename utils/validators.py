"""
EEA Swarm Mission Planner - Input Validation
"""

from dataclasses import dataclass


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


def validate_mission_inputs(
    field_size_ha: float,
    crop_type: str,
    num_drones: int,
    battery_capacity_mah: float,
    liquid_capacity_l: float,
    temperature_c: float,
    wind_speed_kmh: float,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if field_size_ha <= 0:
        errors.append("Field size must be positive.")
    elif field_size_ha > 10000:
        warnings.append("Field size exceeds 10,000 ha — verify input.")

    if num_drones < 1:
        errors.append("At least 1 drone is required.")
    elif num_drones > 100:
        warnings.append("Drone count exceeds 100 — verify input.")

    if battery_capacity_mah < 1000:
        errors.append("Battery capacity must be at least 1,000 mAh.")
    elif battery_capacity_mah > 50000:
        warnings.append("Battery capacity exceeds 50,000 mAh — verify input.")

    if liquid_capacity_l <= 0:
        errors.append("Liquid capacity must be positive.")
    elif liquid_capacity_l > 100:
        warnings.append("Liquid capacity exceeds 100 L — verify input.")

    if temperature_c < -40 or temperature_c > 60:
        errors.append("Temperature must be between -40 and 60 C.")

    if wind_speed_kmh < 0:
        errors.append("Wind speed cannot be negative.")
    elif wind_speed_kmh > 100:
        errors.append("Wind speed exceeds 100 km/h — operations not possible.")

    from config.settings import CROP_PROFILES
    valid_crops = list(CROP_PROFILES.keys())
    if crop_type not in valid_crops:
        errors.append(f"Unknown crop type '{crop_type}'. Valid: {valid_crops}")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
