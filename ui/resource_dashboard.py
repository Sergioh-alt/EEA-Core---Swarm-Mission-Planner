"""
Resource Dashboard
"""

import streamlit as st
import plotly.graph_objects as go

from core.resource_planner import ResourcePlan
from core.mission_intake import MissionProfile
from ui.components import section_header, metric_card
from ui.swarm_view import DRONE_COLORS


def render_resource_dashboard(resources: ResourcePlan, profile: MissionProfile):
    section_header("Resource Planning", "")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Mission Duration", resources.mission_duration_formatted)
    with c2:
        metric_card("Total Liquid", f"{resources.total_liquid_l} L")
    with c3:
        refill_color = "good" if resources.total_refills <= profile.num_drones else "warning"
        metric_card("Total Refills", str(resources.total_refills), color=refill_color)
    with c4:
        metric_card("Bottleneck", resources.bottleneck.split(" — ")[0],
                     delta=resources.bottleneck.split(" — ")[1] if " — " in resources.bottleneck else "")

    tab_battery, tab_liquid, tab_timeline = st.tabs(["Battery", "Liquid", "Timeline"])

    with tab_battery:
        _render_battery_chart(resources)

    with tab_liquid:
        _render_liquid_chart(resources, profile)

    with tab_timeline:
        _render_timeline(resources)


def _render_battery_chart(resources: ResourcePlan):
    drones = [f"Drone {dr.drone_id}" for dr in resources.drone_resources]
    consumptions = [dr.battery_consumption_pct for dr in resources.drone_resources]

    colors = []
    for pct in consumptions:
        if pct > 100:
            colors.append("#f44336")
        elif pct > 80:
            colors.append("#ff9800")
        else:
            colors.append("#4caf50")

    fig = go.Figure(go.Bar(
        x=drones,
        y=consumptions,
        marker_color=colors,
        text=[f"{c:.0f}%" for c in consumptions],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Battery: %{y:.1f}%<extra></extra>",
    ))

    fig.add_hline(y=100, line_dash="dash", line_color="#f44336",
                  annotation_text="Battery Limit")
    fig.add_hline(y=85, line_dash="dot", line_color="#ff9800",
                  annotation_text="Warning Zone")

    fig.update_layout(
        title="Battery Consumption per Drone",
        yaxis_title="Consumption (%)",
        height=400,
        template="plotly_dark",
        margin=dict(l=40, r=40, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_liquid_chart(resources: ResourcePlan, profile: MissionProfile):
    drones = [f"Drone {dr.drone_id}" for dr in resources.drone_resources]
    needed = [dr.liquid_needed_l for dr in resources.drone_resources]
    capacity = profile.liquid_capacity_l

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=drones, y=needed,
        name="Liquid Needed",
        marker_color="#2196F3",
        text=[f"{n:.1f} L" for n in needed],
        textposition="outside",
    ))

    fig.add_hline(y=capacity, line_dash="dash", line_color="#4caf50",
                  annotation_text=f"Tank Capacity ({capacity} L)")

    fig.update_layout(
        title="Liquid Requirements per Drone",
        yaxis_title="Liters",
        height=400,
        template="plotly_dark",
        margin=dict(l=40, r=40, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_timeline(resources: ResourcePlan):
    fig = go.Figure()

    for dr in resources.drone_resources:
        color = DRONE_COLORS[(dr.drone_id - 1) % len(DRONE_COLORS)]

        fig.add_trace(go.Bar(
            y=[f"Drone {dr.drone_id}"],
            x=[dr.flight_time_min],
            orientation="h",
            name=f"D{dr.drone_id} Flight",
            marker_color=color,
            text=f"{dr.flight_time_min:.0f} min",
            textposition="inside",
            showlegend=dr.drone_id == 1,
            legendgroup="flight",
        ))

        if dr.refill_time_min > 0:
            fig.add_trace(go.Bar(
                y=[f"Drone {dr.drone_id}"],
                x=[dr.refill_time_min],
                orientation="h",
                name=f"D{dr.drone_id} Refill",
                marker_color=color,
                marker_pattern_shape="/",
                text=f"+{dr.refill_time_min:.0f} min",
                textposition="inside",
                showlegend=dr.drone_id == 1,
                legendgroup="refill",
            ))

    fig.update_layout(
        title="Mission Timeline per Drone",
        xaxis_title="Time (minutes)",
        barmode="stack",
        height=max(300, len(resources.drone_resources) * 50 + 100),
        template="plotly_dark",
        margin=dict(l=80, r=40, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
