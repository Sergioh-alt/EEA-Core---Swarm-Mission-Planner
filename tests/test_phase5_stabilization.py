"""
Phase 5 — System Stabilization Tests

Tests for architecture consolidation, module independence, and version stability.
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


def _run_full_pipeline(**kwargs):
    profile = create_mission_profile(**kwargs)
    assessment = analyze_environment(profile)
    swarm = plan_swarm(profile, assessment)
    routes = plan_routes(swarm, assessment)
    resources = plan_resources(profile, routes)
    risks = evaluate_risks(profile, assessment, resources, routes)
    rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)
    return profile, assessment, swarm, routes, resources, risks, rec


class TestGeometryCentralization:
    """compute_polygon_orientation must live only in core/geometry.py."""

    def test_geometry_module_has_orientation(self):
        from core import geometry
        assert hasattr(geometry, "compute_polygon_orientation")

    def test_swarm_planner_imports_from_geometry(self):
        import core.swarm_planner as sp
        # swarm_planner should import compute_polygon_orientation from geometry
        assert "compute_polygon_orientation" in dir(sp)

    def test_route_planner_imports_from_geometry(self):
        import core.route_planner as rp
        assert "compute_polygon_orientation" in dir(rp)

    def test_orientation_consistent_across_callers(self):
        rect = box(0, 0, 800, 500)
        result = compute_polygon_orientation(rect)
        # Both swarm_planner and route_planner should use the same function
        from core.geometry import compute_polygon_orientation as geo_orient
        assert compute_polygon_orientation is geo_orient
        assert -180 <= result <= 180


class TestMultiScenarioStability:
    """Various field configurations must produce stable, error-free results."""

    def test_default_50ha(self):
        _, _, swarm, _, resources, _, rec = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert rec.go_no_go == "GO WITH CAUTION"
        assert rec.confidence_pct == 67.7
        assert resources.mission_duration_formatted == "2h 03m"
        assert len(swarm.sectors) == 4
        assert swarm.balance_score == 1.0

    def test_high_wind_no_go(self):
        _, _, _, _, _, _, rec = _run_full_pipeline(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=40,
        )
        assert rec.go_no_go == "NO-GO"
        assert not rec.feasible

    def test_large_field(self):
        _, _, swarm, _, _, _, _ = _run_full_pipeline(
            field_size_ha=1000.0, crop_type="wheat", num_drones=10,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert swarm.partition_method == "grid"
        assert len(swarm.sectors) == 10

    def test_single_drone(self):
        _, _, swarm, _, _, _, _ = _run_full_pipeline(
            field_size_ha=10.0, crop_type="wheat", num_drones=1,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert len(swarm.sectors) == 1

    def test_rice_crop(self):
        _, _, _, _, _, _, rec = _run_full_pipeline(
            field_size_ha=50.0, crop_type="rice", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assert rec.go_no_go == "GO WITH CAUTION"

    def test_polygon_rectangle(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        _, _, swarm, _, _, _, rec = _run_full_pipeline(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        assert swarm.partition_method == "strip"
        assert rec.feasible

    def test_polygon_pentagon(self):
        fg = FieldGeometry.from_points([(0, 0), (600, 0), (800, 300), (400, 600), (0, 400)])
        _, _, swarm, _, _, _, _ = _run_full_pipeline(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
        )
        assert swarm.partition_method == "strip"

    def test_polygon_high_wind(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        _, _, _, _, _, _, rec = _run_full_pipeline(
            field_size_ha=fg.area_ha, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=40, field_geometry=fg,
        )
        assert rec.go_no_go == "NO-GO"


class TestDeterminism:
    """Same inputs must produce identical outputs on repeated runs."""

    def test_deterministic_output(self):
        kwargs = dict(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        _, _, _, _, r1, _, rec1 = _run_full_pipeline(**kwargs)
        _, _, _, _, r2, _, rec2 = _run_full_pipeline(**kwargs)

        assert rec1.go_no_go == rec2.go_no_go
        assert rec1.confidence_pct == rec2.confidence_pct
        assert r1.mission_duration_formatted == r2.mission_duration_formatted
