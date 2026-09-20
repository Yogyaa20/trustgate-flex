import streamlit as st
import time
from utils import inject_global_css, render_sidebar, api_get, api_post

st.set_page_config(page_title="Request File Access", page_icon="🔐", layout="wide")
inject_global_css()
render_sidebar()

st.title("Request File Access")
st.caption("Submit a file access request for risk evaluation")
st.divider()

col1, col2, col3 = st.columns(3)

# Load data
try:
    assets = api_get("/api/v1/assets")
    devices = api_get("/api/v1/devices/my")
except Exception as e:
    st.error(f"Failed to load form data: {e}")
    st.stop()

with col1:
    st.subheader("1. Select Asset")
    
    # Group assets by classification
    classifications = ["RESTRICTED", "CONFIDENTIAL", "INTERNAL", "PUBLIC"]
    selected_asset = st.radio("Asset", [a["id"] for a in assets], format_func=lambda x: next((a["name"] for a in assets if a["id"] == x), x), label_visibility="collapsed")
    
    for cls in classifications:
        cls_assets = [a for a in assets if a["classification"] == cls]
        if cls_assets:
            with st.expander(f"{cls} ({len(cls_assets)} assets)", expanded=True):
                for a in cls_assets:
                    st.markdown(f"**{a['name']}**")
                    st.markdown(f"Classification: <span style='color: #8b949e'>{a['classification']}</span>", unsafe_allow_html=True)
                    st.caption(f"Score: {a['sensitivity_score']} | Project: {a['project_id'][:8]}")
                    if st.button("Select", key=f"sel_ast_{a['id']}"):
                        st.session_state["selected_asset"] = a["id"]

    active_asset_id = st.session_state.get("selected_asset", assets[0]["id"] if assets else None)
    if active_asset_id:
        st.markdown(f"**Selected Asset ID:** `{active_asset_id}`")

with col2:
    st.subheader("2. Select Device")
    if not devices:
        st.warning("No devices registered")
        selected_device = None
    else:
        device_options = []
        for d in devices:
            device_options.append(d["id"])
            
        selected_device = st.radio("Device", device_options, format_func=lambda x: f"{next((d['device_hash'][:8] for d in devices if d['id'] == x), x)}")
        
        d = next((d for d in devices if d["id"] == selected_device), None)
        if d:
            st.write(f"**Device Hash:** `{d['device_hash']}`")
            st.write(f"Managed: {'Yes' if d['is_managed'] else 'No'}")
            st.write("Trust Score")
            st.progress(d["trust_score"] / 100.0)

with col3:
    st.subheader("3. Session Options")
    approved_work_session = st.toggle("Approved work session active")
    request_type = st.selectbox("Request type", ["DOWNLOAD", "READ", "EXPORT"])
    location_hash = st.text_input("Location identifier", value="office-delhi-01", help="Used for location anomaly detection")

st.divider()
if st.button("Submit Access Request", type="primary"):
    if not active_asset_id or not selected_device:
        st.error("Please select an asset and a device")
    else:
        with st.spinner("Evaluating request..."):
            req_body = {
                "asset_id": active_asset_id,
                "device_id": selected_device,
                "session_id": "demo-session-xyz",
                "request_type": request_type,
                "location_hash": location_hash,
                "approved_work_session": approved_work_session
            }
            try:
                res = api_post("/api/v1/access/request", req_body)
                st.session_state["last_decision"] = res
                st.switch_page("pages/3_Decision_Result.py")
            except Exception as e:
                st.error(f"Request failed: {e}")

st.divider()
st.subheader("Demo Scenarios")
st.caption("One-click scenarios for the pitch demo")

dcol1, dcol2 = st.columns(2)

