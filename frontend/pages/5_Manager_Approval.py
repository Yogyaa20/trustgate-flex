import streamlit as st
from utils import inject_global_css, render_sidebar, api_get, api_post

st.set_page_config(page_title="Approval Queue", page_icon="🔐", layout="wide")
inject_global_css()
render_sidebar()

st.title("Approval Queue")

user_role = st.session_state.get("user_role")
if user_role not in ["ADMIN", "MANAGER"]:
    st.error("Access denied. Manager or Admin role required.")
    st.stop()

try:
    approvals_data = api_get("/api/v1/approvals/pending")
    approvals = approvals_data.get("approvals", [])
except Exception as e:
    st.error(f"Failed to load pending approvals: {e}")
    st.stop()

if not approvals:
    st.success("No pending approvals.")
else:
    st.caption(f"{len(approvals)} request(s) awaiting decision")
    
    for appr in approvals:
        with st.container(border=True):
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            with r1c1:
                st.write(f"**User:** {appr.get('requester_name', 'Unknown')}")
            with r1c2:
                st.write(f"**Asset:** {appr.get('asset_name', 'Unknown')}")
            with r1c3:
                st.write(f"**Risk score:** {appr.get('risk_score', 'N/A')}")
            with r1c4:
                st.write(f"**Waiting since:** {appr.get('expires_at', '').split('T')[1][:8] if 'T' in appr.get('expires_at', '') else appr.get('expires_at')}")
                
            st.write(f"**Reason for escalation:** {appr.get('explanation', 'Unknown Policy')}")
            
            st.write("")
            r3c1, r3c2 = st.columns(2)
            
            with r3c1:
                dur_str = st.selectbox("Duration", ["15 min", "30 min", "1 hour", "4 hours"], key=f"dur_{appr['approval_id']}", label_visibility="collapsed")
                dur_map = {"15 min": 15, "30 min": 30, "1 hour": 60, "4 hours": 240}
                if st.button("Approve", key=f"app_{appr['approval_id']}"):
                    try:
                        api_post(f"/api/v1/approvals/{appr['approval_id']}/decide", {
                            "approved": True,
                            "duration_minutes": dur_map[dur_str]
                        })
                        st.success(f"Access granted for {dur_str}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Approval failed: {e}")
            
            with r3c2:
                reason = st.text_input("Denial reason", key=f"den_rsn_{appr['approval_id']}", label_visibility="collapsed", placeholder="Denial reason")
                if st.button("Deny", key=f"den_{appr['approval_id']}"):
                    try:
                        api_post(f"/api/v1/approvals/{appr['approval_id']}/decide", {
                            "approved": False,
                            "reason": reason if reason else "Manager denied"
                        })
                        st.success("Request denied")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Denial failed: {e}")
