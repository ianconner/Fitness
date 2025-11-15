# pages/goals.py
import streamlit as st
import psycopg2
from datetime import date
import pandas as pd
import re

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# Reuse same helper functions
def extract_pace_goal(goal_text):
    text = goal_text.lower()
    dist_match = re.search(r'(\d*\.?\d+)\s*(mile|mi)', text)
    time_match = re.search(r'(\d+)\s*(min|minute|mins)', text)
    distance = float(dist_match.group(1)) if dist_match else None
    total_time = float(time_match.group(1)) if time_match else None
    if distance and total_time and distance > 0:
        return distance, total_time
    return None, None

def calculate_pace_min_mi(distance_mi, total_time_min):
    return total_time_min / distance_mi if distance_mi and distance_mi > 0 else None

def main():
    st.markdown("## Goals")
    st.markdown("Set and track your fitness targets.")

    conn = get_conn()
    cur = conn.cursor()

    try:
        # Load goals
        cur.execute("""
            SELECT exercise, metric_type, target_value, target_date
            FROM goals
            WHERE user_id = %s AND target_date >= %s
            ORDER BY target_date
        """, (st.session_state.user_id, date.today()))
        goals_rows = cur.fetchall()
        df_goals = pd.DataFrame(goals_rows, columns=['exercise', 'metric_type', 'target_value', 'target_date'])

        # Load workouts for progress
        cur.execute("""
            SELECT we.exercise, we.time_min, we.distance_mi, we.rest_min, we.reps
            FROM workout_exercises we
            JOIN workouts w ON we.workout_id = w.id
            WHERE w.user_id = %s
        """, (st.session_state.user_id,))
        rows = cur.fetchall()
        df_workouts = pd.DataFrame(rows, columns=['exercise', 'time_min', 'distance_mi', 'rest_min', 'reps'])

    finally:
        conn.close()

    # Prep workouts
    if not df_workouts.empty:
        for col in ['time_min', 'distance_mi', 'rest_min', 'reps']:
            df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
        df_workouts['distance_mi'] = df_workouts['distance_mi'].replace(0, pd.NA)
        df_workouts['total_effort'] = (df_workouts['time_min'] + df_workouts['rest_min']) * df_workouts['reps']
        df_workouts['pace_min_mi'] = df_workouts['total_effort'] / df_workouts['distance_mi']
    else:
        df_workouts = pd.DataFrame(columns=['exercise', 'pace_min_mi'])

    # Progress logic
    progress = {}
    for _, row in df_goals.iterrows():
        exercise = row['exercise']
        metric_type = row['metric_type']
        target_value = float(row['target_value'])
        days_left = (pd.to_datetime(row['target_date']) - pd.Timestamp.today()).days

        matches = df_workouts[
            df_workouts['exercise'].str.contains(exercise, case=False, na=False)
        ]

        current_distance = current_time = current_pace = None
        if not matches.empty:
            current_distance = pd.to_numeric(matches['distance_mi'], errors='coerce').max()
            current_time = pd.to_numeric(matches['time_min'], errors='coerce').min()
            paces = pd.to_numeric(matches['pace_min_mi'], errors='coerce')
            current_pace = paces.min() if not paces.empty else None

        # Auto-detect pace goal
        dist, total_time = extract_pace_goal(exercise)
        if dist and total_time:
            goal_pace = calculate_pace_min_mi(dist, total_time)
            pct = min((goal_pace / current_pace) * 100, 150) if current_pace and current_pace > 0 else 0
            status = "Exceeding!" if pct > 100 else "On Track" if pct > 0 else "No data"
            progress[exercise] = {
                'type': 'pace_auto',
                'goal_pace': goal_pace,
                'current_pace': current_pace,
                'current_distance': dist,
                'current_time': total_time,
                'pct': pct,
                'status': status
            }
            continue

        # time_min goal
        if metric_type == 'time_min':
            goal_time = target_value
            goal_pace = calculate_pace_min_mi(current_distance, goal_time) if current_distance else None
            pct = min((goal_pace / current_pace) * 100, 150) if goal_pace and current_pace else 0
            status = "Exceeding!" if pct > 100 else "On Track" if pct > 0 else "No data"
            progress[exercise] = {
                'type': 'time_min',
                'goal_time': goal_time,
                'current_distance': current_distance,
                'current_time': current_time,
                'current_pace': current_pace,
                'goal_pace': goal_pace,
                'pct': pct,
                'status': status
            }
            continue

        # Other
        current_val = 0
        if not matches.empty and metric_type in matches.columns:
            current_val = pd.to_numeric(matches[metric_type], errors='coerce').max()
        pct = min((current_val / target_value) * 100, 150) if target_value > 0 else 0
        progress[exercise] = {
            'type': 'value',
            'current': current_val,
            'target': target_value,
            'pct': pct
        }

    # DISPLAY
    st.subheader("Active Goals")
    if not df_goals.empty:
        for _, row in df_goals.iterrows():
            exercise = row['exercise']
            data = progress.get(exercise, {'type': 'value', 'pct': 0})
            days_left = (pd.to_datetime(row['target_date']) - pd.Timestamp.today()).days

            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{exercise}**")

                    if data['type'] == 'pace_auto':
                        st.caption(f"Goal: {data['current_distance']} mi in {data['current_time']} min → **{data['goal_pace']:.2f} min/mi**")
                        st.caption(f"Best: {data['current_pace']:.2f} min/mi" if data['current_pace'] else "No data")

                    elif data['type'] == 'time_min':
                        dist = data['current_distance'] or "?"
                        st.caption(f"Goal: {data['goal_time']} min for ~{dist} mi")
                        if data['current_distance']:
                            st.caption(f"→ Goal Pace: {data['goal_pace']:.2f} min/mi")
                        st.caption(f"Best Pace: {data['current_pace']:.2f} min/mi" if data['current_pace'] else "No pace data")

                    else:
                        st.caption(f"Goal: {data['target']} {row['metric_type'].replace('_', ' ')} | Current: {data['current']}")

                    st.progress(data['pct'] / 100)

                with c2:
                    st.markdown(f"**{data['pct']:.1f}%**")
                    if 'status' in data:
                        st.caption(data['status'])
                    st.caption(f"{days_left} days left")
    else:
        st.info("No active goals.")

    # Add Goal Form
    st.markdown("---")
    st.subheader("Add New Goal")
    with st.form("add_goal"):
        goal_exercise = st.text_input("Goal (e.g., 'Run 2 miles in 18 min')")
        metric_type = st.selectbox("Metric", ["time_min", "distance_mi", "weight_lbs", "reps"])
        target_value = st.number_input("Target Value", min_value=0.1, step=0.1)
        target_date = st.date_input("Target Date", value=date.today())
        submitted = st.form_submit_button("Add Goal")

        if submitted:
            if not goal_exercise:
                st.error("Please describe your goal.")
            else:
                try:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                        (st.session_state.user_id, goal_exercise, metric_type, target_value, target_date)
                    )
                    conn.commit()
                    st.success("Goal added!")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error: {e}")
                finally:
                    conn.close()
