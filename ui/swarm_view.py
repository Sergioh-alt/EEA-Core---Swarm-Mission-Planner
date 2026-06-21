"""
Swarm Allocation Visualization
"""

import streamlit as st
import plotly.graph_objects as go

from core.swarm_planner import SwarmPlan
from core.route_planner import RoutePlan
from ui.components import section_header, metric_card


DRONE_COLORS = [
    "#2196F3", "#4CAF50", "#FF9800", "#E91E63", "#9C27B0",
    "#00BCD4", "#FF5722", "#3F51B5", "#CDDC39", "#795548",
    "#607D8B", "#F44336", "#009688", "#FFC107", "#673AB7",
    "#03A9F4", "#8BC34A", "#FF5252", "#7C4DFF", "#18FFFF",
]


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def render_swarm_view(swarm: SwarmPlan, routes: RoutePlan):
    section_header("Swarm Allocation", "")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Sectors", str(len(swarm.sectors)))
    with c2:
        metric_card("Grid", f"{swarm.grid_cols} x {swarm.grid_rows}")
    with c3:
        metric_card("Area/Drone", f"{swarm.area_per_drone_ha} ha")
    with c4:
        balance_color = "good" if swarm.balance_score > 0.9 else "warning"
        metric_card("Balance", f"{swarm.balance_score:.1%}", color=balance_color)

    tab_map, tab_routes, tab_table = st.tabs(["Sector Map", "Route Preview", "Assignment Table"])

    with tab_map:
        _render_sector_map(swarm)

    with tab_routes:
        _render_route_preview(swarm, routes)

    with tab_table:
        _render_assignment_table(swarm, routes)


def _render_sector_map(swarm: SwarmPlan):
    fig = go.Figure()

    for sector in swarm.sectors:
        color = DRONE_COLORS[(sector.drone_id - 1) % len(DRONE_COLORS)]
        fig.add_trace(go.Scatter(
            x=[sector.x_start, sector.x_end, sector.x_end, sector.x_start, sector.x_start],
            y=[sector.y_start, sector.y_start, sector.y_end, sector.y_end, sector.y_start],
            fill="toself",
            fillcolor=_hex_to_rgba(color, 0.2),
            line=dict(color=color, width=2),
            name=f"Drone {sector.drone_id}",
            hovertemplate=(
                f"<b>Sector {sector.id}</b><br>"
                f"Drone: {sector.drone_id}<br>"
                f"Area: {sector.area_ha} ha<br>"
                f"Size: {sector.width_m:.0f} x {sector.height_m:.0f} m"
                "<extra></extra>"
            ),
        ))

        cx = (sector.x_start + sector.x_end) / 2
        cy = (sector.y_start + sector.y_end) / 2
        fig.add_annotation(
            x=cx, y=cy,
            text=f"D{sector.drone_id}",
            showarrow=False,
            font=dict(size=14, color=color, family="Arial Black"),
        )

    fig.update_layout(
        title=dict(text="Field Sector Map", font=dict(size=16)),
        xaxis_title="Width (m)",
        yaxis_title="Height (m)",
        height=500,
        showlegend=True,
        template="plotly_dark",
        xaxis=dict(scaleanchor="y", scaleratio=1),
        margin=dict(l=40, r=40, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_route_preview(swarm: SwarmPlan, routes: RoutePlan):
    fig = go.Figure()

    for sector in swarm.sectors:
        color = DRONE_COLORS[(sector.drone_id - 1) % len(DRONE_COLORS)]
        fig.add_trace(go.Scatter(
            x=[sector.x_start, sector.x_end, sector.x_end, sector.x_start, sector.x_start],
            y=[sector.y_start, sector.y_start, sector.y_end, sector.y_end, sector.y_start],
            fill="toself",
            fillcolor=_hex_to_rgba(color, 0.07),
            line=dict(color=color, width=1, dash="dot"),
            name=f"Sector {sector.id}",
            showlegend=False,
        ))

    for route in routes.routes:
        color = DRONE_COLORS[(route.drone_id - 1) % len(DRONE_COLORS)]
        xs = [wp.x for wp in route.waypoints]
        ys = [wp.y for wp in route.waypoints]
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=4, color=color),
            name=f"Drone {route.drone_id} route",
            hovertemplate=(
                f"<b>Drone {route.drone_id}</b><br>"
                f"Passes: {route.num_passes}<br>"
                f"Distance: {route.total_distance_m:.0f} m<br>"
                f"Time: {route.estimated_time_min:.1f} min"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        title=dict(text="Route Preview (Boustrophedon Pattern)", font=dict(size=16)),
        xaxis_title="Width (m)",
        yaxis_title="Height (m)",
        height=500,
        showlegend=True,
        template="plotly_dark",
        xaxis=dict(scaleanchor="y", scaleratio=1),
        margin=dict(l=40, r=40, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_assignment_table(swarm: SwarmPlan, routes: RoutePlan):
    route_map = {r.drone_id: r for r in routes.routes}
    data = []
    for sector in swarm.sectors:
        route = route_map.get(sector.drone_id)
        data.append({
            "Sector": sector.id,
            "Drone": sector.drone_id,
            "Area (ha)": sector.area_ha,
            "Width (m)": round(sector.width_m),
            "Height (m)": round(sector.height_m),
            "Passes": route.num_passes if route else 0,
            "Distance (m)": round(route.total_distance_m) if route else 0,
            "Time (min)": round(route.estimated_time_min, 1) if route else 0,
        })
    st.dataframe(data, use_container_width=True, hide_index=True)
