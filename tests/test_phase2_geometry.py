"""
Phase 2 — GIS Geometry Engine Tests

Tests for FieldGeometry construction, validation, and backward compatibility.
"""

import pytest
from shapely.geometry import box

from core.geometry import FieldGeometry, compute_polygon_orientation, SectorGeometry


class TestFieldGeometryFromHectares:
    """FieldGeometry.from_hectares() must replicate v0.1 dimensions."""

    def test_50ha_dimensions(self):
        fg = FieldGeometry.from_hectares(50.0)
        assert fg.bounds == (0, 0, 848.5, 589.3)
        assert fg.is_synthetic is True

    def test_area_consistency(self):
        fg = FieldGeometry.from_hectares(50.0)
        assert abs(fg.area_ha - fg.boundary.area / 10000) < 0.01

    def test_perimeter_consistency(self):
        fg = FieldGeometry.from_hectares(50.0)
        assert abs(fg.perimeter_m - fg.boundary.length) < 0.01

    def test_centroid_inside_boundary(self):
        fg = FieldGeometry.from_hectares(50.0)
        from shapely.geometry import Point
        assert fg.boundary.contains(Point(fg.centroid))

    def test_various_sizes(self):
        for ha in [1.0, 10.0, 100.0, 1000.0]:
            fg = FieldGeometry.from_hectares(ha)
            assert fg.is_synthetic is True
            assert fg.area_m2 > 0
            assert fg.perimeter_m > 0

    def test_small_field(self):
        fg = FieldGeometry.from_hectares(0.1)
        assert fg.area_m2 > 0
        assert fg.is_synthetic is True


class TestFieldGeometryFromPoints:
    """FieldGeometry.from_points() polygon construction and validation."""

    def test_rectangle(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        assert fg.is_synthetic is False
        assert abs(fg.area_m2 - 400000) < 1
        assert abs(fg.perimeter_m - 2600) < 1

    def test_triangle(self):
        fg = FieldGeometry.from_points([(0, 0), (600, 0), (300, 400)])
        assert fg.is_synthetic is False
        assert fg.area_m2 > 0

    def test_pentagon(self):
        fg = FieldGeometry.from_points([(0, 0), (600, 0), (800, 300), (400, 600), (0, 400)])
        assert fg.is_synthetic is False
        assert fg.area_m2 > 0

    def test_hexagon(self):
        fg = FieldGeometry.from_points([(200, 0), (600, 0), (800, 350), (600, 700), (200, 700), (0, 350)])
        assert fg.is_synthetic is False
        assert fg.area_m2 > 0

    def test_rejects_too_few_points(self):
        with pytest.raises(ValueError, match="At least 3 points"):
            FieldGeometry.from_points([(0, 0), (1, 0)])

    def test_rejects_single_point(self):
        with pytest.raises(ValueError):
            FieldGeometry.from_points([(0, 0)])

    def test_rejects_collinear_points(self):
        with pytest.raises(ValueError):
            FieldGeometry.from_points([(0, 0), (1, 0), (2, 0)])

    def test_rejects_near_zero_area(self):
        with pytest.raises(ValueError):
            FieldGeometry.from_points([(0, 0), (0.001, 0), (0, 0.001)])

    def test_centroid_inside_polygon(self):
        fg = FieldGeometry.from_points([(0, 0), (800, 0), (800, 500), (0, 500)])
        from shapely.geometry import Point
        assert fg.boundary.contains(Point(fg.centroid))

    def test_bounds_match_polygon(self):
        fg = FieldGeometry.from_points([(100, 200), (900, 200), (900, 700), (100, 700)])
        assert fg.bounds == (100.0, 200.0, 900.0, 700.0)


class TestComputePolygonOrientation:
    """MABR orientation calculation."""

    def test_horizontal_rectangle(self):
        rect = box(0, 0, 800, 500)
        angle = compute_polygon_orientation(rect)
        assert abs(angle) < 0.01

    def test_vertical_rectangle(self):
        rect = box(0, 0, 500, 800)
        angle = compute_polygon_orientation(rect)
        assert abs(abs(angle) - 90) < 0.01

    def test_square_returns_valid_angle(self):
        sq = box(0, 0, 500, 500)
        angle = compute_polygon_orientation(sq)
        assert -180 <= angle <= 180

    def test_rotated_rectangle(self):
        fg = FieldGeometry.from_points([(0, 0), (600, 300), (500, 500), (-100, 200)])
        angle = compute_polygon_orientation(fg.boundary)
        assert -180 <= angle <= 180


class TestSectorGeometry:
    """SectorGeometry dataclass construction."""

    def test_basic_construction(self):
        poly = box(0, 0, 100, 100)
        sg = SectorGeometry(
            id=1,
            drone_id=1,
            boundary=poly,
            area_m2=10000,
            area_ha=1.0,
            centroid=(50.0, 50.0),
        )
        assert sg.id == 1
        assert sg.area_ha == 1.0
