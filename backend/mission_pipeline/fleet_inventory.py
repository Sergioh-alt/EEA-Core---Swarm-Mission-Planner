"""
Mission Definition Pipeline — fleet inventory (available assets only).

Exposes the catalog of drones, payloads, and products an operator can *select*
when building a Mission Definition. This is inventory, NOT allocation: it never
assigns tasks, balances workload, or schedules resources.

Each drone model advertises read-only catalog specifications (status, payload,
estimated flight time, tanks, supported operations, sensors, equipment, camera
packages, sprayer configurations). The Fleet Configuration workspace (10D.5)
lets the operator select these; feasibility remains the Planning Core's job.

The demonstration inventory is derived from config defaults. A commercial
implementation would source this from a real asset registry behind the same
read-only shape.
"""

from __future__ import annotations

from config.settings import CROP_PROFILES, DroneSpec
from backend.serializers import JSONObject


def _tank(tank_id: str, label: str, capacity_l: float) -> JSONObject:
    return {"tank_id": tank_id, "label": label, "capacity_l": capacity_l}


def _default_drone_models() -> list[JSONObject]:
    spec = DroneSpec()
    return [
        {
            "model": "ORION-Std",
            "vendor": "ORION",
            "status": "available",
            "battery_capacity_mah": 16000.0,
            "liquid_capacity_l": 10.0,
            "working_width_m": spec.spray_width_m,
            "max_speed_kmh": spec.max_speed_kmh,
            "payload_capacity_kg": 10.0,
            "estimated_flight_time_min": 18.0,
            "tanks": [_tank("A", "Tank A", 10.0)],
            "supported_operations": [
                "spray",
                "fertilization",
                "inspection",
                "mapping",
            ],
            "sensors": ["RTK-GPS", "Obstacle Radar", "Flow Meter"],
            "equipment": ["Standard Sprayer"],
            "camera_packages": ["None", "RGB"],
            "sprayer_configs": ["Standard 4-nozzle", "Fine Mist"],
        },
        {
            "model": "ORION-Heavy",
            "vendor": "ORION",
            "status": "available",
            "battery_capacity_mah": 22000.0,
            "liquid_capacity_l": 20.0,
            "working_width_m": 7.0,
            "max_speed_kmh": spec.max_speed_kmh,
            "payload_capacity_kg": 20.0,
            "estimated_flight_time_min": 22.0,
            "tanks": [_tank("A", "Tank A", 10.0), _tank("B", "Tank B", 10.0)],
            "supported_operations": [
                "spray",
                "fertilization",
                "seeding",
                "inspection",
                "mapping",
            ],
            "sensors": [
                "RTK-GPS",
                "Obstacle Radar",
                "Flow Meter",
                "Terrain LiDAR",
            ],
            "equipment": ["Heavy Sprayer", "Granular Spreader"],
            "camera_packages": ["None", "RGB", "Multispectral"],
            "sprayer_configs": [
                "Standard 4-nozzle",
                "Wide 8-nozzle",
                "Fine Mist",
            ],
        },
        {
            "model": "DJI-Agras-T40",
            "vendor": "DJI",
            "status": "available",
            "battery_capacity_mah": 30000.0,
            "liquid_capacity_l": 40.0,
            "working_width_m": 9.0,
            "max_speed_kmh": 36.0,
            "payload_capacity_kg": 40.0,
            "estimated_flight_time_min": 18.0,
            "tanks": [_tank("A", "Tank A", 20.0), _tank("B", "Tank B", 20.0)],
            "supported_operations": [
                "spray",
                "fertilization",
                "seeding",
                "mapping",
            ],
            "sensors": ["RTK-GPS", "Omnidirectional Radar", "Dual FPV"],
            "equipment": ["Spray System", "Spreading System 2.0"],
            "camera_packages": ["FPV", "RGB"],
            "sprayer_configs": ["Dual atomizing", "Standard"],
        },
        {
            "model": "XAG-P100",
            "vendor": "XAG",
            "status": "available",
            "battery_capacity_mah": 30000.0,
            "liquid_capacity_l": 50.0,
            "working_width_m": 7.0,
            "max_speed_kmh": 36.0,
            "payload_capacity_kg": 50.0,
            "estimated_flight_time_min": 15.0,
            "tanks": [_tank("A", "Tank A", 25.0), _tank("B", "Tank B", 25.0)],
            "supported_operations": [
                "spray",
                "fertilization",
                "seeding",
                "mapping",
            ],
            "sensors": ["RTK-GPS", "Digital Radar", "Binocular Vision"],
            "equipment": ["RevoSpray", "RevoCast (granular)"],
            "camera_packages": ["FPV", "RGB"],
            "sprayer_configs": ["Centrifugal dual", "Standard"],
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
