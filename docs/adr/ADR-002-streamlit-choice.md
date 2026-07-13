# ADR-002: Streamlit as UI Framework

**Status**: Accepted
**Date**: 2026-06-21

## Context

The MVP needs a user interface that:
- Is professional enough for public demonstrations and LinkedIn publication
- Supports interactive data visualization (charts, maps, dashboards)
- Can be developed rapidly without frontend expertise
- Runs locally with minimal setup
- Is easy to deploy (Docker, cloud platforms)

Alternatives considered:
- **Flask + React**: Full control but high development overhead
- **Dash (Plotly)**: Good for dashboards but more verbose than Streamlit
- **Gradio**: Optimized for ML demos, less flexible for custom dashboards
- **Panel (HoloViews)**: Powerful but smaller community

## Decision

Use **Streamlit** as the primary UI framework, with **Plotly** for interactive visualizations.

## Consequences

**Positive**:
- Rapid development — Python-only, no JavaScript required
- Built-in layout system (columns, tabs, sidebars, expanders)
- Native support for data tables, metrics, and charts
- Active community and extensive widget ecosystem
- Easy Docker deployment
- Automatic re-run on parameter change creates reactive feel

**Negative**:
- Limited customization compared to full frontend frameworks
- Not suitable for production multi-user applications at scale
- Session state management can become complex for large apps
- Server-side rendering limits client-side interactivity

**Mitigations**:
- Plotly fills visualization gaps that Streamlit's built-in charts cannot cover
- Custom CSS injection provides additional styling control
- Future versions can migrate to a full frontend while keeping the core engine unchanged (ADR-001 separation)
