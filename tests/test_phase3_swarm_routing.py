"""
Phase 3 — Polygon Swarm & Route Intelligence Tests

Tests for strip-based partitioning and polygon sweep routing.
"""

from core.geometry import FieldGeometry
from core.mission_intake import create_mission_profile
from core.environment_analyzer import analyze_environment
from core.swarm_planner import plan_swarm
from core.route_planner import plan_routes


def _run_polygon_pipeline(points, num_drones=4, **kwargs):
    """Run pipeline with a polygon field."""
    fg = FieldGeometry.from_points(points)
    defaults = dict(
        field_size_ha=fg.area_ha, crop_type="wheat", num_drones=num_drones,
        battery_capacity_mah=5000, liquid_capacity_l=10.0,
        temperature_c=25, wind_speed_kmh=10, field_geometry=fg,
    )
    defaults.update(kwargs)
    profile = create_mission_profile(**defaults)
    assessment = analyze_environment(profile)
    swarm = plan_swarm(profile, assessment)
    routes = plan_routes(swarm, assessment)
    return fg, profile, swarm, routes


class TestStripPartitioning:
    """Strip-based polygon partitioning tests."""

    def test_strip_method_for_polygon(self):
        _, _, swarm, _ = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)]
        )
        assert swarm.partition_method == "strip"

    def test_grid_method_for_hectares(self):
        profile = create_mission_profile(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assessment = analyze_environment(profile)
        swarm = plan_swarm(profile, assessment)
        assert swarm.partition_method == "grid"

    def test_correct_sector_count(self):
        _, _, swarm, _ = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)], num_drones=4
        )
        assert len(swarm.sectors) == 4

    def test_sectors_have_boundaries(self):
        _, _, swarm, _ = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)]
        )
        for sector in swarm.sectors:
            assert sector.boundary is not None

    def test_sector_area_coverage(self):
        fg, _, swarm, _ = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)]
        )
        sector_area_sum = sum(s.area_ha for s in swarm.sectors)
        gap_pct = abs(sector_area_sum - fg.area_ha) / fg.area_ha * 100
        assert gap_pct < 0.5

    def test_pentagon_partitioning(self):
        _, _, swarm, _ = _run_polygon_pipeline(
            [(0, 0), (600, 0), (800, 300), (400, 600), (0, 400)]
        )
        assert swarm.partition_method == "strip"
        assert all(s.boundary is not None for s in swarm.sectors)

    def test_triangle_partitioning(self):
        _, _, swarm, _ = _run_polygon_pipeline(
            [(0, 0), (800, 0), (400, 600)], num_drones=3
        )
        assert swarm.partition_method == "strip"
        assert len(swarm.sectors) == 3

    def test_hexagon_partitioning(self):
        _, _, swarm, _ = _run_polygon_pipeline(
            [(200, 0), (600, 0), (800, 350), (600, 700), (200, 700), (0, 350)]
        )
        assert swarm.partition_method == "strip"

    def test_single_drone_polygon(self):
        _, _, swarm, _ = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)], num_drones=1
        )
        assert len(swarm.sectors) == 1
        assert swarm.partition_method == "strip"

    def test_balance_score_rectangle(self):
        _, _, swarm, _ = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)]
        )
        assert swarm.balance_score > 0.9


class TestPolygonRouting:
    """Polygon sweep-line boustrophedon routing tests."""

    def test_routes_generated_for_all_sectors(self):
        _, _, swarm, routes = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)]
        )
        assert len(routes.routes) == len(swarm.sectors)

    def test_each_route_has_waypoints(self):
        _, _, _, routes = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)]
        )
        for route in routes.routes:
            assert len(route.waypoints) > 0
            assert route.num_passes > 0

    def test_route_distance_positive(self):
        _, _, _, routes = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)]
        )
        for route in routes.routes:
            assert route.total_distance_m > 0

    def test_route_time_positive(self):
        _, _, _, routes = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)]
        )
        for route in routes.routes:
            assert route.estimated_time_min > 0

    def test_pentagon_routes(self):
        _, _, _, routes = _run_polygon_pipeline(
            [(0, 0), (600, 0), (800, 300), (400, 600), (0, 400)]
        )
        assert len(routes.routes) > 0
        for route in routes.routes:
            assert route.num_passes > 0

    def test_triangle_routes(self):
        _, _, _, routes = _run_polygon_pipeline(
            [(0, 0), (800, 0), (400, 600)], num_drones=3
        )
        for route in routes.routes:
            assert route.total_distance_m > 0

    def test_total_distance_consistency(self):
        _, _, _, routes = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)]
        )
        computed_total = sum(r.total_distance_m for r in routes.routes)
        assert abs(routes.total_distance_m - computed_total) < 1.0

    def test_efficiency_score_valid(self):
        _, _, _, routes = _run_polygon_pipeline(
            [(0, 0), (800, 0), (800, 500), (0, 500)]
        )
        assert 0.0 <= routes.efficiency_score <= 1.0
