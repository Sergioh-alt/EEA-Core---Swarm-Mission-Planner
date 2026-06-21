"""
Final Recommendation Panel
"""

import streamlit as st

from core.decision_engine import MissionRecommendation
from core.environment_analyzer import EnvironmentAssessment
from ui.components import section_header, metric_card, status_indicator


def render_recommendation(
    recommendation: MissionRecommendation,
    assessment: EnvironmentAssessment,
):
    section_header("Mission Recommendation", "")

    go_html = status_indicator(recommendation.go_no_go)
    st.markdown(
        f"<div style='text-align:center; margin:10px 0 20px 0;'>"
        f"<span style='font-size:0.9rem; color:#888;'>MISSION DECISION: </span>"
        f"{go_html}</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        feasible_color = "good" if recommendation.feasible else "danger"
        metric_card("Feasible", "YES" if recommendation.feasible else "NO", color=feasible_color)
    with c2:
        conf_color = "good" if recommendation.confidence_pct >= 80 else "warning" if recommendation.confidence_pct >= 60 else "danger"
        metric_card("Confidence", f"{recommendation.confidence_pct:.0f}%", color=conf_color)
    with c3:
        metric_card("Coverage", f"{recommendation.coverage_pct:.0f}%")
    with c4:
        metric_card("Duration", recommendation.estimated_duration)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Operational Notes")
        for note in recommendation.operational_notes:
            st.markdown(f"- {note}")

    with col_right:
        st.markdown("#### Optimization Suggestions")
        if recommendation.optimization_suggestions:
            for sug in recommendation.optimization_suggestions:
                st.markdown(f"- {sug}")
        else:
            st.markdown("_No optimizations needed — configuration is optimal._")

    st.markdown("---")

    st.markdown("#### Mission Summary")
    st.code(recommendation.summary, language="text")

    st.markdown("---")
    st.markdown("#### Environment Assessment")
    env_cols = st.columns(3)
    with env_cols[0]:
        metric_card("Area Category", assessment.area_category)
    with env_cols[1]:
        metric_card("Complexity", assessment.operational_complexity)
    with env_cols[2]:
        cond_color = "good" if assessment.flight_conditions == "Clear" else "warning" if assessment.flight_conditions in ("Caution", "Restricted") else "danger"
        metric_card("Flight Conditions", assessment.flight_conditions, color=cond_color)

    st.markdown(
        f"<div style='padding:10px; background:#1e1e2e; border-radius:6px; "
        f"font-size:0.85rem; margin-top:8px;'>"
        f"<strong>Weather:</strong> {assessment.weather_details}<br/>"
        f"<strong>Recommended Speed:</strong> {assessment.recommended_speed_kmh} km/h<br/>"
        f"<strong>Effective Spray Width:</strong> {assessment.effective_spray_width_m} m"
        f"</div>",
        unsafe_allow_html=True,
    )
