import streamlit as st
import pandas as pd
from utils import inject_global_css, render_sidebar, api_get, format_timestamp

st.set_page_config(page_title="Decision Replay", page_icon="🔐", layout="wide")
inject_global_css()
render_sidebar()

st.title("Decision Replay")
st.caption("Full audit record for any access decision")
st.divider()

col_nav, col_main = st.columns([0.3, 0.7])

with col_nav:
    try:
        requests_data = api_get("/api/v1/access/requests")
        events = requests_data.get("requests", [])
        
        if not events:
            st.info("No past requests found.")
        else:
            options = {ev["request_id"]: f"[{ev['timestamp'].split('T')[1][:8]}] — {ev['user_name']} — {ev['asset_name']} — {ev['outcome']}" for ev in events}
            
            # Use query parameter or session state to set default
            default_index = 0
            preset_id = st.session_state.get("replay_request_id")
            if preset_id and preset_id in options:
                default_index = list(options.keys()).index(preset_id)
                # clear it so it doesn't stick forever
                st.session_state["replay_request_id"] = None
                
            selected_id = st.selectbox(
                "Select a request",
                list(options.keys()),
                format_func=lambda x: options[x],
                index=default_index
            )
            
            if selected_id:
                replay_data = api_get(f"/api/v1/access/request/{selected_id}/replay")
    except Exception as e:
        st.error(f"Failed to load requests: {e}")
        replay_data = None

if 'replay_data' in locals() and replay_data:
    with col_main:
        # Section 1 - Request Details
        st.subheader("Request")
        r = replay_data.get("request", {})
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**User:** {r.get('user_name', 'Unknown')} ({r.get('user_role', 'Unknown')})")
            
            status = r.get("user_status", "UNKNOWN")
            color = "#2ea043" if status == "ACTIVE" else "#f85149"
            st.markdown(f"**Status:** <span style='color: {color}'>{status}</span>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"**Time:** {format_timestamp(r.get('timestamp', ''))}")
            st.markdown(f"**Request type:** {r.get('request_type', 'UNKNOWN')}")
        
        st.divider()
        
        # Section 2 - Device
        st.subheader("Device")
        ts = r.get("device_trust", 0)
        st.progress(ts / 100.0)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.write(f"**Trust score:** {ts}")
        with c2:
            st.write(f"**Managed:** {r.get('device_managed')}")
        with c3:
            st.markdown(f"**Hash:** `{r.get('device_hash', 'UNKNOWN')}`")
            
        st.divider()
        
        # Section 3 - Asset
        st.subheader("Asset")
        cls = r.get("asset_classification", "UNKNOWN")
        cls_color = "#f85149" if cls == "RESTRICTED" else ("#f0883e" if cls == "CONFIDENTIAL" else ("#1f6feb" if cls == "INTERNAL" else "#8b949e"))
        
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Name:** {r.get('asset_name')}")
            st.markdown(f"**Classification:** <span style='color: {cls_color}'>{cls}</span>", unsafe_allow_html=True)
        with c2:
            st.write(f"**Project:** {r.get('project_name')}")
            st.write(f"**Sensitivity score:** {r.get('sensitivity_score', 'UNKNOWN')}")
            
        st.divider()
        
        # Section 4 - Risk Evaluation
        st.subheader("Risk Evaluation")
        risk = replay_data.get("risk", {})
        st.metric("Risk Score", risk.get("score"))
        st.caption(f"Category: {risk.get('category')}")
        
        factors = risk.get("factors", [])
        if factors:
            df = pd.DataFrame(factors)
            df = df.rename(columns={"name": "Factor", "raw_value": "Raw Value", "weight": "Weight", "contribution": "Contribution"})
            df = df[["Factor", "Raw Value", "Weight", "Contribution"]].sort_values("Contribution", ascending=False)
            st.dataframe(df, hide_index=True, use_container_width=True)
            
        st.divider()
        
        # Section 5 - Policy Decision
        st.subheader("Policy Decision")
        pol = replay_data.get("policy", {})
        outcome = pol.get("outcome", "UNKNOWN")
        out_color = "#2ea043" if outcome == "ALLOW" else "#f85149"
        
        st.write(f"**Policy applied:** {pol.get('policy_applied')}")
        st.markdown(f"**Outcome:** <span style='color: {out_color}'>{outcome}</span>", unsafe_allow_html=True)
        st.write(f"**Reason:** {pol.get('reason')}")
        st.write(f"**Enforcement action:** {pol.get('enforcement_action')}")
        
        st.divider()
        
        # Section 6 - Approval
        appr = replay_data.get("approval")
        if appr:
            st.subheader("Approval Record")
            st.write(f"**Manager:** {appr.get('manager_name')}")
            st.write(f"**Decision:** {appr.get('status')}")
            st.write(f"**Reason:** {appr.get('reason')}")
            st.write(f"**Approved at:** {appr.get('approved_at')}")
            st.write(f"**Expires at:** {appr.get('expires_at')}")
            st.divider()
            
        # Section 7 - Audit Integrity
        st.subheader("Audit Record")
        aud = replay_data.get("audit")
        if aud:
            st.code(aud.get("event_hash"), language=None)
            c1, c2, c3 = st.columns(3)
            with c1:
                st.write(f"**Event ID:** {aud.get('event_id')}")
            with c2:
                st.write(f"**Timestamp:** {aud.get('timestamp')}")
            with c3:
                prev = aud.get("prev_hash")
                st.write(f"**Previous hash:** {prev[:16]}..." if prev else "**Previous hash:** None")
                
            st.write("")
            if st.button("Verify Hash Chain"):
                try:
                    verify_res = api_get("/api/v1/audit/verify")
                    if verify_res.get("valid"):
                        st.success(f"Chain verified — {verify_res.get('events_checked')} events checked")
                    else:
                        st.error(f"Chain broken at: {verify_res.get('broken_at')}")
                except Exception as e:
                    st.error(f"Verification failed: {e}")
