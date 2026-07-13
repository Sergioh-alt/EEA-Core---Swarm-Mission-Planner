# ADR-004: Real Geometry Engine (Phase 2)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 2 — GIS Geometry Engine

## Context

v0.1 used a synthetic rectangular field approximation (`_estimate_field_dimensions()`) that computed `side = sqrt(area_m2)`, `width = side * 1.2`, `height = area / width`. This prevented the system from supporting real-world irregularly shaped fields.

Phase 2 required:
- Real polygon-based field representation
- Shapely integration for geometry operations
- Full backward compatibility with v0.1 outputs

Alternatives considered:
- **Manual polygon math**: Implement area/centroid/bounds calculations manually
- **Shapely**: Use the industry-standard computational geometry library
- **GeoPandas**: Full GIS stack with CRS support

## Decision

Adopt **Shapely** as the geometry backend and introduce `FieldGeometry` as the canonical field representation:

```python
@dataclass
class FieldGeometry:
    boundary: Polygon
    area_m2: float
    area_ha: float
    centroid: tuple[float, float]
    bounds: tuple[float, float, float, float]
    perimeter_m: float
    is_synthetic: bool = False
```

Two constructors:
- `from_hectares(ha)` — replicates v0.1's synthetic rectangle (sets `is_synthetic=True`)
- `from_points([(x,y)...])` — builds from user-drawn vertices with validation

All downstream modules branch on `is_synthetic` to choose v0.1-compatible or polygon-aware code paths.

`compute_polygon_orientation()` centralizes MABR (minimum-area bounding rectangle) calculation, shared by SwarmPlanner and RoutePlanner.

## Consequences

**Positive**:
- Real polygon fields are now supported (convex shapes)
- `from_hectares()` produces bit-identical results to v0.1
- Shapely provides robust intersection, clipping, and validation
- Single geometry module (`core/geometry.py`) prevents duplication

**Negative**:
- New dependency: `shapely>=2.0.0` (C-extension, requires GEOS)
- `is_synthetic` flag introduces branching in downstream modules
- Polygon validation adds latency for malformed inputs

**Mitigations**:
- Shapely 2.x uses compiled GEOS — geometry ops are sub-millisecond
- Branching is confined to `plan_swarm()` and `plan_routes()` entry points
- Validation errors raise `ValueError` with clear messages
