# pages/1_📊_Dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2
from datetime import datetime

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
    st.warning("No logs yet – log a session!")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)
valid_df = df[df['distance'] > 0].copy()

# ——— GOAL SETTINGS (Sidebar) ———
st.sidebar.markdown("## Goal Settings")
col_g1, col_g2 = st.sidebar.columns(2)
with col_g1:
    goal_run_min = st.number_input("2-Mile Target (min)", min_value=10.0, max_value=30.0, value=18.0, step=0.1)
with col_g2:
    goal_date = st.date_input("Target Date", value=datetime(2026, 6, 1).date())

goal_push = st.number_input("Push-ups", min_value=20, max_value=100, value=45, step=1)
goal_crunch = st.number_input("Crunches", min_value=20, max_value=100, value=45, step=1)

if st.sidebar.button("Save Goals"):
    st.session_state.goal_run_min = goal_run_min
    st.session_state.goal_date = goal_date
    st.session_state.goal_push = goal_push
    st.session_state.goal_crunch = goal_crunch
    st.success("Goals saved!")

# Load saved
GOAL_RUN_MIN = st.session_state.get("goal_run_min", goal_run_min)
GOAL_DATE = st.session_state.get("goal_date", goal_date)
GOAL_PUSH = st.session_state.get("goal_push", goal_push)
GOAL_CRUNCH = st.session_state.get("goal_crunch", goal_crunch)

# ——— PROJECTIONS ———
last_5 = valid_df.head(5)
avg_pace = last_5['pace_min_per_mi'].mean()
projected_2mi = avg_pace * 2
projected_str = f"{int(projected_2mi):02d}:{int((projected_2mi % 1)*60):02d}"

# ——— DASHBOARD ———
st.title("USAF PT Dashboard")

col1, col2, col3 = st.columns(3)
with col1:
    progress_val = max(0, min(1, (20 - projected_2mi) / (20 - GOAL_RUN_MIN)))
    st.metric("Projected 2-Mile", projected_str, f"Last 5: {avg_pace:.2f} min/mi")
    if projected_2mi <= GOAL_RUN_MIN:
        st.markdown("<div style='background-color:#4CAF50;height:8px;border-radius:4px;'></div>", unsafe_allow_html=True)
    elif projected_2mi <= 20:
        st.markdown("<div style='background-color:#FFC107;height:8px;border-radius:4px;'></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='background-color:#F44336;height:8px;border-radius:4px;'></div>", unsafe_allow_html=True)

with col2:
    latest_p = df['pushups'].iloc[-1]
    color_p = "#4CAF50" if latest_p >= GOAL_PUSH else "#FFC107" if latest_p >= GOAL_PUSH*0.8 else "#F44336"
    st.metric("Push-ups", latest_p, f"{GOAL_PUSH - latest_p} to goal")
    st.markdown(f"<div style='background-color:{color_p};height:8px;border-radius:4px;'></div>", unsafe_allow_html=True)

with col3:
    latest_c = df['crunches'].iloc[-1]
    color_c = "#4CAF50" if latest_c >= GOAL_CRUNCH else "#FFC107" if latest_c >= GOAL_CRUNCH*0.8 else "#F44336"
    st.metric("Crunches", latest_c, f"{GOAL_CRUNCH - latest_c} to goal")
    st.markdown(f"<div style='background-color:{color_c};height:8px;border-radius:4px;'></div>", unsafe_allow_html=True)

# ——— TRENDS ———
st.markdown("---")
st.subheader("Performance Trends")
colA, colB = st.columns(2)
with colA:
    st.metric("Total Miles", f"{valid_df['distance'].sum():.1f}")
with colB:
    st.metric("Days to Goal", f"{(GOAL_DATE - datetime.today().date()).days}")

tab1, tab2, tab3 = st.tabs(["Pace", "Push-ups", "Crunches"])
with tab1:
    valid_df['rolling'] = valid_df['pace_min_per_mi'].rolling(5, min_periods=1).mean()
    fig = px.line(valid_df, x='date', y=['pace_min_per_mi', 'rolling'], title="Pace Trend")
    fig.add_hline(y=GOAL_RUN_MIN/2, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)
