# pages/goals.py
import streamlit as st
from datetime import date, timedelta
import psycopg2
import pandas as pd
import time
import re
import numpy as np # Import numpy for robust array handling

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# Auto-detect helpers (same as dashboard)
def extract_pace_goal(goal_text):
    text = goal_text.lower()
    dist_match = re.search(r'(\d*\\.?\\d+)\\s*(mile|mi)', text)
    time_match = re.search(r'(\\d+)\\s*(min|minute|mins)', text)
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

    # Initialize session state for editing
    if 'editing_goal_id' not in st.session_state:
        st.session_state.editing_goal_id = None
    
    # ───── EDIT GOAL FORM ─────
    # (Assuming the Edit Form logic exists here, using st.session_state.editing_goal_id)
    if st.session_state.editing_goal_id is not None:
        # Load the goal data being edited
        cur.execute("SELECT id, exercise, metric_type, target_value, target_date FROM goals WHERE id = %s AND user_id = %s", (st.session_state.editing_goal_id, st.session_state.user_id))
        goal_data = cur.fetchone()
        
        if goal_data:
            edit_id, edit_exercise, edit_metric, edit_value, edit_date = goal_data
            
            st.subheader(f"Edit Goal ID: {edit_id}")
            with st.form(f"edit_goal_{edit_id}"):
                new_exercise = st.text_input("Goal (e.g., 'Run 2 miles in 18 min')", value=edit_exercise)
                new_metric_type = st.selectbox("Metric", ["time_min", "distance_mi", "weight_lbs", "reps"], index=["time_min", "distance_mi", "weight_lbs", "reps"].index(edit_metric))
                new_target_value = st.number_input("Target Value", min_value=0.1, step=0.1, value=float(edit_value))
                new_target_date = st.date_input("Target Date", value=edit_date)

                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("Save Changes", type="primary"):
                        try:
                            cur.execute(
                                "UPDATE goals SET exercise = %s, metric_type = %s, target_value = %s, target_date = %s WHERE id = %s AND user_id = %s",
                                (new_exercise, new_metric_type, new_target_value, new_target_date, edit_id, st.session_state.user_id)
                            )
                            conn.commit()
                            st.success("Goal updated!")
                            st.session_state.editing_goal_id = None
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error saving goal: {e}")
                        finally:
                            cur.close()
                            conn.close()
                with col_cancel:
                    if st.button("Cancel"):
                        st.session_state.editing_goal_id = None
                        st.rerun()
            return # Exit main() to prevent other forms from loading while editing

    try:
        # Load all goals
        goals_query = """
            SELECT id, exercise, metric_type, target_value, target_date, created_at
            FROM goals
            WHERE user_id = %s
            ORDER BY target_date
        """
        df_goals = pd.read_sql(goals_query, conn, params=(st.session_state.user_id,))

        if not df_goals.empty:
            df_goals['target_date'] = pd.to_datetime(df_goals['target_date']).dt.date
            df_goals['target_value'] = pd.to_numeric(df_goals['target_value'], errors='coerce')
        
        # Load workouts for progress calculation
        workouts_query = """
            SELECT w.workout_date, w.duration_min, w.notes,
                   we.exercise, we.sets, we.reps, we.weight_lbs, we.time_min, we.distance_mi
            FROM workouts w
            LEFT JOIN workout_exercises we ON w.id = we.workout_id
            WHERE w.user_id = %s
            ORDER BY w.workout_date DESC
        """
        df_workouts = pd.read_sql(workouts_query, conn, params=(st.session_state.user_id,))
        
        # Robust data type conversion for workouts
        if not df_workouts.empty:
            df_workouts['workout_date'] = pd.to_datetime(df_workouts['workout_date']).dt.date
            numeric_cols = ['duration_min', 'sets', 'reps', 'weight_lbs', 'time_min', 'distance_mi']
            for col in numeric_cols:
                df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
            df_workouts['pace_min_mi'] = np.where(df_workouts['distance_mi'] > 0, df_workouts['time_min'] / df_workouts['distance_mi'], np.nan)
            df_workouts['pace_min_mi'] = pd.to_numeric(df_workouts['pace_min_mi'], errors='coerce')

        # === GOAL PROGRESS CALCULATION (Synchronized with Dashboard) ===
        progress = {}
        if not df_goals.empty and not df_workouts.empty:
            for _, goal in df_goals.iterrows():
                goal_text = goal['exercise']
                metric = goal['metric_type']
                target = goal['target_value']
                
                # Check for pace goal first
                dist, time = extract_pace_goal(goal_text)
                
                if dist and time and metric == 'time_min':
                    target_pace = time / dist
                    matches = df_workouts[
                        (df_workouts['distance_mi'] >= dist * 0.9) & 
                        (df_workouts['distance_mi'] <= dist * 1.1)
                    ]
                    best_pace = matches['pace_min_mi'].min()
                    
                    if not pd.isna(best_pace) and target_pace > 0:
                        pct = min((target_pace / best_pace) * 100, 150)
                    else:
                        best_pace = None
                        pct = 0
                        
                    progress[goal_text] = {
                        'type': 'pace', 'current_pace': best_pace, 'goal_pace': target_pace, 'pct': pct
                    }

                elif metric in ['weight_lbs', 'reps', 'distance_mi', 'time_min']:
                    matches = df_workouts[
                        df_workouts['exercise'].str.contains(goal_text, case=False, na=False)
                    ]
                    
                    if metric in ['weight_lbs', 'reps', 'distance_mi']:
                        current = pd.to_numeric(matches[metric], errors='coerce').max()
                        if not pd.isna(current) and target > 0:
                            pct = min((current / target) * 100, 150)
                        else:
                            current = 0
                            pct = 0
                    else: # metric is 'time_min' (lower is better)
                        current = pd.to_numeric(matches[metric], errors='coerce').min()
                        if not pd.isna(current) and current > 0 and target > 0:
                            pct = min((target / current) * 100, 150)
                        else:
                            current = None
                            pct = 0
                    
                    progress[goal_text] = {
                        'type': 'value', 'current': current, 'target': target, 'metric': metric, 'pct': pct
                    }

        # ───── DISPLAY ACTIVE GOALS ─────
        df_active_goals = df_goals[df_goals['target_date'] >= date.today()].copy()
        
        st.subheader("Active Goals")
        if not df_active_goals.empty:
            for _, row in df_active_goals.iterrows():
                goal_id = row['id']
                exercise = row['exercise']
                data = progress.get(exercise, {'type': 'value', 'pct': 0, 'current': 0, 'target': row['target_value']})
                
                with st.container(border=True):
                    # Columns for progress and buttons (FIX for Issue 1)
                    col_display, col_buttons = st.columns([5, 1])

                    with col_display:
                        st.markdown(f"**{exercise}**")
                        
                        days_left = (pd.to_datetime(row['target_date']) - pd.Timestamp.today()).days
                        status = "On Track" if days_left > 7 else "Urgent" if days_left >= 0 else "Overdue"
                        
                        if data['type'] == 'pace':
                            goal_pace_text = f"Goal: {data['goal_pace']:.2f} min/mi"
                            current_pace_text = f"Best: {data['current_pace']:.2f} min/mi" if data['current_pace'] else "No data"
                            st.caption(f"{goal_pace_text} | {current_pace_text} | Due: {row['target_date'].strftime('%b %d, %Y')} | Status: {status}")
                        else:
                            metric_unit = row['metric_type'].replace('_', ' ')
                            current_text = f"Current: {data['current']}" if data['current'] else "No data"
                            st.caption(f"Goal: {data['target']} {metric_unit} | {current_text} | Due: {row['target_date'].strftime('%b %d, %Y')} | Status: {status}")

                        st.progress(data['pct'] / 100)

                    with col_buttons:
                        # Edit Button
                        if st.button("✏️", key=f"edit_{goal_id}", help="Edit goal", use_container_width=True):
                            st.session_state.editing_goal_id = goal_id
                            st.rerun()

                        # Delete Button
                        if st.button("🗑️", key=f"delete_{goal_id}", help="Delete goal", use_container_width=True):
                            conn_del = get_conn()
                            cur_del = conn_del.cursor()
                            try:
                                cur_del.execute("DELETE FROM goals WHERE id=%s AND user_id=%s", (goal_id, st.session_state.user_id))
                                conn_del.commit()
                                st.success("Goal deleted!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                            finally:
                                cur_del.close()
                                conn_del.close()
        else:
            st.info("No active goals yet. Add one below!")
            
        st.markdown("---") # Separator before the Add Goal form

    except Exception as e:
        st.error(f"Error loading goals: {e}")
    finally:
        # Close connection only if not inside an editing block that needs it open
        if st.session_state.editing_goal_id is None:
            cur.close()
            conn.close()

    # ───── ADD GOAL FORM ─────
    st.subheader("Add New Goal")
    with st.form("add_goal"):
        goal_exercise = st.text_input("Goal (e.g., 'Run 2 miles in 18 min')")
        metric_type = st.selectbox("Metric", ["time_min", "distance_mi", "weight_lbs", "reps"])
        target_value = st.number_input("Target Value", min_value=0.1, step=0.1)
        target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30))
        submitted = st.form_submit_button("Add Goal", type="primary")

        if submitted:
            if not goal_exercise:
                st.error("Please describe your goal.")
            else:
                conn_add = get_conn()
                cur_add = conn_add.cursor()
                try:
                    cur_add.execute(
                        "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                        (st.session_state.user_id, goal_exercise, metric_type, target_value, target_date)
                    )
                    conn_add.commit()
                    st.success("Goal added!")
                    st.rerun()
                except Exception as e:
                    conn_add.rollback()
                    st.error(f"Error adding goal: {e}")
                finally:
                    cur_add.close()
                    conn_add.close()
