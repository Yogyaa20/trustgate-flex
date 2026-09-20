import streamlit as st
import pandas as pd
import plotly.express as px
from utils import inject_global_css, render_sidebar, api_get, api_post, format_timestamp, time_ago

st.set_page_config(page_title="Dashboard", page_icon="🔐", layout="wide")
inject_global_css()
render_sidebar()

st.title("Dashboard")
st.caption("Real-time access event overview")
st.divider()

try:
    requests_data = api_get("/api/v1/access/requests")
    alerts_data = api_get("/api/v1/alerts?acknowledged=false")
    
    if st.session_state.get("user_role") in ["ADMIN", "MANAGER"]:
        approvals_data = api_get("/api/v1/approvals/pending")
        pending_approvals = approvals_data.get("total", 0)
    else:
        pending_approvals = "N/A"
    
    total_requests = requests_data.get("total", 0)
    alerts_count = alerts_data.get("total", 0)
    
    events = requests_data.get("requests", [])
    blocks = sum(1 for e in events if e.get("decision") in ["BLOCK_AND_ALERT", "RATE_LIMIT_AND_ALERT"])
    block_rate = f"{(blocks / total_requests * 100):.1f}%" if total_requests > 0 else "0%"

    # Row 1 - 4 Metric cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Today's Requests", total_requests)
    with col2:
        st.metric("Active Alerts", alerts_count)
    with col3:
        st.metric("Pending Approvals", pending_approvals)
    with col4:
        st.metric("Block Rate", block_rate)

    st.write("") # spacer

    # Row 2 - Two columns
    col_left, col_right = st.columns([0.6, 0.4])
    
    with col_left:
        st.subheader("Recent Access Decisions")
        if not events:
            st.info("No recent access events")
        else:
            table_data = []
            for ev in events[:10]:
                table_data.append({
                    "Time": format_timestamp(ev.get("timestamp", "")),
                    "User": ev.get("user_name", ""),
                    "Asset": ev.get("asset_name", ""),
                    "Risk Score": ev.get("risk_score", ""),
                    "Decision": ev.get("decision", ""),
                    "Policy": ev.get("policy_applied", "")
                })
            df = pd.DataFrame(table_data)
            st.dataframe(df, hide_index=True, use_container_width=True)

    with col_right:
        st.subheader("Decision Breakdown")
        if not events:
            st.info("No data for breakdown")
        else:
            decision_counts = {}
            for ev in events:
                d = ev.get("decision", "UNKNOWN")
                decision_counts[d] = decision_counts.get(d, 0) + 1
            
            df_chart = pd.DataFrame(list(decision_counts.items()), columns=["Decision", "Count"])
            
            color_map = {
                "ALLOW": "#2ea043",
                "ALLOW_WITH_MONITOR": "#1f6feb",
                "STEP_UP_AUTH": "#d29922",
                "MANAGER_APPROVAL": "#d29922",
                "RATE_LIMIT_AND_ALERT": "#f0883e",
                "BLOCK_AND_ALERT": "#f85149"
            }
            
            fig = px.bar(
                df_chart, 
                x="Decision", 
                y="Count", 
                color="Decision",
                color_discrete_map=color_map
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#e6edf3",
                showlegend=False,
                margin=dict(l=0, r=0, t=0, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)

    st.write("") # spacer

    # Row 3
    st.subheader("Active Alerts")
    active_alerts = alerts_data.get("alerts", [])
    if not active_alerts:
        st.info("No active alerts")
    else:
        for al in active_alerts:
            with st.container(border=True):
                col_al1, col_al2, col_al3, col_al4 = st.columns([1, 4, 2, 2])
                with col_al1:
                    st.write(al.get("severity", ""))
                with col_al2:
                    st.write(al.get("message", ""))
                with col_al3:
                    st.write(al.get("sent_at", "").split("T")[1][:8] if "T" in al.get("sent_at", "") else "")
                with col_al4:
                    if st.button("Acknowledge", key=f"ack_{al['id']}"):
                        from utils import api_post
                        api_post(f"/api/v1/alerts/{al['id']}/acknowledge", {})
                        st.rerun()

except Exception as e:
    st.error(f"Failed to load dashboard data: {e}")

st.divider()
st.subheader("Insider Threat Simulation")
st.caption("Demonstrate real-time offboarding protection")

sim_col1, sim_col2 = st.columns(2)

with sim_col1:
    st.markdown("**Offboard Employee**")
    try:
        all_users = api_get("/api/v1/users")
        active_users = [u for u in all_users if u["status"] == "ACTIVE" and u["role"] != "ADMIN"]
        if active_users:
            selected_user = st.selectbox(
                "Select employee to offboard",
                [u["id"] for u in active_users],
                format_func=lambda x: next((f"{u['name']} ({u['role']})" for u in active_users if u["id"] == x), x)
            )
            if st.button("Revoke Access", type="primary"):
                result = api_post(f"/api/v1/users/{selected_user}/revoke", {})
                st.session_state["revoked_user_id"] = selected_user
                st.session_state["revoked_user_name"] = result.get("user_name")
                st.success(f"{result.get('user_name')}'s access has been revoked. Next request will be hard-blocked by P01.")
                st.rerun()
    except Exception as e:
        st.error(f"Could not load users: {e}")

with sim_col2:
    st.markdown("**Post-Offboarding Request Simulation**")
    if st.session_state.get("revoked_user_id"):
        st.warning(f"{st.session_state.get('revoked_user_name')} is now REVOKED")
        st.caption("Any access attempt will be hard-blocked by policy P01")
        st.markdown("**P01:** User account revoked → BLOCK_AND_ALERT → FILE_OPERATION_DENIED")
        st.markdown("This fires before any risk scoring — status check is always first.")
    else:
        st.info("Revoke a user on the left to see P01 in action")
