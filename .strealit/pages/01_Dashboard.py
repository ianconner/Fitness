# pages/01_Dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2
from datetime import datetime

# ——— PAGE CONFIG ———
st.set_page_config(
    page_title="Dashboard - SOPHIA",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ——— HIDE STREAMLIT AUTO NAV ———
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none !important;}
    .block-container {padding-top: 2rem !important;}
</style>
""", unsafe_allow_html=True)

# ——— CHECK LOGIN ———
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.error("Please log in from the home page.")
    st.stop()

# ——— SIDEBAR ———
st.sidebar.success(f"**{st.session_state.username}**")
st.sidebar.page_link("app.py", label="Home")
st.sidebar.page_link("pages/01_Dashboard.py", label="Dashboard")
st.sidebar.page_link("pages/02_AI_Coach.py", label="SOPHIA Coach")
if st.sidebar.button("Logout", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ——— DB ———
def get_db_connection():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT * FROM logs WHERE user_id = %s ORDER BY date",
        conn, params=(st.session_state.user_id,)
    )
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("No logs yet.")
    st.stop()

# ——— PROCESS DATA ———
df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)
valid_df = df[df['distance'] > 0].copy()

# ——— GOALS FROM SESSION STATE ———
GOAL_RUN_MIN = st.session_state.get("goal_run_min", 18.0)
GOAL_PUSH = st.session_state.get("goal_push", 45)
GOAL_CRUNCH = st.session_state.get("goal_crunch", 45)

# ——— TITLE ———
st.markdown("## Progress Dashboard")

# ——— TABS ———
tab1, tab2, tab3 = st.tabs(["Pace", "Push-ups", "Crunches"])

# ——— TAB 1: PACE ———
with tab1:
    fig = px.scatter(valid_df, x='date', y='pace_min_per_mi', title="Pace Trend")
    fig.add_scatter(x=valid_df['date'], y=valid_df['pace_min_per_mi'],
                    mode='lines', line=dict(color='green', width=2), name='Trend')
    avg_pace = valid_df['pace_min_per_mi'].mean()
    fig.add_hline(y=avg_pace, line_dash="solid", line_color="gold", annotation_text=f"Avg: {avg_pace:.2f}")
    goal_pace = GOAL_RUN_MIN / 2
    fig.add_hline(y=goal_pace, line_dash="dash", line_color="red", annotation_text="Goal")
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

# ——— TAB 2: PUSH-UPS ———
with tab2:
    fig = px.scatter(df, x='date', y='pushups', title="Push-ups")
    fig.add_scatter(x=df['date'], y=df['pushups'],
                    mode='lines', line=dict(color='green', width=2), name='Trend')
    avg_push = df['pushups'].mean()
    fig.add_hline(y=avg_push, line_dash="solid", line_color="gold", annotation_text=f"Avg: {avg_push:.0f}")
    fig.add_hline(y=GOAL_PUSH, line_dash="dash", line_color="red", annotation_text="Goal")
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

# ——— TAB 3: CRUNCHES ———
with tab3:
    fig = px.scatter(df, x='date', y='crunches', title="Crunches")
    fig.add_scatter(x=df['date'], y=df['crunches'],
                    mode='lines', line=dict(color='green', width=2), name='Trend')
    avg_crunch = df['crunches'].mean()
    fig.add_hline(y=avg_crunch, line_dash="solid", line_color="gold", annotation_text=f"Avg: {avg_crunch:.0f}")
    fig.add_hline(y=GOAL_CRUNCH, line_dash="dash", line_color="red", annotation_text="Goal")
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(showlegend=True)
    st.plotly_chart(fig, use_container_width=True)
