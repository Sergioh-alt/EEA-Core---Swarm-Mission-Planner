# ADR-005: Polygon Routing Strategy (Phase 3)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 3 — Polygon Swarm & Route Intelligence

## Context

With real polygon fields (Phase 2), the grid-based partitioning and fixed-height boustrophedon routing no longer work for non-rectangular shapes. Phase 3 needed:

- A partitioning strategy that works with arbitrary convex polygons
- A routing algorithm that generates valid passes within polygon boundaries
- Preservation of v0.1 behavior for rectangular/slider inputs

Strategies considered:
- **Voronoi partitioning**: Area-balanced but complex; produces irregular sectors hard to route
- **Strip partitioning + MABR alignment**: Simple, deterministic, aligns strips to the field's long axis
- **Quadtree decomposition**: Adaptive grid; overkill for convex-only fields

## Decision

Adopt **MABR-aligned strip partitioning** with **polygon-clipped boustrophedon sweep routing**:

### Partitioning (`_plan_strips`)
1. Compute polygon's MABR orientation via `compute_polygon_orientation()`
2. Rotate polygon so the long axis is horizontal
3. Divide the bounding box into N vertical strips (one per drone)
4. Clip each strip to the rotated polygon boundary
5. Rotate clipped sectors back to original orientation

### Routing (`_generate_polygon_route`)
1. Rotate sector polygon so its MABR is axis-aligned
2. Generate vertical sweep lines at `spray_width` intervals
3. Intersect each sweep line with the polygon to get variable-length pass endpoints
4. Connect passes in boustrophedon order
5. Rotate waypoints back to original coordinates

### Strategy selection
- `is_synthetic=True` (from hectares) → grid partition + rectangular route (v0.1)
- `is_synthetic=False` (from points) → strip partition + polygon sweep route (v0.2)

## Consequences

**Positive**:
- Deterministic and explainable — no randomness or heuristics
- Strips align naturally to the field's optimal coverage direction
- Sweep-line intersection handles variable-width passes correctly
- v0.1 path is completely preserved (separate code path)

**Negative**:
- Strip partition may produce uneven areas for highly non-rectangular fields (balance score < 1.0)
- Concave polygons may produce multi-segment sweep intersections (not handled yet)
- Two code paths increases maintenance surface

**Mitigations**:
- Balance score is computed and displayed to the user
- Concave polygon handling explicitly deferred to v0.3+
- Both code paths share `compute_polygon_orientation()` from `core/geometry.py`
