import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        database=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASS"),
        port=os.getenv("PG_PORT", "5432")
    )

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM logs ORDER BY date", conn)
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("No logs yet – go add one on the home page!")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['run_pace_min_per_mile'] = df['run_time_min'] / 2

df = df.sort_values('date')
df['cum_miles'] = (df['run_time_min'] > 0).cumsum() * 2
df['cum_pushups'] = df['pushups'].cumsum()
df['cum_crunches'] = df['crunches'].cumsum()

GOAL_RUN_MIN = 18.0
GOAL_PUSH = 45
GOAL_CRUNCH = 45

st.title("Progress Dashboard")

col1, col2, col3 = st.columns(3)
with col1:
    latest_run = df['run_time_min'].iloc[-1]
    prog = min(latest_run / GOAL_RUN_MIN, 1.0)
    st.metric("2-Mile Run", f"{latest_run:.2f} min", f"{(GOAL_RUN_MIN-latest_run):.1f} min to goal")
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

st.markdown("---")
st.subheader("Trend Charts")

tab1, tab2, tab3 = st.tabs(["Run Pace", "Push-ups", "Crunches"])

with tab1:
    fig = px.line(df, x='date', y='run_pace_min_per_mile',
                  title="2-Mile Pace (min/mile)",
                  labels={"run_pace_min_per_mile": "Pace"})
    fig.add_hline(y=GOAL_RUN_MIN/2, line_dash="dash", line_color="red",
                  annotation_text="Goal 9:00/mi")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig = px.bar(df, x='date', y='pushups', title="Push-ups per Session")
    fig.add_hline(y=GOAL_PUSH, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    fig = px.bar(df, x='date', y='crunches', title="Crunches per Session")
    fig.add_hline(y=GOAL_CRUNCH, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Cumulative Totals (Year-to-Date)")

colA, colB, colC = st.columns(3)
with colA:
    st.metric("Total Miles Run", f"{df['cum_miles'].iloc[-1]:.1f}")
with colB:
    st.metric("Total Push-ups", f"{int(df['cum_pushups'].iloc[-1])}")
with colC:
    st.metric("Total Crunches", f"{int(df['cum_crunches'].iloc[-1])}")
