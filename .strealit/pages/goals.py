# pages/goals.py
import streamlit as st
from datetime import date, timedelta
import psycopg2
import pandas as pd
import re
import numpy as np

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def extract_pace_goal(goal_text):
    """Extract distance and time from goal text like 'Run 2 miles in 18 min'"""
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

    if 'editing_goal_id' not in st.session_state:
        st.session_state.editing_goal_id = None
    
    # ───── EDIT GOAL FORM ─────
    if st.session_state.editing_goal_id is not None:
        cur.execute("SELECT id, exercise, metric_type, target_value, target_date FROM goals WHERE id = %s AND user_id = %s", 
                   (st.session_state.editing_goal_id, st.session_state.user_id))
        goal_data = cur.fetchone()
        
        if goal_data:
            edit_id, edit_exercise, edit_metric, edit_value, edit_date = goal_data
            
            st.subheader(f"✏️ Edit Goal")
            with st.form(f"edit_goal_{edit_id}"):
                new_exercise = st.text_input("Goal (e.g., 'Run 2 miles in 18 min')", value=edit_exercise)
                new_metric_type = st.selectbox("Metric", ["time_min", "distance_mi", "weight_lbs", "reps"], 
                                              index=["time_min", "distance_mi", "weight_lbs", "reps"].index(edit_metric))
                new_target_value = st.number_input("Target Value", min_value=0.1, step=0.1, value=float(edit_value))
                new_target_date = st.date_input("Target Date", value=edit_date)

                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("💾 Save Changes", type="primary"):
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
                with col_cancel:
                    if st.form_submit_button("❌ Cancel"):
                        st.session_state.editing_goal_id = None
                        st.rerun()
            cur.close()
            conn.close()
            return

    try:
        # Load goals
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
        
        # Load workouts
        workouts_query = """
            SELECT w.workout_date, w.duration_min, w.notes,
                   we.exercise, we.sets, we.reps, we.weight_lbs, we.time_min, we.distance_mi, we.rest_min
            FROM workouts w
            LEFT JOIN workout_exercises we ON w.id = we.workout_id
            WHERE w.user_id = %s
            ORDER BY w.workout_date DESC
        """
        df_workouts = pd.read_sql(workouts_query, conn, params=(st.session_state.user_id,))
        
        if not df_workouts.empty:
            df_workouts['workout_date'] = pd.to_datetime(df_workouts['workout_date']).dt.date
            numeric_cols = ['duration_min', 'sets', 'reps', 'weight_lbs', 'time_min', 'distance_mi', 'rest_min']
            for col in numeric_cols:
                df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
            
            # Calculate pace: ((time + rest) * reps) / distance
            df_workouts['total_effort'] = (df_workouts['time_min'] + df_workouts['rest_min']) * df_workouts['reps']
            df_workouts['pace_min_mi'] = np.where(
                df_workouts['distance_mi'] > 0,
                df_workouts['total_effort'] / df_workouts['distance_mi'],
                np.nan
            )

        # === CALCULATE PROGRESS ===
        progress = {}
        if not df_goals.empty and not df_workouts.empty:
            for _, goal in df_goals.iterrows():
                goal_text = goal['exercise']
                metric = goal['metric_type']
                target = goal['target_value']
                
                # Check for pace-based cardio goal
                dist, time = extract_pace_goal(goal_text)
                
                if dist and time and metric == 'time_min':
                    goal_pace = time / dist
                    goal_distance = dist
                    
                    # Identify cardio workouts
                    cardio_keywords = ['run', 'running', 'walk', 'walking', 'elliptical', 'rowing', 'swim', 'cycling', 'bike', 'cardio']
                    cardio_workouts = df_workouts[
                        df_workouts['exercise'].str.contains('|'.join(cardio_keywords), case=False, na=False) |
                        (df_workouts['distance_mi'] > 0)
                    ].copy()
                    
                    if not cardio_workouts.empty:
                        # Best pace achieved (any distance)
                        best_pace = cardio_workouts['pace_min_mi'].min()
                        best_pace_workout = cardio_workouts[cardio_workouts['pace_min_mi'] == best_pace].iloc[0]
                        
                        # Longest distance achieved
                        best_distance = cardio_workouts['distance_mi'].max()
                        
                        # Star counts
                        pace_stars = len(cardio_workouts[cardio_workouts['pace_min_mi'] <= goal_pace])
                        distance_stars = len(cardio_workouts[cardio_workouts['distance_mi'] >= goal_distance])
                        
                        # Progress percentages (capped at 100 for display)
                        pace_pct = min((goal_pace / best_pace) * 100, 100) if not pd.isna(best_pace) and best_pace > 0 else 0
                        distance_pct = min((best_distance / goal_distance) * 100, 100) if not pd.isna(best_distance) and goal_distance > 0 else 0
                        
                        progress[goal_text] = {
                            'type': 'pace',
                            'goal_pace': goal_pace,
                            'goal_distance': goal_distance,
                            'goal_time': time,
                            'best_pace': best_pace,
                            'best_distance': best_distance,
                            'best_time': best_pace_workout['time_min'],
                            'pace_pct': pace_pct,
                            'distance_pct': distance_pct,
                            'pace_stars': pace_stars,
                            'distance_stars': distance_stars
                        }
                    else:
                        progress[goal_text] = {
                            'type': 'pace',
                            'goal_pace': goal_pace,
                            'goal_distance': goal_distance,
                            'goal_time': time,
                            'pace_pct': 0,
                            'distance_pct': 0,
                            'pace_stars': 0,
                            'distance_stars': 0
                        }
                
                elif metric in ['weight_lbs', 'reps', 'distance_mi']:
                    matches = df_workouts[df_workouts['exercise'].str.contains(goal_text, case=False, na=False)]
                    current = pd.to_numeric(matches[metric], errors='coerce').max() if not matches.empty else 0
                    pct = min((current / target) * 100, 100) if target > 0 and not pd.isna(current) else 0
                    
                    progress[goal_text] = {
                        'type': 'value',
                        'current': current,
                        'target': target,
                        'metric': metric,
                        'pct': pct
                    }

        # ───── DISPLAY ACTIVE GOALS ─────
        df_active = df_goals[df_goals['target_date'] >= date.today()].copy()
        
        st.subheader("Active Goals")
        if not df_active.empty:
            for _, row in df_active.iterrows():
                goal_id = row['id']
                exercise = row['exercise']
                data = progress.get(exercise, {'type': 'value', 'pct': 0})
                
                with st.container(border=True):
                    col_display, col_buttons = st.columns([5, 1])

                    with col_display:
                        st.markdown(f"**{exercise}**")
                        
                        days_left = (row['target_date'] - date.today()).days
                        status = "On Track" if days_left > 7 else "Urgent" if days_left >= 0 else "Overdue"
                        
                        if data['type'] == 'pace':
                            st.caption(f"Goal: {data['goal_distance']:.1f} mi in {data['goal_time']:.0f} min ({data['goal_pace']:.2f} min/mi pace)")
                            
                            if data.get('best_pace'):
                                st.caption(f"Best: {data['best_distance']:.1f} mi in {data['best_time']:.0f} min ({data['best_pace']:.2f} min/mi pace)")
                            else:
                                st.caption("Best: No data yet")
                            
                            st.caption(f"Due: {row['target_date'].strftime('%b %d, %Y')} | Status: {status}")
                            
                            # Pace progress bar
                            pace_label = f"Pace: {data['pace_pct']:.0f}%"
                            if data['pace_stars'] > 0:
                                pace_label += f" {'⭐' * min(data['pace_stars'], 5)}"
                                if data['pace_stars'] > 5:
                                    pace_label += f" x{data['pace_stars']}"
                            st.caption(pace_label)
                            st.progress(data['pace_pct'] / 100)
                            
                            # Distance progress bar
                            dist_label = f"Distance: {data['distance_pct']:.0f}%"
                            if data['distance_stars'] > 0:
                                dist_label += f" {'⭐' * min(data['distance_stars'], 5)}"
                                if data['distance_stars'] > 5:
                                    dist_label += f" x{data['distance_stars']}"
                            st.caption(dist_label)
                            st.progress(data['distance_pct'] / 100)
                        else:
                            metric_unit = row['metric_type'].replace('_', ' ')
                            current_text = f"Current: {data['current']:.1f}" if data.get('current') else "No data"
                            st.caption(f"Goal: {data['target']:.1f} {metric_unit} | {current_text}")
                            st.caption(f"Due: {row['target_date'].strftime('%b %d, %Y')} | Status: {status}")
                            st.progress(data['pct'] / 100)

                    with col_buttons:
                        if st.button("✏️", key=f"edit_{goal_id}", help="Edit goal", width='stretch'):
                            st.session_state.editing_goal_id = goal_id
                            st.rerun()

                        if st.button("🗑️", key=f"delete_{goal_id}", help="Delete goal", width='stretch'):
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
            
        st.markdown("---")

    except Exception as e:
        st.error(f"Error loading goals: {e}")
    finally:
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
