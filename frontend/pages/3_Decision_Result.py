import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from utils import inject_global_css, render_sidebar

st.set_page_config(page_title="Access Decision", page_icon="🔐", layout="wide")
inject_global_css()
render_sidebar()

st.title("Access Decision")

result = st.session_state.get("last_decision")
if not result:
    st.info("No decision to display. Make an access request first.")
    st.page_link("pages/2_Access_Request.py", label="Make a request")
    st.stop()

# Decision banner
decision = result.get("decision", "UNKNOWN")
action = result.get("enforcement_action", "UNKNOWN")

color_map = {
    "ALLOW": "#2ea043",
    "ALLOW_WITH_MONITOR": "#1f6feb",
    "STEP_UP_AUTH": "#d29922",
    "MANAGER_APPROVAL": "#d29922",
    "RATE_LIMIT_AND_ALERT": "#f0883e",
    "BLOCK_AND_ALERT": "#f85149"
}
bg_color = color_map.get(decision, "#30363d")

st.markdown(
    f"""
    <div style='background-color: {bg_color}; padding: 16px; border-radius: 4px; margin-bottom: 24px;'>
        <span style='color: #ffffff; font-size: 20px; font-weight: bold;'>
            {decision} — {action}
        </span>
    </div>
    """, 
    unsafe_allow_html=True
)

col1, col2 = st.columns(2)

risk_score = result.get("risk_score", 0)

with col1:
    st.subheader("Risk Score")
    
    # Plotly gauge chart
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = risk_score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        gauge = {
            'axis': {'range': [0, 100]},
            'bar': {'color': "rgba(0,0,0,0)"},
            'steps': [
                {'range': [0, 30], 'color': "#2ea043"},
                {'range': [30, 50], 'color': "#d29922"},
                {'range': [50, 70], 'color': "#f0883e"},
                {'range': [70, 100], 'color': "#f85149"}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': risk_score
            }
        }
    ))
    fig_gauge.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e6edf3",
        margin=dict(l=20, r=20, t=30, b=20),
        height=250
    )
    st.plotly_chart(fig_gauge, use_container_width=True)
    
    st.metric("Score", risk_score, delta=None)
    st.caption(f"Category: {result.get('risk_category')}")
    st.caption(f"Policy applied: {result.get('policy_applied')}")
    st.caption(f"Decided in {result.get('latency_ms')}ms")

with col2:
    st.subheader("Risk Factor Breakdown")
    factors = result.get("factors", [])
    
    if factors:
        df_factors = pd.DataFrame(factors)
        df_factors = df_factors.sort_values("contribution", ascending=True)
        
        fig_bar = px.bar(
            df_factors,
            x="contribution",
            y="name",
            orientation='h',
        )
        fig_bar.update_traces(marker_color="#1f6feb")
        fig_bar.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e6edf3",
            margin=dict(l=0, r=0, t=0, b=0),
            height=300
        )
        fig_bar.update_xaxes(range=[0, 20])
        st.plotly_chart(fig_bar, use_container_width=True)
    
    st.info(result.get("explanation", "No explanation provided."))

if result.get("requires_approval"):
    st.warning("This request requires manager approval before access is granted.")
    st.caption(f"Approval ID: {result.get('approval_id')}")

st.divider()
c1, c2 = st.columns(2)
with c1:
    if st.button("View Full Replay"):
        st.session_state["replay_request_id"] = result.get("request_id")
        st.switch_page("pages/4_Decision_Replay.py")
with c2:
    if st.button("New Request"):
        st.switch_page("pages/2_Access_Request.py")
