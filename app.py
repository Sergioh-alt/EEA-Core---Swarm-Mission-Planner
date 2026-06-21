"""
EEA Swarm Mission Planner
=========================
Decision-support platform for autonomous agricultural drone swarm coordination.
Part of the EEA Core ecosystem.

Run: streamlit run app.py
"""

import streamlit as st

from config.settings import app_config
from core.mission_intake import create_mission_profile
from core.environment_analyzer import analyze_environment
from core.swarm_planner import plan_swarm
from core.route_planner import plan_routes
from core.resource_planner import plan_resources
from core.risk_engine import evaluate_risks
from core.decision_engine import generate_recommendation
from ui.mission_config import render_mission_config
from ui.swarm_view import render_swarm_view
from ui.resource_dashboard import render_resource_dashboard
from ui.risk_dashboard import render_risk_dashboard
from ui.recommendation_panel import render_recommendation
from utils.logger import get_logger

logger = get_logger("app")

st.set_page_config(
    page_title="EEA Swarm Mission Planner",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container { padding-top: 1rem; }
        [data-testid="stSidebar"] { min-width: 320px; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 20px;
            border-radius: 6px 6px 0 0;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def main():
    params = render_mission_config()

    st.markdown(
        """
        <div style="text-align:center; margin-bottom:20px;">
            <h1 style="margin-bottom:0; font-weight:800; letter-spacing:1px;">
                EEA Swarm Mission Planner
            </h1>
            <p style="color:#888; font-size:0.9rem; margin-top:4px;">
                Autonomous Planning Layer &mdash; EEA Core v{version}
            </p>
        </div>
        """.format(version=app_config.version),
        unsafe_allow_html=True,
    )

    profile = create_mission_profile(**params)

    if not profile.validation.valid:
        st.error("Mission configuration has errors:")
        for err in profile.validation.errors:
            st.error(f"  {err}")
        st.stop()

    if profile.validation.warnings:
        for w in profile.validation.warnings:
            st.warning(w)

    assessment = analyze_environment(profile)
    swarm = plan_swarm(profile, assessment)
    routes = plan_routes(swarm, assessment)
    resources = plan_resources(profile, routes)
    risks = evaluate_risks(profile, assessment, resources, routes)
    rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)

    tab_rec, tab_swarm, tab_resources, tab_risks = st.tabs([
        "Recommendation",
        "Swarm Planning",
        "Resources",
        "Risk Assessment",
    ])

    with tab_rec:
        render_recommendation(rec, assessment)

    with tab_swarm:
        render_swarm_view(swarm, routes)

    with tab_resources:
        render_resource_dashboard(resources, profile)

    with tab_risks:
        render_risk_dashboard(risks)

    st.markdown(
        """
        <div style="text-align:center; padding:20px 0 10px 0; color:#555; font-size:0.75rem;">
            EEA Swarm Mission Planner v{version} &mdash; Part of the EEA Core Ecosystem<br/>
            Cognitive Operating System for Autonomous Decision Systems
        </div>
        """.format(version=app_config.version),
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
