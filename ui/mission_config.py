"""
Mission Configuration Panel
"""

import streamlit as st

from config.settings import CROP_PROFILES


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
    field_size = st.sidebar.number_input(
        "Field Size (hectares)",
        min_value=0.1, max_value=10000.0, value=50.0, step=5.0,
        help="Total area to be covered by the drone swarm",
    )

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

    return {
        "field_size_ha": field_size,
        "crop_type": crop_type,
        "num_drones": num_drones,
        "battery_capacity_mah": battery_capacity,
        "liquid_capacity_l": liquid_capacity,
        "temperature_c": temperature,
        "wind_speed_kmh": wind_speed,
    }