with dcol1:
    if st.button("Demo A — Normal Access", use_container_width=True):
        # Find first INTERNAL asset and first managed device from loaded data
        internal_assets = [a for a in assets if a["classification"] == "INTERNAL"]
        managed_devices = [d for d in devices if d.get("is_managed")]
        if internal_assets and managed_devices:
            with st.spinner("Running Demo A..."):
                result = api_post("/api/v1/access/request", {
                    "asset_id": internal_assets[0]["id"],
                    "device_id": managed_devices[0]["id"],
                    "session_id": "demo-A",
                    "request_type": "DOWNLOAD",
                    "location_hash": "office-delhi-01"
                })
                st.session_state["last_decision"] = result
                st.session_state["last_request_id"] = result.get("request_id")
            score = result.get("risk_score", "?")
            decision = result.get("decision", "?")
            color = "#2ea043" if decision == "ALLOW" else "#f85149"
            st.markdown(f"**Result:** <span style='color:{color}'>{decision}</span> — Risk Score: {score}", unsafe_allow_html=True)
            st.caption(f"Trusted device + assigned project → {result.get('decision', '')}")

    if st.button("Demo C — New Device + Restricted Asset", use_container_width=True):
        restricted_assets = [a for a in assets if a["classification"] == "RESTRICTED"]
        unmanaged_devices = [d for d in devices if not d.get("is_managed")]
        if restricted_assets and unmanaged_devices:
            with st.spinner("Running Demo C..."):
                result = api_post("/api/v1/access/request", {
                    "asset_id": restricted_assets[0]["id"],
                    "device_id": unmanaged_devices[0]["id"],
                    "session_id": "demo-C",
                    "request_type": "DOWNLOAD",
                    "location_hash": "office-delhi-01"
                })
                st.session_state["last_decision"] = result
                st.session_state["last_request_id"] = result.get("request_id")
            score = result.get("risk_score", "?")
            decision = result.get("decision", "?")
            st.markdown(f"**Result:** <span style='color:#d29922'>{decision}</span> — Risk Score: {score}", unsafe_allow_html=True)
            st.caption("Unmanaged device + RESTRICTED asset → MANAGER_APPROVAL")

with dcol2:
    if st.button("Demo B — Night Worker (Fairness Proof)", use_container_width=True):
        internal_assets = [a for a in assets if a["classification"] == "INTERNAL"]
        managed_devices = [d for d in devices if d.get("is_managed")]
        if internal_assets and managed_devices:
            with st.spinner("Running Demo B..."):
                result = api_post("/api/v1/access/request", {
                    "asset_id": internal_assets[0]["id"],
                    "device_id": managed_devices[0]["id"],
                    "session_id": "demo-B",
                    "request_type": "DOWNLOAD",
                    "location_hash": "office-delhi-01"
                })
                st.session_state["last_decision"] = result
            score = result.get("risk_score", "?")
            decision = result.get("decision", "?")
            st.markdown(f"**Result:** <span style='color:#2ea043'>{decision}</span> — Risk Score: {score}", unsafe_allow_html=True)
            st.caption(f"Same request, different time → {result.get('decision', '')}. Night work = zero weight.")

    if st.button("Demo D — Bulk Exfiltration (David Park)", use_container_width=True):
        confidential_assets = [a for a in assets if a["classification"] == "CONFIDENTIAL"]
        if not confidential_assets:
            confidential_assets = assets
        managed_devices = [d for d in devices if d.get("is_managed")]
        if confidential_assets and managed_devices:
            # First reset velocity to get clean demo
            try:
                api_post("/api/v1/access/demo_reset_velocity", {})
            except:
                pass
            with st.spinner("Simulating 20 rapid downloads on CONFIDENTIAL asset..."):
                result = api_post("/api/v1/access/simulate_bulk_download", {
                    "asset_id": confidential_assets[0]["id"],
                    "device_id": managed_devices[0]["id"],
                    "file_count": 20
                })
            throttle_at = result.get("throttle_triggered_at")
            decisions = result.get("decisions", [])
            if throttle_at:
                last = decisions[throttle_at - 1] if decisions else {}
                score = last.get("risk_score", "?")
                dec = last.get("decision", "?")
                st.markdown(f"**Throttled at file {throttle_at} of 20** — Risk Score: <span style='color:#f0883e'>{score}</span> — <span style='color:#f0883e'>{dec}</span>", unsafe_allow_html=True)
                st.caption(f"Download velocity exceeded 2x baseline — P04 fired — download throttled before completion")
            elif decisions:
                last = decisions[-1]
                st.markdown(f"**Final after {len(decisions)} files:** {last.get('decision')} — Score: {last.get('risk_score')}")
                st.caption("Reset demo data from login page if throttle not triggering")
