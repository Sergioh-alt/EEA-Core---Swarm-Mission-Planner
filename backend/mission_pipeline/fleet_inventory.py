"""
Mission Definition Pipeline — fleet inventory (available assets only).

Exposes the catalog of drones, payloads, and products an operator can *select*
when building a Mission Definition. This is inventory, NOT allocation: it never
assigns tasks, balances workload, or schedules resources.

The demonstration inventory is derived from config defaults. A commercial
implementation would source this from a real asset registry behind the same
read-only shape.
"""

from __future__ import annotations

from config.settings import CROP_PROFILES, DroneSpec
from backend.serializers import JSONObject


def _default_drone_models() -> list[JSONObject]:
    spec = DroneSpec()
    return [
        {
            "model": "ORION-Std",
            "vendor": "ORION",
            "battery_capacity_mah": 16000.0,
            "liquid_capacity_l": 10.0,
            "working_width_m": spec.spray_width_m,
            "max_speed_kmh": spec.max_speed_kmh,
        },
        {
            "model": "ORION-Heavy",
            "vendor": "ORION",
            "battery_capacity_mah": 22000.0,
            "liquid_capacity_l": 20.0,
            "working_width_m": 7.0,
            "max_speed_kmh": spec.max_speed_kmh,
        },
        {
            "model": "DJI-Agras-T40",
            "vendor": "DJI",
            "battery_capacity_mah": 30000.0,
            "liquid_capacity_l": 40.0,
            "working_width_m": 9.0,
            "max_speed_kmh": 36.0,
        },
    ]


def _default_products() -> list[JSONObject]:
    return [
        {"product_id": "water", "name": "Water (calibration)", "rate_l_per_ha": 10.0},
        {"product_id": "herbicide_a", "name": "Herbicide A", "rate_l_per_ha": 12.0},
        {"product_id": "fungicide_b", "name": "Fungicide B", "rate_l_per_ha": 8.0},
        {"product_id": "fertilizer_c", "name": "Liquid Fertilizer C", "rate_l_per_ha": 15.0},
    ]


def get_fleet_inventory() -> JSONObject:
    """Return available drone models, product catalog, and supported crops."""
    return {
        "drone_models": _default_drone_models(),
        "products": _default_products(),
        "crop_types": sorted(CROP_PROFILES.keys()),
    }
