# ADR-006: UI Geometry Input Design (Phase 4)

**Status**: Accepted
**Date**: 2026-06-21
**Phase**: 4 — UI Geometry & Interactive Design

## Context

Phase 4 needed to let users define custom polygon fields through the Streamlit UI. Challenges:
- Streamlit does not natively support click-to-draw on canvas
- The system must support both scalar (hectares) and polygon inputs simultaneously
- Polygon preview must update live as vertices are added

Approaches considered:
- **Streamlit-drawable-canvas**: External widget with click-to-draw, but limited coordinate precision and heavy dependency
- **Plotly click events**: Native Plotly interaction, but Streamlit's event model makes real-time click capture unreliable
- **Manual coordinate entry + live preview**: Numeric inputs for X,Y coordinates with Plotly polygon preview

## Decision

Adopt **manual coordinate entry with live Plotly preview and preset shapes**:

### Dual-mode sidebar
- **Slider mode** (default): unchanged v0.1 hectares input
- **Draw Polygon mode**: X,Y coordinate entry with Add/Undo/Clear controls

### Features
- Live Plotly polygon preview updates on each vertex change
- Area and perimeter displayed when polygon is valid (>= 3 points)
- Quick presets: Rectangle 800x500, Pentagon, Hexagon, L-shape
- Invalid polygon detection with user-facing error messages
- `FieldGeometry` constructed via `from_points()` on valid polygon

### Visualization
- `swarm_view.py` renders polygon sector boundaries (strip mode) or rectangular sectors (grid mode)
- Routes rendered as sweep-line paths clipped to sector polygons
- Assignment table includes perimeter column for polygon sectors

## Consequences

**Positive**:
- No new dependencies — uses existing Plotly and Streamlit
- Precise coordinate control (numeric input, not mouse drawing)
- Preset shapes enable quick testing without manual entry
- Dual-mode preserves v0.1 slider workflow unchanged

**Negative**:
- Coordinate entry is less intuitive than click-to-draw for non-technical users
- Requires manual conversion from real-world coordinates (no GPS/map integration)
- Presets are hardcoded shapes (not configurable)

**Mitigations**:
- Presets cover the most common testing scenarios
- Future phases can add map-based drawing (GeoJSON import, satellite tiles)
- Live preview provides immediate visual feedback
