"""
Regression Test Suite — v0.1 Compatibility & End-to-End Validation

Ensures that the v0.1 default scenario produces identical outputs
after all v0.2–v0.4 changes, and that polygon pipelines work correctly.
"""

from core.geometry import FieldGeometry, compute_polygon_orientation
from core.mission_intake import create_mission_profile
from core.environment_analyzer import analyze_environment
from core.swarm_planner import plan_swarm
from core.route_planner import plan_routes
from core.resource_planner import plan_resources
from core.risk_engine import evaluate_risks
from core.decision_engine import generate_recommendation
from shapely.geometry import box


def _run_pipeline(**kwargs):
    """Run the full 7-module pipeline and return all outputs."""
    profile = create_mission_profile(**kwargs)
    assessment = analyze_environment(profile)
    swarm = plan_swarm(profile, assessment)
    routes = plan_routes(swarm, assessment)
    resources = plan_resources(profile, routes)
    risks = evaluate_risks(profile, assessment, resources, routes)
    rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)
    return profile, assessment, swarm, routes, resources, risks, rec


# ===========================================================================
# v0.1 Regression Tests
# ===========================================================================

class TestV01Regression:
    """v0.1 default scenario must produce identical outputs."""

    def test_default_scenario(self):
        _, _, swarm, _, resources, _, rec = _run_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert rec.go_no_go == "GO WITH CAUTION"
        assert rec.confidence_pct == 67.7
        assert resources.mission_duration_formatted == "2h 03m"
        assert len(swarm.sectors) == 4
        assert swarm.balance_score == 1.0
        assert swarm.partition_method == "grid"

    def test_high_wind_no_go(self):
        _, _, _, _, _, _, rec = _run_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=40,
        )
        assert rec.go_no_go == "NO-GO"
        assert not rec.feasible

    def test_rice_crop(self):
        _, _, _, _, _, _, rec = _run_pipeline(
            field_size_ha=50.0, crop_type="rice", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert rec.go_no_go == "GO WITH CAUTION"
        assert rec.confidence_pct == 67.7

    def test_large_field_slider(self):
        _, _, swarm, _, _, _, rec = _run_pipeline(
            field_size_ha=1000.0, crop_type="wheat", num_drones=10,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert swarm.partition_method == "grid"
        assert len(swarm.sectors) == 10

    def test_single_drone(self):
        _, _, swarm, _, _, _, _ = _run_pipeline(
            field_size_ha=10.0, crop_type="wheat", num_drones=1,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert len(swarm.sectors) == 1


# ===========================================================================
# Polygon Pipeline Tests
# ===========================================================================

class TestPolygonPipeline:
    """Polygon fields use strip partition and polygon sweep routing."""

    def test_rectangle_polygon(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        _, _, swarm, routes, _, _, rec = _run_pipeline(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        assert swarm.partition_method == "strip"
        assert len(swarm.sectors) == 4
        assert all(s.boundary is not None for s in swarm.sectors)
        assert len(routes.routes) == 4

    def test_pentagon_polygon(self):
        fg = FieldGeometry.from_points([(0, 0), (600, 0), (800, 300), (400, 600), (0, 400)])
        _, _, swarm, routes, _, _, _ = _run_pipeline(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        assert swarm.partition_method == "strip"
        assert all(s.boundary is not None for s in swarm.sectors)

    def test_hexagon_polygon(self):
        fg = FieldGeometry.from_points([(200, 0), (600, 0), (800, 350), (600, 700), (200, 700), (0, 350)])
        _, _, swarm, _, _, _, _ = _run_pipeline(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        assert swarm.partition_method == "strip"

    def test_small_polygon(self):
        fg = FieldGeometry.from_points([(0, 0), (100, 0), (100, 100), (0, 100)])
        _, _, swarm, _, _, _, _ = _run_pipeline(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=2,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        assert swarm.partition_method == "strip"
        assert len(swarm.sectors) == 2

    def test_polygon_high_wind(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        _, _, _, _, _, _, rec = _run_pipeline(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=40, field_geometry=fg,
        )
        assert rec.go_no_go == "NO-GO"


# ===========================================================================
# Geometry Validation Tests
# ===========================================================================

class TestGeometryValidation:
    """Sector coverage and geometry consistency."""

    def test_sector_area_coverage(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        _, _, swarm, _, _, _, _ = _run_pipeline(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        sector_area_sum = sum(s.area_ha for s in swarm.sectors)
        gap_pct = abs(sector_area_sum - fg.area_ha) / fg.area_ha * 100
        assert gap_pct < 0.5

    def test_from_hectares_consistency(self):
        fg = FieldGeometry.from_hectares(50.0)
        assert fg.is_synthetic is True
        assert abs(fg.area_ha - fg.boundary.area / 10000) < 0.01
        assert abs(fg.perimeter_m - fg.boundary.length) < 0.01

    def test_from_points_consistency(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        assert fg.is_synthetic is False
        assert abs(fg.area_m2 - 400000) < 1
        assert abs(fg.perimeter_m - 2600) < 1

    def test_compute_polygon_orientation_horizontal(self):
        rect = box(0, 0, 800, 500)
        angle = compute_polygon_orientation(rect)
        assert abs(angle) < 0.01

    def test_invalid_polygon_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            FieldGeometry.from_points([(0, 0), (1, 0)])  # Too few points

    def test_collinear_points_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            FieldGeometry.from_points([(0, 0), (1, 0), (2, 0)])  # Zero area
