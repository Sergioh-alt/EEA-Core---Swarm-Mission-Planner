"""
Mission Configuration Panel

Supports two field input modes:
- Slider (v0.1 compat): scalar hectares input
- Draw Polygon (v0.2): manual vertex entry with live polygon preview
"""

import streamlit as st
import plotly.graph_objects as go

from config.settings import CROP_PROFILES
from core.geometry import FieldGeometry


def render_mission_config() -> dict:
    st.sidebar.markdown(
        """
        <div style="text-align:center; padding:10px 0 5px 0;">
            <span style="font-size:1.6rem; font-weight:800; letter-spacing:1px;">
                EEA CORE
            </span><br/>
            <span style="font-size:0.75rem; color:#888; letter-spacing:2px;">
                SWARM MISSION PLANNER
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("---")

    st.sidebar.markdown("#### Field Parameters")

    field_mode = st.sidebar.radio(
        "Field Input Mode",
        options=["Slider", "Draw Polygon"],
        index=0,
        horizontal=True,
        help="Slider uses a scalar area value. Draw Polygon allows manual field boundary definition.",
    )

    field_geometry = None

    if field_mode == "Slider":
        field_size = st.sidebar.number_input(
            "Field Size (hectares)",
            min_value=0.1, max_value=10000.0, value=50.0, step=5.0,
            help="Total area to be covered by the drone swarm",
        )
    else:
        field_size, field_geometry = _render_polygon_input()

    crop_type = st.sidebar.selectbox(
        "Crop Type",
        options=list(CROP_PROFILES.keys()),
        index=0,
        format_func=lambda x: x.capitalize(),
        help="Crop type affects spray rate, altitude, and complexity",
    )

    st.sidebar.markdown("#### Drone Fleet")
    num_drones = st.sidebar.slider(
        "Number of Drones",
        min_value=1, max_value=20, value=4,
        help="Total drones available for the mission",
    )

    battery_capacity = st.sidebar.number_input(
        "Battery Capacity (mAh)",
        min_value=1000, max_value=50000, value=5000, step=500,
        help="Per-drone battery capacity in milliamp-hours",
    )

    liquid_capacity = st.sidebar.number_input(
        "Liquid Capacity (L)",
        min_value=1.0, max_value=100.0, value=10.0, step=1.0,
        help="Per-drone liquid tank capacity in liters",
    )

    st.sidebar.markdown("#### Weather Conditions")
    temperature = st.sidebar.slider(
        "Temperature (C)",
        min_value=-10, max_value=50, value=25,
        help="Ambient temperature at the field",
    )

    wind_speed = st.sidebar.slider(
        "Wind Speed (km/h)",
        min_value=0, max_value=60, value=10,
        help="Current wind speed at the field",
    )

    st.sidebar.markdown("---")

    crop_info = CROP_PROFILES.get(crop_type, CROP_PROFILES["generic"])
    st.sidebar.markdown(
        f"""
        <div style="background:#1e1e2e; padding:10px; border-radius:6px; font-size:0.8rem;">
            <strong>Crop Profile: {crop_type.capitalize()}</strong><br/>
            Spray Rate: {crop_info['spray_rate_l_per_ha']} L/ha<br/>
            Altitude: {crop_info['flight_altitude_m']} m<br/>
            Complexity: {crop_info['complexity'].capitalize()}<br/>
            <em>{crop_info['notes']}</em>
        </div>
        """,
        unsafe_allow_html=True,
    )

    result = {
        "field_size_ha": field_size,
        "crop_type": crop_type,
        "num_drones": num_drones,
        "battery_capacity_mah": battery_capacity,
        "liquid_capacity_l": liquid_capacity,
        "temperature_c": temperature,
        "wind_speed_kmh": wind_speed,
    }

    if field_geometry is not None:
        result["field_geometry"] = field_geometry

    return result


def _render_polygon_input() -> tuple[float, FieldGeometry | None]:
    """Render polygon drawing interface and return (area_ha, field_geometry)."""

    if "polygon_points" not in st.session_state:
        st.session_state.polygon_points = []

    st.sidebar.markdown(
        '<div style="font-size:0.8rem; color:#aaa; margin-bottom:8px;">'
        "Add vertices (X, Y in meters) to define the field boundary."
        "</div>",
        unsafe_allow_html=True,
    )

    col_x, col_y = st.sidebar.columns(2)
    with col_x:
        new_x = st.number_input("X (m)", value=0.0, step=50.0, key="new_point_x")
    with col_y:
        new_y = st.number_input("Y (m)", value=0.0, step=50.0, key="new_point_y")

    col_add, col_undo, col_clear = st.sidebar.columns(3)
    with col_add:
        if st.button("Add Point", use_container_width=True):
            st.session_state.polygon_points.append((new_x, new_y))
            st.rerun()
    with col_undo:
        if st.button("Undo", use_container_width=True):
            if st.session_state.polygon_points:
                st.session_state.polygon_points.pop()
                st.rerun()
    with col_clear:
        if st.button("Clear", use_container_width=True):
            st.session_state.polygon_points = []
            st.rerun()

    points = st.session_state.polygon_points
    num_points = len(points)

    st.sidebar.markdown(
        f'<div style="font-size:0.8rem; color:#ccc;">Points: <b>{num_points}</b></div>',
        unsafe_allow_html=True,
    )

    if num_points > 0:
        pts_str = " | ".join([f"({p[0]:.0f}, {p[1]:.0f})" for p in points])
        st.sidebar.markdown(
            f'<div style="font-size:0.7rem; color:#888; word-wrap:break-word;">{pts_str}</div>',
            unsafe_allow_html=True,
        )

    # Preset shapes for quick testing
    preset = st.sidebar.selectbox(
        "Quick Presets",
        options=["(none)", "Rectangle 800x500", "Pentagon", "Hexagon", "L-shape"],
        index=0,
        help="Load a predefined shape for testing",
    )
    if preset != "(none)" and st.sidebar.button("Load Preset"):
        st.session_state.polygon_points = _get_preset_points(preset)
        st.rerun()

    field_geometry = None
    area_ha = 0.1

    if num_points >= 3:
        try:
            field_geometry = FieldGeometry.from_points(points)
            area_ha = field_geometry.area_ha

            st.sidebar.markdown(
                f"""
                <div style="background:#1a3a1a; padding:8px; border-radius:6px;
                            font-size:0.8rem; border-left:3px solid #4CAF50;">
                    <b>Area:</b> {area_ha:.2f} ha ({field_geometry.area_m2:.0f} m&sup2;)<br/>
                    <b>Perimeter:</b> {field_geometry.perimeter_m:.0f} m
                </div>
                """,
                unsafe_allow_html=True,
            )
        except ValueError as e:
            st.sidebar.error(f"Invalid polygon: {e}")
            field_geometry = None
    elif num_points > 0:
        st.sidebar.info(f"Need at least 3 points ({3 - num_points} more)")

    _render_polygon_preview(points, field_geometry)

    return area_ha if area_ha > 0.1 else 0.1, field_geometry


def _render_polygon_preview(points: list[tuple[float, float]], field_geometry):
    """Render a live preview of the polygon being drawn."""
    fig = go.Figure()

    if len(points) >= 3 and field_geometry is not None:
        coords = list(field_geometry.boundary.exterior.coords)
        fig.add_trace(go.Scatter(
            x=[c[0] for c in coords],
            y=[c[1] for c in coords],
            fill="toself",
            fillcolor="rgba(76, 175, 80, 0.15)",
            line=dict(color="#4CAF50", width=2),
            name="Field Boundary",
            hoverinfo="skip",
        ))

    if points:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            marker=dict(size=10, color="#FF9800", symbol="circle"),
            text=[f"P{i+1}" for i in range(len(points))],
            textposition="top center",
            textfont=dict(size=9, color="#FF9800"),
            name="Vertices",
        ))

        if len(points) >= 2:
            fig.add_trace(go.Scatter(
                x=xs + [xs[0]],
                y=ys + [ys[0]],
                mode="lines",
                line=dict(color="#FF9800", width=1, dash="dash"),
                name="Edges",
                hoverinfo="skip",
            ))

    all_x = [p[0] for p in points] if points else [0, 1000]
    all_y = [p[1] for p in points] if points else [0, 1000]
    margin = 100
    x_range = [min(all_x) - margin, max(all_x) + margin]
    y_range = [min(all_y) - margin, max(all_y) + margin]

    fig.update_layout(
        height=250,
        template="plotly_dark",
        xaxis=dict(title="X (m)", range=x_range, scaleanchor="y", scaleratio=1),
        yaxis=dict(title="Y (m)", range=y_range),
        margin=dict(l=30, r=10, t=10, b=30),
        showlegend=False,
    )

    st.sidebar.plotly_chart(fig, use_container_width=True)


def _get_preset_points(preset: str) -> list[tuple[float, float]]:
    """Return predefined polygon points for quick testing."""
    presets = {
        "Rectangle 800x500": [(0, 0), (800, 0), (800, 500), (0, 500)],
        "Pentagon": [(0, 0), (600, 0), (800, 300), (400, 600), (0, 400)],
        "Hexagon": [(200, 0), (600, 0), (800, 350), (600, 700), (200, 700), (0, 350)],
        "L-shape": [(0, 0), (600, 0), (600, 300), (300, 300), (300, 600), (0, 600)],
    }
    return presets.get(preset, [])
