"""
Phase 4 — UI Geometry Input Tests

Tests for polygon presets, field mode selection, and UI helper functions.
Note: Streamlit rendering cannot be tested in pytest; these tests validate
the data layer that feeds the UI.
"""

from core.geometry import FieldGeometry
from core.mission_intake import create_mission_profile
from core.environment_analyzer import analyze_environment
from core.swarm_planner import plan_swarm
from core.route_planner import plan_routes
from core.resource_planner import plan_resources
from core.risk_engine import evaluate_risks
from core.decision_engine import generate_recommendation


PRESETS = {
    "Rectangle 800x500": [(0, 0), (800, 0), (800, 500), (0, 500)],
    "Pentagon": [(0, 0), (600, 0), (800, 300), (400, 600), (0, 400)],
    "Hexagon": [(200, 0), (600, 0), (800, 350), (600, 700), (200, 700), (0, 350)],
    "L-shape": [(0, 0), (600, 0), (600, 300), (300, 300), (300, 600), (0, 600)],
}


class TestPresetShapes:
    """All preset shapes must produce valid FieldGeometry."""

    def test_rectangle_preset(self):
        fg = FieldGeometry.from_points(PRESETS["Rectangle 800x500"])
        assert fg.area_ha > 0
        assert fg.perimeter_m > 0
        assert not fg.is_synthetic

    def test_pentagon_preset(self):
        fg = FieldGeometry.from_points(PRESETS["Pentagon"])
        assert fg.area_ha > 0
        assert fg.perimeter_m > 0

    def test_hexagon_preset(self):
        fg = FieldGeometry.from_points(PRESETS["Hexagon"])
        assert fg.area_ha > 0
        assert fg.perimeter_m > 0

    def test_l_shape_preset(self):
        fg = FieldGeometry.from_points(PRESETS["L-shape"])
        assert fg.area_ha > 0
        assert fg.perimeter_m > 0


class TestSliderModeBackwardCompat:
    """Slider mode (no field_geometry) must produce v0.1-identical results."""

    def test_slider_default_scenario(self):
        profile = create_mission_profile(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assessment = analyze_environment(profile)
        swarm = plan_swarm(profile, assessment)
        routes = plan_routes(swarm, assessment)
        resources = plan_resources(profile, routes)
        risks = evaluate_risks(profile, assessment, resources, routes)
        rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)

        assert rec.go_no_go == "GO WITH CAUTION"
        assert rec.confidence_pct == 67.7
        assert swarm.partition_method == "grid"
        assert len(swarm.sectors) == 4
        assert resources.mission_duration_formatted == "2h 03m"


class TestPolygonModePipeline:
    """Polygon mode (with field_geometry) must produce valid pipeline output."""

    def test_rectangle_full_pipeline(self):
        fg = FieldGeometry.from_points(PRESETS["Rectangle 800x500"])
        profile = create_mission_profile(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        assessment = analyze_environment(profile)
        swarm = plan_swarm(profile, assessment)
        routes = plan_routes(swarm, assessment)
        resources = plan_resources(profile, routes)
        risks = evaluate_risks(profile, assessment, resources, routes)
        rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)

        assert swarm.partition_method == "strip"
        assert rec.go_no_go in ("GO", "GO WITH CAUTION")
        assert rec.feasible

    def test_pentagon_full_pipeline(self):
        fg = FieldGeometry.from_points(PRESETS["Pentagon"])
        profile = create_mission_profile(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        assessment = analyze_environment(profile)
        swarm = plan_swarm(profile, assessment)
        routes = plan_routes(swarm, assessment)
        resources = plan_resources(profile, routes)
        risks = evaluate_risks(profile, assessment, resources, routes)
        rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)

        assert swarm.partition_method == "strip"
        assert rec.feasible

    def test_hexagon_full_pipeline(self):
        fg = FieldGeometry.from_points(PRESETS["Hexagon"])
        profile = create_mission_profile(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        assessment = analyze_environment(profile)
        swarm = plan_swarm(profile, assessment)

        assert swarm.partition_method == "strip"

    def test_small_polygon_pipeline(self):
        fg = FieldGeometry.from_points([(0, 0), (100, 0), (100, 100), (0, 100)])
        profile = create_mission_profile(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=2,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        assessment = analyze_environment(profile)
        swarm = plan_swarm(profile, assessment)

        assert swarm.partition_method == "strip"
        assert len(swarm.sectors) == 2
