import streamlit as st
import requests

# Page Config
st.set_page_config(page_title="TrustGate Flex", page_icon="🔐", layout="wide")

# Global CSS Injection
st.markdown("""
<style>
.stApp { background-color: #0d1117; color: #e6edf3; }
.stSidebar { background-color: #161b22; border-right: 1px solid #30363d; }
.stButton>button {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 14px;
}
.stButton>button:hover { background-color: #30363d; border-color: #8b949e; }
div[data-testid="metric-container"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 12px;
}
.stDataFrame { background-color: #161b22; }
hr { border-color: #30363d; }
</style>
""", unsafe_allow_html=True)

BACKEND_URL = "https://trustgate-flex-production.up.railway.app"


def handle_login(email: str):
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={"username": email, "password": "demo123"}
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state["token"] = data["access_token"]
            st.session_state["user_id"] = data["user"]["id"]
            st.session_state["user_name"] = data["user"]["name"]
            st.session_state["user_role"] = data["user"]["role"]
            st.session_state["user_email"] = data["user"]["email"]
            st.switch_page("pages/1_Dashboard.py")
        else:
            st.error(f"Login failed: {response.text}")
    except Exception as e:
        st.error(f"Error connecting to backend: {e}")


# Two columns: left 60% has login, right 40% has system status
col1, col2 = st.columns([0.6, 0.4])

with col1:
    st.title("TrustGate Flex")
    st.caption("Access Gateway — BuildForge Hackathon Demo")
    st.divider()
    st.subheader("Select a demo account")
    st.caption("All accounts use password: demo123")

    personas = [
        {"name": "Alice Chen", "role": "Senior Engineer", "email": "alice@trustgate.com"},
        {"name": "Bob Martinez", "role": "Admin / Manager", "email": "bob@trustgate.com"},
        {"name": "David Park", "role": "Engineer", "email": "david@trustgate.com"},
        {"name": "Admin User", "role": "Administrator", "email": "admin@trustgate.com"},
    ]

    for p in personas:
        with st.container(border=True):
            st.markdown(f"**{p['name']}**")
            st.markdown(f"<span style='color: #8b949e'>{p['role']}</span>", unsafe_allow_html=True)
            st.markdown(f"`{p['email']}`")
            if st.button("Sign in", key=f"login_{p['email']}"):
                handle_login(p['email'])

    st.divider()
    st.caption("Demo controls")
    rc1, rc2 = st.columns(2)
    with rc1:
        if st.button("Reset Demo Data"):
            try:
                from utils import api_post
                result = requests.post("https://trustgate-flex-production.up.railway.app/demo/reset")
                st.success("Demo data reset — fresh state loaded")
            except Exception as e:
                st.error(f"Reset failed: {e}")
    with rc2:
        st.markdown("[API Documentation](https://trustgate-flex-production.up.railway.app/docs)")

with col2:
    st.subheader("System Status")
    
    try:
        health_res = requests.get(f"{BACKEND_URL}/health")
        if health_res.status_code == 200:
            st.success("Backend online")
        else:
            st.error("Backend offline (Bad status code)")
            
        debug_res = requests.get(f"{BACKEND_URL}/debug/status")
        if debug_res.status_code == 200:
            data = debug_res.json()
            st.write("Database: ", data.get("database_connection"))
            
            st.markdown("**Table Row Counts**")
            tables = data.get("table_counts", {})
            import pandas as pd
            df = pd.DataFrame(list(tables.items()), columns=["Table", "Rows"])
            st.dataframe(df, hide_index=True, use_container_width=True)
    except Exception as e:
        st.error(f"Backend offline: {e}")
