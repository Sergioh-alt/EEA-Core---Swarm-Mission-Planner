"""
EEA Swarm Mission Planner - Configuration Settings

Centralizes all configuration, environment variables, and constants.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    name: str = os.getenv("APP_NAME", "EEA Swarm Mission Planner")
    env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    version: str = "0.5.0"


@dataclass
class DroneSpec:
    """Default drone specifications."""
    min_speed_kmh: float = 15.0
    max_speed_kmh: float = 40.0
    spray_width_m: float = 5.0
    turn_time_s: float = 8.0
    takeoff_landing_s: float = 30.0
    battery_voltage: float = 22.2
    power_consumption_wh_per_km: float = 15.0
    liquid_flow_rate_l_per_ha: float = 10.0
    min_battery_reserve_pct: float = 15.0


@dataclass
class WeatherThresholds:
    """Operational weather limits."""
    max_wind_kmh: float = 35.0
    warning_wind_kmh: float = 20.0
    max_temp_c: float = 45.0
    min_temp_c: float = 0.0
    warning_temp_high_c: float = 38.0
    warning_temp_low_c: float = 5.0


@dataclass
class RiskThresholds:
    """Risk assessment thresholds."""
    battery_critical_pct: float = 20.0
    battery_warning_pct: float = 35.0
    coverage_acceptable_pct: float = 95.0
    max_mission_duration_h: float = 8.0


CROP_PROFILES = {
    "wheat": {
        "spray_rate_l_per_ha": 8.0,
        "flight_altitude_m": 3.0,
        "complexity": "low",
        "notes": "Uniform terrain, standard spray pattern",
    },
    "corn": {
        "spray_rate_l_per_ha": 12.0,
        "flight_altitude_m": 5.0,
        "complexity": "medium",
        "notes": "Tall crop, requires higher altitude",
    },
    "rice": {
        "spray_rate_l_per_ha": 15.0,
        "flight_altitude_m": 3.0,
        "complexity": "high",
        "notes": "Paddy fields, water interference, higher liquid usage",
    },
    "soybean": {
        "spray_rate_l_per_ha": 10.0,
        "flight_altitude_m": 3.0,
        "complexity": "low",
        "notes": "Uniform crop, standard operations",
    },
    "vineyard": {
        "spray_rate_l_per_ha": 14.0,
        "flight_altitude_m": 4.0,
        "complexity": "high",
        "notes": "Row structure, precision navigation required",
    },
    "cotton": {
        "spray_rate_l_per_ha": 10.0,
        "flight_altitude_m": 4.0,
        "complexity": "medium",
        "notes": "Medium density crop, standard altitude",
    },
    "sugarcane": {
        "spray_rate_l_per_ha": 12.0,
        "flight_altitude_m": 6.0,
        "complexity": "high",
        "notes": "Very tall crop, high altitude required",
    },
    "generic": {
        "spray_rate_l_per_ha": 10.0,
        "flight_altitude_m": 4.0,
        "complexity": "medium",
        "notes": "Default profile for unspecified crops",
    },
}

COMPLEXITY_MULTIPLIER = {
    "low": 1.0,
    "medium": 1.25,
    "high": 1.5,
}

# Operational time constants (shared across modules)
REFILL_TIME_MIN: float = 5.0
BATTERY_SWAP_TIME_MIN: float = 3.0

app_config = AppConfig()
drone_spec = DroneSpec()
weather_thresholds = WeatherThresholds()
risk_thresholds = RiskThresholds()
