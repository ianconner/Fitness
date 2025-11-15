# pages/goals.py
import streamlit as st
from datetime import date
import psycopg2
import pandas as pd
import time
import re

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# Auto-detect helpers (same as dashboard)
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
            SELECT id, exercise, metric_type, target_value, target_date, created_at
            FROM goals
            WHERE user_id = %s AND target_date >= %s
            ORDER BY target_date
        """, (st.session_state.user_id, date.today()))
        goals_rows = cur.fetchall()
        df_goals = pd.DataFrame(goals_rows, columns=['id', 'exercise', 'metric_type', 'target_value', 'target_date', 'created_at'])

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

    # ───── ADD GOAL FORM ─────
    st.subheader("Add New Goal")
    with st.form("add_goal"):
        goal_exercise = st.text_input("Goal (e.g., 'Run 2 miles in 18 min')")
        metric_type = st.selectbox("Metric", ["time_min", "distance_mi", "weight_lbs", "reps"])
        target_value = st.number_input("Target Value", min_value=0.1, step=0.1)
        target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30))
        submitted = st.form_submit_button("Add Goal")

        if submitted:
            if not goal_exercise:
                st.error("Please describe your goal.")
            else:
                try:
                    cur = get_conn().cursor()
                    cur.execute(
                        "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                        (st.session_state.user_id, goal_exercise, metric_type, target_value, target_date)
                    )
                    get_conn().commit()
                    st.success("Goal added!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # ───── DISPLAY GOALS (Same as Dashboard) ─────
    st.subheader("Active Goals")
    if not df_goals.empty:
        # Progress logic
        progress = {}
        for _, row in df_goals.iterrows():
            exercise = row['exercise']
            metric_type = row['metric_type']
            target_value = float(row['target_value'])
            days_left = (pd.to_datetime(row['target_date']) - pd.Timestamp.today()).days

            matches = df_workouts[df_workouts['exercise'].str.contains(exercise, case=False, na=False)]

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

        # Display with Edit/Delete
        for idx, row in df_goals.iterrows():
            goal_id = row['id']
            exercise = row['exercise']
            data = progress.get(exercise, {'type': 'value', 'pct': 0})
            days_left = (pd.to_datetime(row['target_date']) - pd.Timestamp.today()).days

            with st.container(border=True):
                col_main, col_status = st.columns([3, 1])
                with col_main:
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

                with col_status:
                    st.markdown(f"**{data['pct']:.1f}%**")
                    if 'status' in data:
                        st.caption(data['status'])
                    st.caption(f"{days_left} days left")

                # Edit/Delete Buttons
                st.markdown("---")
                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button("✏️ Edit", key=f"edit_{goal_id}"):
                        # Edit logic (open inline form)
                        st.session_state.editing_goal_id = goal_id
                        st.rerun()
                with col_delete:
                    if st.button("🗑️ Delete", key=f"delete_{goal_id}", type="secondary"):
                        conn_del = get_conn()
                        cur_del = conn_del.cursor()
                        try:
                            cur_del.execute("DELETE FROM goals WHERE id = %s AND user_id = %s", (goal_id, st.session_state.user_id))
                            conn_del.commit()
                            st.success("Goal deleted!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                        finally:
                            cur_del.close()
                            conn_del.close()

            st.write("")

    else:
        st.info("No active goals.")

    # ───── EDIT MODE ─────
    if st.session_state.get("editing_goal_id"):
        goal_id = st.session_state.editing_goal_id
        # Fetch goal
        conn_edit = get_conn()
        cur_edit = conn_edit.cursor()
        cur_edit.execute("SELECT exercise, metric_type, target_value, target_date FROM goals WHERE id = %s AND user_id = %s", (goal_id, st.session_state.user_id))
        edit_row = cur_edit.fetchone()
        if edit_row:
            edit_exercise = st.text_input("Goal", value=edit_row[0])
            edit_metric = st.selectbox("Metric", ["time_min", "distance_mi", "weight_lbs", "reps"], index=["time_min", "distance_mi", "weight_lbs", "reps"].index(edit_row[1]))
            edit_value = st.number_input("Target Value", value=float(edit_row[2]))
            edit_date = st.date_input("Target Date", value=edit_row[3])

            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("Save Changes"):
                    try:
                        cur_edit.execute(
                            "UPDATE goals SET exercise = %s, metric_type = %s, target_value = %s, target_date = %s WHERE id = %s AND user_id = %s",
                            (edit_exercise, edit_metric, edit_value, edit_date, goal_id, st.session_state.user_id)
                        )
                        conn_edit.commit()
                        st.success("Goal updated!")
                        st.session_state.editing_goal_id = None
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                    finally:
                        cur_edit.close()
                        conn_edit.close()
            with col_cancel:
                if st.button("Cancel"):
                    st.session_state.editing_goal_id = None
                    st.rerun()
        else:
            st.session_state.editing_goal_id = None
            st.rerun()

    # ───── ADD GOAL FORM ─────
    st.markdown("---")
    st.subheader("Add New Goal")
    with st.form("add_goal"):
        goal_exercise = st.text_input("Goal (e.g., 'Run 2 miles in 18 min')")
        metric_type = st.selectbox("Metric", ["time_min", "distance_mi", "weight_lbs", "reps"])
        target_value = st.number_input("Target Value", min_value=0.1, step=0.1)
        target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30))
        submitted = st.form_submit_button("Add Goal")

        if submitted:
            if not goal_exercise:
                st.error("Please describe your goal.")
            else:
                try:
                    cur = get_conn().cursor()
                    cur.execute(
                        "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                        (st.session_state.user_id, goal_exercise, metric_type, target_value, target_date)
                    )
                    get_conn().commit()
                    st.success("Goal added!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
