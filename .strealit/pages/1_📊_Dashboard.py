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

# Avg Pace Over Last 5 Runs (or all if <5)
last_n = valid_df.head(5)  # Last 5 (most recent)
avg_pace = last_n['pace_min_per_mi'].mean() if not last_n.empty else pd.NA

# Projected 2-Mile
projected_2mi_min = avg_pace * 2 if pd.notna(avg_pace) else pd.NA
projected_str = f"{int(projected_2mi_min):02d}:{int((projected_2mi_min % 1)*60):02d}" if pd.notna(projected_2mi_min) else "N/A"

GOAL_RUN_MIN = 18.0
GOAL_PUSH = 45
GOAL_CRUNCH = 45

st.title("Progress Dashboard")

# Metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Projected 2-Mile Time", projected_str, f"Based on avg pace ({avg_pace:.2f} min/mi over last {len(last_n)} runs)")
    prog = min(projected_2mi_min / GOAL_RUN_MIN, 1.0) if pd.notna(projected_2mi_min) else 0
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

# Trend Summary (Full History)
st.markdown("---")
st.subheader("Trend Summary (Full History)")
colA, colB, colC = st.columns(3)
with colA:
    st.metric("Total Miles", f"{valid_df['cum_miles'].iloc[-1]:.1f}")
with colB:
    st.metric("Avg Pace (All Runs)", f"{valid_df['pace_min_per_mi'].mean():.2f} min/mi")
with colC:
    pace_delta = valid_df['pace_min_per_mi'].iloc[0] - valid_df['pace_min_per_mi'].iloc[-1]  # First to last
    st.metric("Pace Improvement", f"{pace_delta:.2f} min/mi")

# Charts (Full History Trends)
st.markdown("---")
st.subheader("Trend Charts")

tab1, tab2, tab3 = st.tabs(["Pace Trend", "Push-ups", "Crunches"])

with tab1:
    valid_df['rolling_avg_pace'] = valid_df['pace_min_per_mi'].rolling(window=5).mean()  # 5-run rolling avg
    fig = px.line(valid_df, x='date', y=['pace_min_per_mi', 'rolling_avg_pace'], title="Pace Trend (min/mi)")
    fig.add_hline(y=9.0, line_dash="dash", line_color="red", annotation_text="Goal 9:00/mi")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig = px.bar(df, x='date', y='pushups', title="Push-ups per Session")
    fig.add_hline(y=GOAL_PUSH, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    fig = px.bar(df, x='date', y='crunches', title="Crunches per Session")
    fig.add_hline(y=GOAL_CRUNCH, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)
