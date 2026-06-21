"""
EEA Swarm Mission Planner - Reusable UI Components
"""

import streamlit as st


def metric_card(label: str, value: str, delta: str = "", color: str = "normal"):
    color_map = {
        "normal": "#262730",
        "good": "#0e6e1e",
        "warning": "#8a6d00",
        "danger": "#b3261e",
    }
    bg = color_map.get(color, color_map["normal"])
    st.markdown(
        f"""
        <div style="
            background: {bg}22;
            border-left: 4px solid {bg};
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 8px;
        ">
            <div style="font-size: 0.8rem; color: #888; text-transform: uppercase;
                         letter-spacing: 0.5px;">{label}</div>
            <div style="font-size: 1.5rem; font-weight: 700; margin: 4px 0;">{value}</div>
            {'<div style="font-size: 0.75rem; color: #aaa;">' + delta + '</div>' if delta else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def risk_badge(level: str) -> str:
    colors = {
        "Minimal": "#4caf50",
        "Low": "#8bc34a",
        "Medium": "#ff9800",
        "High": "#f44336",
        "Critical": "#b71c1c",
    }
    bg = colors.get(level, "#666")
    return (
        f'<span style="background:{bg}; color:white; padding:3px 10px; '
        f'border-radius:12px; font-size:0.8rem; font-weight:600;">'
        f'{level}</span>'
    )


def section_header(title: str, icon: str = ""):
    st.markdown(
        f"### {icon} {title}" if icon else f"### {title}",
    )
    st.markdown("---")


def status_indicator(status: str) -> str:
    indicators = {
        "GO": '<span style="color:#4caf50; font-weight:700; font-size:1.2rem;">GO</span>',
        "GO WITH CAUTION": '<span style="color:#ff9800; font-weight:700; font-size:1.2rem;">GO WITH CAUTION</span>',
        "NO-GO": '<span style="color:#f44336; font-weight:700; font-size:1.2rem;">NO-GO</span>',
    }
    return indicators.get(
        status,
        f'<span style="color:#ff9800; font-weight:700; font-size:1.2rem;">{status}</span>',
    )
