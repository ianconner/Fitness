# pages/01_Dashboard.py
import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime

# ——— DATABASE ———
def conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— FETCH DATA ———
c = conn()
df_workouts = pd.read_sql("""
    SELECT w.workout_date, w.notes, w.duration_min,
           COALESCE(string_agg(
               e.exercise || 
               COALESCE(' ' || e.sets || 'x', '') ||
               COALESCE(e.reps || ' reps', '') ||
               COALESCE(' ' || e.weight_lbs || ' lb', '') ||
               COALESCE(' ' || e.time_min || ' min', '') ||
               COALESCE(' (rest ' || e.rest_min || ' min)', ''),
               '; '
           ), 'No exercises parsed') AS summary
    FROM workouts w
    LEFT JOIN workout_exercises e ON w.id = e.workout_id
    WHERE w.user_id = %s
    GROUP BY w.id, w.workout_date, w.notes, w.duration_min
    ORDER BY w.workout_date DESC
""", c, params=(st.session_state.user_id,))

df_goals = pd.read_sql("""
    SELECT exercise, metric_type, target_value, target_date 
    FROM goals WHERE user_id = %s ORDER BY target_date
""", c, params=(st.session_state.user_id,))
c.close()

# ——— PAGE ———
st.set_page_config(page_title="Dashboard - SOPHIA", layout="wide")
st.title("Workout Dashboard")

# ——— HEATMAP ———
if not df_workouts.empty:
    df_heat = df_workouts.copy()
    df_heat['date'] = pd.to_datetime(df_heat['workout_date'])
    df_heat = df_heat.groupby('date').size().reset_index(name='count')
    df_heat['weekday'] = df_heat['date'].dt.day_name()
    df_heat['week'] = df_heat['date'].dt.isocalendar().week
    df_heat['year'] = df_heat['date'].dt.year

    fig = px.density_heatmap(
        df_heat,
        x='date',
        y='weekday',
        z='count',
        nbinsx=365,
        color_continuous_scale="Viridis",
        title="Workout Heatmap (Darker = More Workouts)",
        category_orders={"weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
    )
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=50, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ——— WORKOUT HISTORY ———
st.subheader("Workout History")
if df_workouts.empty:
    st.info("No workouts logged yet. Go to **Log Workout** to start!")
else:
    for _, row in df_workouts.iterrows():
        with st.expander(f"**{row['workout_date']}** – {row['duration_min'] or '?'} min"):
            st.caption("**Notes:**")
            st.write(row['notes'])
            st.caption("**Parsed Exercises:**")
            st.code(row['summary'], language=None)

# ——— ACTIVE GOALS ———
if not df_goals.empty:
    st.subheader("Active Goals")
    for _, g in df_goals.iterrows():
        metric = g['metric_type'].replace('_', ' ').title()
        st.markdown(f"**{g['exercise']}** → **{g['target_value']} {metric}** by **{g['target_date']}**")
else:
    st.info("No goals set. Go to **Goals** to add one!")

# ——— QUICK STATS ———
if not df_workouts.empty:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Workouts", len(df_workouts))
    with col2:
        total_min = df_workouts['duration_min'].sum()
        st.metric("Total Time", f"{int(total_min)} min" if pd.notna(total_min) else "N/A")
    with col3:
        days = (df_workouts['workout_date'].max() - df_workouts['workout_date'].min()).days + 1
        freq = len(df_workouts) / days if days > 0 else 0
        st.metric("Avg Frequency", f"{freq:.2f} / day")
