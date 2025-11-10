# pages/03_Admin.py
import streamlit as st
import psycopg2
import pandas as pd

# ——— PAGE CONFIG ———
st.set_page_config(
    page_title="Admin - SOPHIA",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ——— HIDE AUTO NAV ———
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none !important;}
    .block-container {padding-top: 2rem !important;}
</style>
""", unsafe_allow_html=True)

# ——— LOGIN CHECK ———
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.error("Please log in from the home page.")
    st.stop()

# ——— ADMIN CHECK ———
if st.session_state.role != 'admin':
    st.error("Access denied. Admin only.")
    st.stop()

# ——— SIDEBAR NAV ———
st.sidebar.success(f"**{st.session_state.username}**")
st.sidebar.page_link("app.py", label="Home")
st.sidebar.page_link("pages/01_Dashboard.py", label="Dashboard")
st.sidebar.page_link("pages/02_Log_run.py", label="Log Run")
st.sidebar.page_link("pages/04_Coach.py", label="Coach")
if st.session_state.role == 'admin':
    st.sidebar.page_link("pages/03_Admin.py", label="Admin")
if st.sidebar.button("Logout", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ——— DB ———
def get_db_connection():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— ADMIN PANEL ———
st.title("Admin Panel")

conn = get_db_connection()

# View all users
st.subheader("User Accounts")
users_df = pd.read_sql_query("SELECT id, username, created_at, role FROM users", conn)
st.dataframe(users_df)

# Traffic stats
st.subheader("Traffic and Usage Stats")
total_users = len(users_df)
st.write(f"Total Users: {total_users}")

active_users = pd.read_sql_query("SELECT COUNT(DISTINCT user_id) as active FROM logs", conn)['active'][0]
st.write(f"Active Users (with at least one log): {active_users}")

total_logs = pd.read_sql_query("SELECT COUNT(*) as total FROM logs", conn)['total'][0]
st.write(f"Total Runs Logged: {total_logs}")

# Logs per user
st.subheader("Logs Per User")
logs_per_user = pd.read_sql_query("""
    SELECT u.username, COUNT(l.id) as log_count
    FROM users u LEFT JOIN logs l ON u.id = l.user_id
    GROUP BY u.username
""", conn)
st.dataframe(logs_per_user)

conn.close()
