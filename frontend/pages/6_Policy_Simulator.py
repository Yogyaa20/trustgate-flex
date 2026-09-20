"""
TrustGate Flex — Policy Simulator
"""
import streamlit as st
from utils import inject_global_css, render_sidebar, api_post

st.set_page_config(page_title="Policy Simulator", page_icon="🔐", layout="wide")
inject_global_css()
render_sidebar()

st.title("Policy Simulator")
st.caption("Adjust risk signals and see live decisions — no real access is granted")
st.divider()

left, right = st.columns([0.45, 0.55])

with left:
    st.subheader("Risk Signals")
    device_trust = st.slider("Device trust score", 0, 100, 85)
    asset_class = st.selectbox("Asset classification", ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"])
    project_assigned = st.toggle("Project assigned", value=True)
    download_velocity = st.slider("Download velocity (x baseline)", 0.0, 20.0, 1.0, step=0.5)
    location_known = st.toggle("Location known", value=True)
    failed_mfa = st.slider("Failed MFA attempts", 0, 5, 0)
    concurrent_sessions = st.slider("Concurrent sessions", 1, 4, 1)
    user_status = st.selectbox("User status", ["ACTIVE", "SUSPENDED", "REVOKED"])
    approved_session = st.toggle("Approved work session", value=False)
    temp_permission = st.toggle("Temporary permission active", value=False)
    repeat_violations = st.slider("Repeat violations (24h)", 0, 5, 0)
    st.caption("Note: Time of day has zero weight — night work is never penalised")

with right:
    st.subheader("Live Decision")
    try:
        sim_result = api_post("/api/v1/access/simulate_evaluate", {
            "device_trust_score": device_trust,
            "asset_classification": asset_class,
            "project_assigned": project_assigned,
            "download_velocity_ratio": download_velocity,
            "location_known": location_known,
            "failed_mfa_attempts": failed_mfa,
            "concurrent_sessions": concurrent_sessions,
            "user_status": user_status,
            "approved_work_session": approved_session,
            "temporary_permission_active": temp_permission,
            "violations_last_24h": repeat_violations
        })

        score = sim_result.get("risk_score", 0)
        category = sim_result.get("risk_category", "")
        decision = sim_result.get("decision", "")
        policy = sim_result.get("policy_applied", "")
        enforcement = sim_result.get("enforcement_action", "")
        factors = sim_result.get("factors", [])

        # Color the score
        if score < 30:
            score_color = "#2ea043"
        elif score < 50:
            score_color = "#d29922"
        elif score < 70:
            score_color = "#f0883e"
        else:
            score_color = "#f85149"

        decision_colors = {
            "ALLOW": "#2ea043",
            "ALLOW_WITH_MONITOR": "#1f6feb",
            "STEP_UP_AUTH": "#d29922",
            "MANAGER_APPROVAL": "#d29922",
            "RATE_LIMIT_AND_ALERT": "#f0883e",
            "BLOCK_AND_ALERT": "#f85149"
        }
        dec_color = decision_colors.get(decision, "#8b949e")

        st.markdown(f"<h1 style='color:{score_color};font-size:64px;margin:0'>{score}</h1>", unsafe_allow_html=True)
        st.markdown(f"**Category:** {category}")
        st.markdown(f"**Policy fired:** {policy}")
        st.markdown(f"**Decision:** <span style='color:{dec_color};font-weight:bold'>{decision}</span>", unsafe_allow_html=True)
        st.markdown(f"**Enforcement:** {enforcement}")

        st.divider()
        st.subheader("Factor Breakdown")
        if factors:
            import pandas as pd
            df = pd.DataFrame(factors)[["factor_name", "raw_value", "weight", "contribution"]]
            df.columns = ["Factor", "Raw Value", "Weight", "Contribution"]
            df = df.sort_values("Contribution", ascending=False)
            st.dataframe(df, hide_index=True, use_container_width=True)
    except Exception as e:
        st.error(f"Simulator error: {e}")
