import streamlit as st
import requests

BACKEND_URL = "https://trustgate-flex-production.up.railway.app"

def inject_global_css():
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

def render_sidebar():
    if "token" not in st.session_state:
        st.error("Please log in first.")
        st.page_link("app.py", label="Go to Login")
        st.stop()
        
    st.sidebar.markdown(f"**Logged in as:** {st.session_state.get('user_name')}")
    st.sidebar.markdown(f"**Role:** {st.session_state.get('user_role')}")
    st.sidebar.divider()
    st.sidebar.page_link("pages/1_Dashboard.py", label="Dashboard")
    st.sidebar.page_link("pages/2_Access_Request.py", label="Request Access")
    st.sidebar.page_link("pages/3_Decision_Result.py", label="Decision Result")
    st.sidebar.page_link("pages/4_Decision_Replay.py", label="Decision Replay")
    st.sidebar.page_link("pages/5_Manager_Approval.py", label="Approval Queue")
    st.sidebar.page_link("pages/6_Policy_Simulator.py", label="Policy Simulator")
    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("app.py")

def api_get(endpoint: str):
    headers = {"Authorization": f"Bearer {st.session_state.get('token')}"}
    res = requests.get(f"{BACKEND_URL}{endpoint}", headers=headers)
    res.raise_for_status()
    return res.json()

def api_post(endpoint: str, json_data: dict):
    headers = {"Authorization": f"Bearer {st.session_state.get('token')}"}
    res = requests.post(f"{BACKEND_URL}{endpoint}", headers=headers, json=json_data)
    res.raise_for_status()
    return res.json()

from datetime import datetime, timezone, timedelta

def format_timestamp(ts_str: str) -> str:
    """Format ISO timestamp to human-readable."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        today = now.date()
        yesterday = today - timedelta(days=1)
        dt_date = dt.date() if dt.tzinfo else dt.replace(tzinfo=timezone.utc).date()
        time_part = dt.strftime("%I:%M %p").lstrip("0")
        if dt_date == today:
            return f"Today {time_part}"
        elif dt_date == yesterday:
            return f"Yesterday {time_part}"
        else:
            return dt.strftime("%d %b ") + time_part
    except:
        return ts_str[:16] if ts_str else ""

def time_ago(ts_str: str) -> str:
    """Return relative time string."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        minutes = int(diff.total_seconds() / 60)
        if minutes < 1:
            return "just now"
        elif minutes < 60:
            return f"{minutes} min ago"
        elif minutes < 1440:
            return f"{int(minutes/60)} hours ago"
        else:
            return f"{int(minutes/1440)} days ago"
    except:
        return ts_str[:16] if ts_str else ""
