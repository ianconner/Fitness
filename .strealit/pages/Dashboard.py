# .strealit/pages/01_Dashboard.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from datetime import date, timedelta
import plotly.express as px

# ——— DATABASE ENGINE ———
engine = create_engine(st.secrets["POSTGRES_URL"])  # Must be postgresql://

# ——— FETCH WORKOUTS ———
def get_workouts():
    return pd.read_sql("""
        SELECT w.workout_date, w.duration_min, w.notes,
               we.exercise, we.sets, we.reps, we.weight_lbs, we.time_min, we.distance_mi
        FROM workouts w
        LEFT JOIN workout_exercises we ON w.id = we.workout_id
        WHERE w.user_id = %s
        ORDER BY w.workout_date DESC
    """, engine, params=(st.session_state.user_id,))

# ——— FETCH GOALS ———
def get_goals():
    return pd.read_sql("""
        SELECT exercise, metric_type, target_value, target_date
        FROM goals
        WHERE user_id = %s AND target_date >= %s
        ORDER BY target_date
    """, engine, params=(st.session_state.user_id, date.today()))

# ——— MAIN ———
st.markdown("## Dashboard")
st.markdown("Your fitness journey at a glance.")

# ——— WORKOUT SUMMARY ———
df_workouts = get_workouts()
if not df_workouts.empty:
    col1, col2, col3 = st.columns(3)
    with col1:
        total_workouts = len(df_workouts.drop_duplicates('workout_date'))
        st.metric("Total Workouts", total_workouts)
    with col2:
        total_duration = df_workouts['duration_min'].sum()
        st.metric("Total Time", f"{int(total_duration)} min")
    with col3:
        avg_duration = df_workouts.groupby('workout_date')['duration_min'].sum().mean()
        st.metric("Avg Duration", f"{int(avg_duration)} min")

    st.subheader("Recent Workouts")
    recent = df_workouts.head(10)
    st.dataframe(recent[["workout_date", "exercise", "sets", "reps", "weight_lbs", "time_min", "distance_mi"]],
                 use_container_width=True, hide_index=True)

    st.subheader("Workout Frequency")
    freq = df_workouts.groupby('workout_date').size().reset_index(name='count')
    freq['workout_date'] = pd.to_datetime(freq['workout_date'])
    fig = px.bar(freq, x='workout_date', y='count', title="Workouts per Day")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No workouts yet. Log one to get started!")

# ——— GOALS PROGRESS ———
df_goals = get_goals()
if not df_goals.empty:
    st.subheader("Active Goals")
    df_goals["Days Left"] = (df_goals["target_date"] - date.today()).dt.days
    df_goals["Status"] = df_goals["Days Left"].apply(
        lambda x: "On Track" if x > 7 else "Urgent" if x >= 0 else "Overdue"
    )
    df_goals = df_goals[["exercise", "metric_type", "target_value", "target_date", "Days Left", "Status"]]
    st.dataframe(df_goals, use_container_width=True, hide_index=True)
else:
    st.info("No active goals. Set one in the Goals tab!")
