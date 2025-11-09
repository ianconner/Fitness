import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# DB Connection
def get_db_connection():
    url = st.secrets.get("POSTGRES_URL") or os.getenv("POSTGRES_URL")
    if not url:
        st.error("Missing POSTGRES_URL!")
        st.stop()
    return psycopg2.connect(url)

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM logs ORDER BY date", conn)
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("No logs yet – log a session!")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)

# Filter valid runs
valid_df = df[df['distance'] > 0].copy()
valid_df['cum_miles'] = valid_df['distance'].cumsum()

# === GOAL MANAGEMENT (Editable on Dashboard) ===
st.sidebar.markdown("## Goal Settings")
col_g1, col_g2 = st.sidebar.columns(2)
with col_g1:
    goal_run_min = st.number_input("2-Mile Target (min)", min_value=10.0, max_value=30.0, value=18.0, step=0.5)
with col_g2:
    goal_push = st.number_input("Push-ups", min_value=20, max_value=100, value=45, step=1)
    goal_crunch = st.number_input("Crunches", min_value=20, max_value=100, value=45, step=1)

# Save goals to session state (persists across pages)
if st.sidebar.button("Save Goals"):
    st.session_state.goal_run_min = goal_run_min
    st.session_state.goal_push = goal_push
    st.session_state.goal_crunch = goal_crunch
    st.success("Goals saved!")

# Load saved goals
GOAL_RUN_MIN = st.session_state.get("goal_run_min", goal_run_min)
GOAL_PUSH = st.session_state.get("goal_push", goal_push)
GOAL_CRUNCH = st.session_state.get("goal_crunch", goal_crunch)

# === PROJECTIONS ===
last_n = valid_df.head(5)
avg_pace = last_n['pace_min_per_mi'].mean() if not last_n.empty else pd.NA
projected_2mi_min = avg_pace * 2 if pd.notna(avg_pace) else pd.NA
projected_str = f"{int(projected_2mi_min):02d}:{int((projected_2mi_min % 1)*60):02d}" if pd.notna(projected_2mi_min) else "N/A"

st.title("USAF PT Dashboard")

# === METRICS WITH RED/YELLOW/GREEN ===
col1, col2, col3 = st.columns(3)

with col1:
    if pd.notna(projected_2mi_min):
        progress_val = max(0, min(1, (20 - projected_2mi_min) / (20 - GOAL_RUN_MIN)))
        st.metric("Projected 2-Mile", projected_str, f"Last {len(last_n)}: {avg_pace:.2f} min/mi")
        if projected_2mi_min <= GOAL_RUN_MIN:
            st.markdown("<div style='background-color:#4CAF50;height:8px;border-radius:4px;'></div>", unsafe_allow_html=True)
        elif projected_2mi_min <= 20:
            st.markdown("<div style='background-color:#FFC107;height:8px;border-radius:4px;'></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='background-color:#F44336;height:8px;border-radius:4px;'></div>", unsafe_allow_html=True)
    else:
        st.metric("Projected 2-Mile", "N/A")

with col2:
    latest_p = df['pushups'].iloc[-1]
    prog_p = min(latest_p / GOAL_PUSH, 1.0)
    color_p = "#4CAF50" if latest_p >= GOAL_PUSH else "#FFC107" if latest_p >= GOAL_PUSH*0.8 else "#F44336"
    st.metric("Push-ups", latest_p, f"{GOAL_PUSH - latest_p} to goal")
    st.markdown(f"<div style='background-color:{color_p};height:8px;border-radius:4px;'></div>", unsafe_allow_html=True)

with col3:
    latest_c = df['crunches'].iloc[-1]
    prog_c = min(latest_c / GOAL_CRUNCH, 1.0)
    color_c = "#4CAF50" if latest_c >= GOAL_CRUNCH else "#FFC107" if latest_c >= GOAL_CRUNCH*0.8 else "#F44336"
    st.metric("Crunches", latest_c, f"{GOAL_CRUNCH - latest_c} to goal")
    st.markdown(f"<div style='background-color:{color_c};height:8px;border-radius:4px;'></div>", unsafe_allow_html=True)

# === TRENDS (FULL HISTORY) ===
st.markdown("---")
st.subheader("Performance Trends")
colA, colB, colC = st.columns(3)
with colA:
    st.metric("Total Miles", f"{valid_df['cum_miles'].iloc[-1]:.1f}")
with colB:
    overall_avg = valid_df['pace_min_per_mi'].mean()
    st.metric("Career Avg Pace", f"{overall_avg:.2f} min/mi")
with colC:
    if len(valid_df) > 1:
        delta = valid_df['pace_min_per_mi'].iloc[0] - valid_df['pace_min_per_mi'].iloc[-1]
        st.metric("Pace Δ (First → Now)", f"{delta:+.2f} min/mi")
    else:
        st.metric("Pace Δ", "N/A")

# === CHARTS ===
tab1, tab2, tab3 = st.tabs(["Pace", "Push-ups", "Crunches"])

with tab1:
    valid_df['rolling_pace'] = valid_df['pace_min_per_mi'].rolling(5, min_periods=1).mean()
    fig = px.line(valid_df, x='date', y=['pace_min_per_mi', 'rolling_pace'], title="Pace Trend")
    fig.add_hline(y=GOAL_RUN_MIN/2, line_dash="dash", line_color="red", annotation_text=f"Goal: {GOAL_RUN_MIN/2:.1f} min/mi")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig = px.bar(df, x='date', y='pushups', title="Push-ups")
    fig.add_hline(y=GOAL_PUSH, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    fig = px.bar(df, x='date', y='crunches', title="Crunches")
    fig.add_hline(y=GOAL_CRUNCH, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)
