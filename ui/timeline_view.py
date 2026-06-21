"""
Mission Timeline View (Phase 6)

Renders the realism-layer timeline, drone physics,
battery model, and liquid model in the Streamlit UI.
"""

import streamlit as st
import plotly.graph_objects as go

from core.mission_timeline import MissionTimeline, DroneTimeline


EVENT_COLORS = {
    "launch": "#9C27B0",
    "transit": "#607D8B",
    "spraying": "#4CAF50",
    "refill": "#2196F3",
    "battery_swap": "#FF9800",
    "return": "#607D8B",
    "complete": "#9E9E9E",
}

EVENT_LABELS = {
    "launch": "Launch",
    "transit": "Transit",
    "spraying": "Spray",
    "refill": "Refill",
    "battery_swap": "Batt Swap",
    "return": "Return",
    "complete": "Done",
}


def render_timeline_view(timeline: MissionTimeline):
    """Render the full mission timeline dashboard."""

    st.markdown(
        '<h3 style="margin-bottom:0.5rem;">Mission Timeline</h3>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Mission Duration", timeline.mission_duration_formatted)
    with c2:
        st.metric("Drones", len(timeline.drone_timelines))
    with c3:
        st.metric("Total Events", timeline.total_events)

    _render_gantt_chart(timeline)

    st.markdown("---")

    for dt in timeline.drone_timelines:
        _render_drone_detail(dt)


def _render_gantt_chart(timeline: MissionTimeline):
    """Render a Gantt-style chart of all drone events."""
    fig = go.Figure()

    legend_shown: set[str] = set()

    for dt in reversed(timeline.drone_timelines):
        drone_label = f"Drone {dt.drone_id}"
        for event in dt.events:
            if event.duration_min <= 0:
                continue
            etype = event.event_type
            color = EVENT_COLORS.get(etype, "#9E9E9E")
            label = EVENT_LABELS.get(etype, etype)
            show_legend = etype not in legend_shown
            if show_legend:
                legend_shown.add(etype)

            fig.add_trace(go.Bar(
                y=[drone_label],
                x=[event.duration_min],
                orientation="h",
                name=label,
                legendgroup=etype,
                showlegend=show_legend,
                marker_color=color,
                hovertemplate=(
                    f"<b>{drone_label}</b><br>"
                    f"{label}: {event.description}<br>"
                    f"Start: {event.timestamp_formatted}<br>"
                    f"Duration: {event.duration_min:.1f} min<extra></extra>"
                ),
            ))

    fig.update_layout(
        title="Mission Execution Timeline",
        xaxis_title="Time (minutes)",
        barmode="stack",
        height=max(300, len(timeline.drone_timelines) * 60 + 120),
        template="plotly_dark",
        margin=dict(l=80, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_drone_detail(dt: DroneTimeline):
    """Render detailed breakdown for a single drone."""
    with st.expander(f"Drone {dt.drone_id} — {dt.total_duration_formatted}", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Spray Time", f"{dt.spray_time_min:.1f} min")
        with col2:
            st.metric("Transit Time", f"{dt.transit_time_min:.1f} min")
        with col3:
            st.metric("Idle/Refill", f"{dt.idle_time_min:.1f} min")

        # Physics summary
        st.markdown("**Drone Physics**")
        p = dt.physics
        pcols = st.columns(4)
        with pcols[0]:
            st.metric("Effective Speed", f"{p.effective_speed_kmh} km/h")
        with pcols[1]:
            st.metric("Wind Speed Loss", f"-{p.speed_reduction_wind_pct}%")
        with pcols[2]:
            st.metric("Payload", f"{p.payload_weight_kg} kg")
        with pcols[3]:
            st.metric("Turn Time", f"{p.total_turn_time_s:.0f}s")

        # Battery breakdown
        st.markdown("**Battery Model**")
        b = dt.battery
        bcols = st.columns(4)
        with bcols[0]:
            st.metric("Base", f"{b.base_consumption_wh} Wh")
        with bcols[1]:
            st.metric("+ Wind", f"{b.wind_penalty_wh} Wh")
        with bcols[2]:
            st.metric("+ Payload", f"{b.payload_penalty_wh} Wh")
        with bcols[3]:
            st.metric("Total", f"{b.total_consumption_wh} Wh ({b.consumption_pct:.0f}%)")

        # Liquid breakdown
        st.markdown("**Liquid Model**")
        lq = dt.liquid
        lcols = st.columns(4)
        with lcols[0]:
            st.metric("Needed", f"{lq.total_liquid_needed_l} L")
        with lcols[1]:
            st.metric("Loads", str(lq.loads_needed))
        with lcols[2]:
            st.metric("Refills", str(len(lq.refill_events)))
        with lcols[3]:
            st.metric("Refill Time", f"{lq.total_refill_time_min} min")

        # Event list
        st.markdown("**Event Log**")
        event_rows = []
        for ev in dt.events:
            event_rows.append({
                "Time": ev.timestamp_formatted,
                "Type": EVENT_LABELS.get(ev.event_type, ev.event_type),
                "Description": ev.description,
                "Duration": f"{ev.duration_min:.1f} min" if ev.duration_min > 0 else "-",
            })
        st.dataframe(event_rows, use_container_width=True, hide_index=True)
