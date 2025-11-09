import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    url = st.secrets.get("POSTGRES_URL") or os.getenv("POSTGRES_URL")
    if not url:
        st.error("Missing POSTGRES_URL in secrets!")
        st.stop()
    return psycopg2.connect(url)

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM logs ORDER BY date", conn)
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("No logs yet – go crush a run!")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mile'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)

# Filter valid runs
runs = df[df['distance'] > 0].copy()
runs['cum_miles'] = runs['distance'].cumsum()

GOAL_RUN_MIN = 18.0
GOAL_PUSH = 45
GOAL_CRUNCH = 45

st.title("Progress Dashboard")

# Latest Stats
col1, col2, col3 = st.columns(3)
with col1:
    latest_run = runs['run_time_min'].iloc[-1] if not runs.empty else None
    if latest_run:
        prog = min(latest_run / GOAL_RUN_MIN, 1.0)
        st.metric("2-Mile Time", f"{latest_run:.2f} min", f"{(GOAL_RUN_MIN-latest_run):.1f} to goal")
        st.progress(prog)
with col2:
    latest_p = df['pushups'].iloc[-1]
    prog_p = min(latest_p / GOAL_PUSH, 1.0)
    st.metric("Push-ups", latest_p, f"{GOAL_PUSH-latest_p} to goal")
    st.progress(prog_p)
with col3:
    latest_c = df['crunches'].iloc[-1]
    prog_c = min(latest_c / GOAL_CRUNCH, 1.0)
    st.metric("Crunches", latest_c, f"{GOAL_CRUNCH-latest_c} to goal")
    st.progress(prog_c)

# Charts
st.markdown("---")
tab1, tab2, tab3, tab4 = st.tabs(["Pace", "Distance", "Strength", "Energy"])

with tab1:
    fig = px.line(runs, x='date', y='pace_min_per_mile', title="Pace Trend (min/mile)")
    fig.add_hline(y=9.0, line_dash="dash", line_color="red", annotation_text="Goal: 9:00/mi")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig = px.bar(runs, x='date', y='distance', title="Run Distance (miles)")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    fig = px.line(df, x='date', y=['pushups', 'crunches'], title="Strength Progress")
    fig.add_hline(y=45, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    fig = px.scatter(df, x='date', y='felt_rating', size='distance',
                     title="Energy Level (1–5) vs Run Distance",
                     labels={"felt_rating": "How You Felt"})
    st.plotly_chart(fig, use_container_width=True)

# Cumulative
st.markdown("---")
colA, colB, colC = st.columns(3)
with colA:
    total_miles = runs['cum_miles'].iloc[-1] if not runs.empty else 0
    st.metric("Total Miles Run", f"{total_miles:.1f}")
with colB:
    st.metric("Total Push-ups", df['pushups'].sum())
with colC:
    st.metric("Total Crunches", df['crunches'].sum())
