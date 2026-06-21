"""
Risk Dashboard
"""

import streamlit as st
import plotly.graph_objects as go

from core.risk_engine import RiskAssessment
from ui.components import section_header, metric_card, risk_badge


def render_risk_dashboard(risks: RiskAssessment):
    section_header("Risk Assessment", "")

    risk_color = {
        "Minimal": "good", "Low": "good",
        "Medium": "warning", "High": "danger", "Critical": "danger",
    }

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card(
            "Overall Risk",
            risks.overall_risk,
            f"Score: {risks.overall_score:.2f}",
            color=risk_color.get(risks.overall_risk, "normal"),
        )
    with c2:
        viable_color = "good" if risks.mission_viable else "danger"
        metric_card("Mission Viable", "YES" if risks.mission_viable else "NO", color=viable_color)
    with c3:
        if risks.critical_risks:
            metric_card(
                "Critical Risks",
                str(len(risks.critical_risks)),
                ", ".join(risks.critical_risks),
                color="danger",
            )
        else:
            metric_card("Critical Risks", "None", color="good")

    tab_radar, tab_details = st.tabs(["Risk Radar", "Risk Details"])

    with tab_radar:
        _render_risk_radar(risks)

    with tab_details:
        _render_risk_details(risks)


def _render_risk_radar(risks: RiskAssessment):
    categories = [r.category for r in risks.risks]
    scores = [r.score for r in risks.risks]

    categories_closed = categories + [categories[0]]
    scores_closed = scores + [scores[0]]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=scores_closed,
        theta=categories_closed,
        fill="toself",
        fillcolor="rgba(244, 67, 54, 0.2)",
        line=dict(color="#f44336", width=2),
        marker=dict(size=8, color="#f44336"),
        name="Risk Score",
    ))

    fig.add_trace(go.Scatterpolar(
        r=[0.3] * len(categories_closed),
        theta=categories_closed,
        line=dict(color="#4caf50", width=1, dash="dash"),
        name="Low Risk Threshold",
        showlegend=True,
    ))

    fig.add_trace(go.Scatterpolar(
        r=[0.7] * len(categories_closed),
        theta=categories_closed,
        line=dict(color="#ff9800", width=1, dash="dash"),
        name="High Risk Threshold",
        showlegend=True,
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1], tickvals=[0.3, 0.5, 0.7, 1.0]),
            bgcolor="rgba(0,0,0,0)",
        ),
        title="Risk Radar",
        height=450,
        template="plotly_dark",
        margin=dict(l=60, r=60, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_risk_details(risks: RiskAssessment):
    for risk in risks.risks:
        with st.expander(f"{risk.category} — {risk.level}", expanded=risk.level in ("High", "Critical")):
            st.markdown(
                f"**Level:** {risk_badge(risk.level)}&nbsp;&nbsp;"
                f"**Score:** {risk.score:.2f}",
                unsafe_allow_html=True,
            )
            st.markdown(f"**Assessment:** {risk.description}")
            st.markdown(f"**Mitigation:** {risk.mitigation}")
