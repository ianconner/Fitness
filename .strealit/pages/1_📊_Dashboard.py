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
    st.warning("No logs yet.")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)
valid_df = df[df['distance'] > 0].copy()
valid_df['cum_miles'] = valid_df['distance'].cumsum()

# ——— GOAL SETTINGS ———
st.sidebar.markdown("## Goal Settings")
goal_run_min = st.sidebar.number_input("2-Mile Target (min)", value=18.0, step=0.1)
goal_date = st.sidebar.date_input("Target Date", value=datetime(2026, 6, 1).date())
goal_push = st.sidebar.number_input("Push-ups", value=45, step=1)
goal_crunch = st.sidebar.number_input("Crunches", value=45, step=1)
if st.sidebar.button("Save Goals"):
    st.session_state.goal_run_min = goal_run_min
    st.session_state.goal_date = goal_date
    st.session_state.goal_push = goal_push
    st.session_state.goal_crunch = goal_crunch
    st.success("Goals saved!")

GOAL_RUN_MIN = st.session_state.get("goal_run_min", 18.0)
GOAL_DATE = st.session_state.get("goal_date", datetime(2026, 6, 1).date())
GOAL_PUSH = st.session_state.get("goal_push", 45)
GOAL_CRUNCH = st.session_state.get("goal_crunch", 45)

# ——— PROJECTIONS ———
last_5 = valid_df.head(5)
avg_pace = last_5['pace_min_per_mi'].mean() if not last_5.empty else pd.NA
projected_2mi_min = avg_pace * 2 if pd.notna(avg_pace) else pd.NA
projected_str = f"{int(projected_2mi_min):02d}:{int((projected_2mi_min % 1)*60):02d}" if pd.notna(projected_2mi_min) else "N/A"

st.title("Progress Dashboard")

col1, col2, col3 = st.columns(3)
with col1:
    progress_val = max(0, min(1, (20 - projected_2mi_min) / (20 - GOAL_RUN_MIN))) if pd.notna(projected_2mi_min) else 0
    st.metric("Projected 2-Mile", projected_str, f"Last {len(last_5)}: {avg_pace:.2f} min/mi")
    if projected_2mi_min <= GOAL_RUN_MIN:
        st.markdown("<div style='background-color:#4CAF50;height:8px;'></div>", unsafe_allow_html=True)
    elif projected_2mi_min <= 20:
        st.markdown("<div style='background-color:#FFC107;height:8px;'></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='background-color:#F44336;height:8px;'></div>", unsafe_allow_html=True)

with col2:
    latest_p = df['pushups'].iloc[-1]
    st.metric("Push-ups", latest_p, f"{GOAL_PUSH - latest_p} to goal")

with col3:
    latest_c = df['crunches'].iloc[-1]
    st.metric("Crunches", latest_c, f"{GOAL_CRUNCH - latest_c} to goal")

# Trends
st.markdown("---")
st.subheader("Trends")
colA, colB = st.columns(2)
with colA:
    st.metric("Total Miles", f"{valid_df['cum_miles'].iloc[-1]:.1f}")
with colB:
    days_to_goal = (GOAL_DATE - datetime.today().date()).days
    st.metric("Days to Goal", f"{days_to_goal}")

tab1, tab2, tab3 = st.tabs(["Pace", "Push-ups", "Crunches"])
with tab1:
    fig = px.line(valid_df, x='date', y='pace_min_per_mi', title="Pace Trend")
    fig.add_hline(y=GOAL_RUN_MIN/2, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)
