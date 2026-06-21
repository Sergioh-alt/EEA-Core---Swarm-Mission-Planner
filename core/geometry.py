"""
Field Geometry Module

Provides the canonical FieldGeometry representation used by all
geometry-aware modules. Supports construction from hectares (v0.1
backward compatibility) and from user-drawn polygon points.
"""

import math
from dataclasses import dataclass

from shapely.geometry import Polygon, box
from shapely.validation import make_valid

from utils.logger import get_logger

logger = get_logger("geometry")


@dataclass
class FieldGeometry:
    """Canonical field representation in local metric coordinates (meters)."""

    boundary: Polygon
    area_m2: float
    area_ha: float
    centroid: tuple[float, float]
    bounds: tuple[float, float, float, float]  # (minx, miny, maxx, maxy)
    perimeter_m: float

    @classmethod
    def from_hectares(cls, ha: float) -> "FieldGeometry":
        """
        Build a synthetic rectangle matching v0.1's _estimate_field_dimensions().

        Replicates: side = sqrt(area_m2), width = side * 1.2, height = area / width,
        both rounded to 1 decimal place.
        """
        area_m2 = ha * 10000
        side = math.sqrt(area_m2)
        width = round(side * 1.2, 1)
        height = round(area_m2 / (side * 1.2), 1)

        boundary = box(0, 0, width, height)
        centroid = boundary.centroid

        return cls(
            boundary=boundary,
            area_m2=boundary.area,
            area_ha=boundary.area / 10000,
            centroid=(centroid.x, centroid.y),
            bounds=boundary.bounds,
            perimeter_m=boundary.length,
        )

    @classmethod
    def from_points(cls, points: list[tuple[float, float]]) -> "FieldGeometry":
        """
        Build from user-drawn vertices in local metric coordinates.

        Points are (x, y) tuples in meters. Minimum 3 non-collinear points
        required. The polygon is closed automatically.
        """
        if len(points) < 3:
            raise ValueError("At least 3 points are required to define a field boundary.")

        boundary = Polygon(points)

        if not boundary.is_valid:
            logger.warning("Invalid polygon — attempting auto-fix")
            boundary = make_valid(boundary)
            if not isinstance(boundary, Polygon):
                raise ValueError(
                    "Points do not form a valid polygon. "
                    "Ensure the boundary does not self-intersect."
                )

        if boundary.is_empty or boundary.area < 1.0:
            raise ValueError("Polygon area is too small (< 1 m²).")

        centroid = boundary.centroid

        logger.info(
            "Field geometry from points: %.1f ha, %d vertices",
            boundary.area / 10000,
            len(points),
        )

        return cls(
            boundary=boundary,
            area_m2=boundary.area,
            area_ha=boundary.area / 10000,
            centroid=(centroid.x, centroid.y),
            bounds=boundary.bounds,
            perimeter_m=boundary.length,
        )


@dataclass
class SectorGeometry:
    """A sector assigned to a drone, defined by an arbitrary polygon boundary."""

    id: int
    drone_id: int
    boundary: Polygon
    area_m2: float
    area_ha: float
    centroid: tuple[float, float]
