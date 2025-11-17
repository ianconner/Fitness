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
    """Extract distance and time from goal text like 'Run 2 miles in 18:30'"""
    text = goal_text.lower()
    dist_match = re.search(r'(\d*\.?\d+)\s*(mile|mi)', text)
    # Match both MM:SS and plain minutes format
    time_match = re.search(r'(\d+):(\d+)', text)  # MM:SS format
    if not time_match:
        time_match = re.search(r'(\d+)\s*(min|minute|mins)', text)  # Plain minutes
    
    distance = float(dist_match.group(1)) if dist_match else None
    
    if time_match:
        if ':' in time_match.group(0):  # MM:SS format
            minutes = int(time_match.group(1))
            seconds = int(time_match.group(2))
            total_time = minutes + (seconds / 60)
        else:  # Plain minutes
            total_time = float(time_match.group(1))
    else:
        total_time = None
    
    if distance and total_time and distance > 0:
        return distance, total_time
    return None, None

def format_time_mmss(decimal_minutes):
    """Convert decimal minutes to MM:SS format"""
    if pd.isna(decimal_minutes) or decimal_minutes <= 0:
        return "0:00"
    minutes = int(decimal_minutes)
    seconds = int((decimal_minutes - minutes) * 60)
    return f"{minutes}:{seconds:02d}"

def format_pace_mmss(pace_decimal):
    """Convert decimal pace to MM:SS per mile format"""
    if pd.isna(pace_decimal) or pace_decimal <= 0:
        return "-"
    minutes = int(pace_decimal)
    seconds = int((pace_decimal - minutes) * 60)
    return f"{minutes}:{seconds:02d}"

def main():
    st.markdown("## Goals")
    st.markdown("Set and track your fitness targets.")

    conn = get_conn()
    cur = conn.cursor()

    if 'editing_goal_id' not in st.session_state:
        st.session_state.editing_goal_id = None
    
    # Fetch past exercises for autocomplete
    try:
        cur.execute("""
            SELECT DISTINCT we.exercise
            FROM workout_exercises we
            JOIN workouts w ON we.workout_id = w.id
            WHERE w.user_id = %s AND we.exercise IS NOT NULL
        """, (st.session_state.user_id,))
        past_exercises = [row[0] for row in cur.fetchall()]
    except:
        past_exercises = []

    # ───── EDIT GOAL FORM ─────
    if st.session_state.editing_goal_id is not None:
        cur.execute("SELECT id, exercise, metric_type, target_value, target_date FROM goals WHERE id = %s AND user_id = %s", 
                   (st.session_state.editing_goal_id, st.session_state.user_id))
        goal_data = cur.fetchone()
        
        if goal_data:
            edit_id, edit_exercise, edit_metric, edit_value, edit_date = goal_data
            
            st.subheader(f"✏️ Edit Goal")
            with st.form(f"edit_goal_{edit_id}"):
                new_exercise = st.text_input("Goal", value=edit_exercise)
                new_metric_type = st.selectbox("Metric", ["time_min", "distance_mi", "weight_lbs", "reps"], 
                                              index=["time_min", "distance_mi", "weight_lbs", "reps"].index(edit_metric) if edit_metric in ["time_min", "distance_mi", "weight_lbs", "reps"] else 0)
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
            
            # Calculate pace
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
                        best_pace = cardio_workouts['pace_min_mi'].min()
                        best_pace_workout = cardio_workouts[cardio_workouts['pace_min_mi'] == best_pace].iloc[0]
                        best_distance = cardio_workouts['distance_mi'].max()
                        
                        pace_stars = len(cardio_workouts[cardio_workouts['pace_min_mi'] <= goal_pace])
                        distance_stars = len(cardio_workouts[cardio_workouts['distance_mi'] >= goal_distance])
                        
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
                
                elif metric in ['weight_lbs', 'reps', 'distance_mi', 'sets']:
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
                data = progress.get(exercise, {'type': 'value', 'pct': 0, 'current': 0, 'target': row['target_value']})
                
                with st.container(border=True):
                    col_display, col_buttons = st.columns([5, 1])

                    with col_display:
                        st.markdown(f"**{exercise}**")
                        
                        days_left = (row['target_date'] - date.today()).days
                        status = "On Track" if days_left > 7 else "Urgent" if days_left >= 0 else "Overdue"
                        
                        if data['type'] == 'pace':
                            goal_time_formatted = format_time_mmss(data.get('goal_time', 0))
                            goal_pace_formatted = format_pace_mmss(data.get('goal_pace', 0))
                            st.caption(f"Goal: {data.get('goal_distance', 0):.1f} mi in {goal_time_formatted} ({goal_pace_formatted}/mi pace)")
                            
                            if data.get('best_pace'):
                                best_time_formatted = format_time_mmss(data.get('best_time', 0))
                                best_pace_formatted = format_pace_mmss(data['best_pace'])
                                st.caption(f"Best: {data.get('best_distance', 0):.1f} mi in {best_time_formatted} ({best_pace_formatted}/mi pace)")
                            else:
                                st.caption("Best: No data yet")
                            
                            st.caption(f"Due: {row['target_date'].strftime('%b %d, %Y')} | Status: {status}")
                            
                            # Pace progress bar
                            pace_pct = data.get('pace_pct', 0)
                            pace_stars = data.get('pace_stars', 0)
                            pace_label = f"Pace: {pace_pct:.0f}%"
                            if pace_stars > 0:
                                pace_label += f" {'⭐' * min(pace_stars, 5)}"
                                if pace_stars > 5:
                                    pace_label += f" x{pace_stars}"
                            st.caption(pace_label)
                            st.progress(pace_pct / 100)
                            
                            # Distance progress bar
                            dist_pct = data.get('distance_pct', 0)
                            dist_stars = data.get('distance_stars', 0)
                            dist_label = f"Distance: {dist_pct:.0f}%"
                            if dist_stars > 0:
                                dist_label += f" {'⭐' * min(dist_stars, 5)}"
                                if dist_stars > 5:
                                    dist_label += f" x{dist_stars}"
                            st.caption(dist_label)
                            st.progress(dist_pct / 100)
                        else:
                            metric_unit = row['metric_type'].replace('_', ' ')
                            current_val = data.get('current', 0)
                            target_val = data.get('target', row['target_value'])
                            current_text = f"Current: {current_val:.1f}" if current_val else "No data"
                            st.caption(f"Goal: {target_val:.1f} {metric_unit} | {current_text}")
                            st.caption(f"Due: {row['target_date'].strftime('%b %d, %Y')} | Status: {status}")
                            st.progress(data.get('pct', 0) / 100)

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

    # ───── ADD GOAL FORM (Interactive like Log Workout) ─────
    st.subheader("Add New Goal")
    
    # Initialize session state for goal form
    if 'new_goal_category' not in st.session_state:
        st.session_state.new_goal_category = None
    if 'track_weight' not in st.session_state:
        st.session_state.track_weight = True
    if 'track_reps' not in st.session_state:
        st.session_state.track_reps = False
    if 'track_sets' not in st.session_state:
        st.session_state.track_sets = False
    
    # Category selection (outside form for reactivity)
    category = st.selectbox(
        "Category",
        ["", "Cardio", "Weights", "Free-Text"],
        key="goal_category_select"
    )
    st.session_state.new_goal_category = category

    if category:
        if category == "Cardio":
            with st.form("add_goal"):
                # Sub-category
                sub_category = st.selectbox("Type", ["Running", "Walking", "Elliptical", "Other"])
                
                # Exercise name with autocomplete
                cardio_exercises = [ex for ex in past_exercises if any(kw in ex.lower() for kw in ['run', 'walk', 'cardio', 'elliptical', 'bike', 'cycle'])]
                selected_ex = st.selectbox("Exercise (select or type new)", [""] + cardio_exercises, key="cardio_ex_select")
                exercise_name = st.text_input("or type new name", value=selected_ex, key="cardio_ex_input")
                
                # Distance
                distance = st.number_input("Distance (miles)", min_value=0.1, step=0.1, value=2.0)
                
                # Time input in MM:SS format
                st.markdown("**Target Time**")
                col1, col2 = st.columns(2)
                with col1:
                    minutes = st.number_input("Minutes", min_value=0, step=1, value=18, key="time_min")
                with col2:
                    seconds = st.number_input("Seconds", min_value=0, max_value=59, step=1, value=0, key="time_sec")
                
                time_target = minutes + (seconds / 60)  # Convert to decimal minutes for storage
                
                # Calculate and display pace
                if distance > 0:
                    target_pace_decimal = time_target / distance
                    pace_min = int(target_pace_decimal)
                    pace_sec = int((target_pace_decimal - pace_min) * 60)
                    st.info(f"**Target Pace: {pace_min}:{pace_sec:02d} per mile**")
                
                # Target date
                target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30))
                
                submitted = st.form_submit_button("Add Goal", type="primary")
                
                if submitted:
                    if not exercise_name:
                        st.error("Please enter an exercise name.")
                    else:
                        # Format goal text with time in MM:SS format
                        full_name = f"Cardio - {sub_category}: {exercise_name}" if exercise_name else f"Cardio - {sub_category}"
                        goal_text = f"{full_name} - {distance} miles in {minutes}:{seconds:02d}"
                        
                        conn_add = get_conn()
                        cur_add = conn_add.cursor()
                        try:
                            cur_add.execute(
                                "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                                (st.session_state.user_id, goal_text, 'time_min', time_target, target_date)
                            )
                            conn_add.commit()
                            st.success("Cardio goal added!")
                            st.session_state.new_goal_category = None
                            # Clear the category selection
                            if 'goal_category_select' in st.session_state:
                                del st.session_state['goal_category_select']
                            st.rerun()
                        except Exception as e:
                            conn_add.rollback()
                            st.error(f"Error: {e}")
                        finally:
                            cur_add.close()
                            conn_add.close()
        
        elif category == "Weights":
            # Checkboxes OUTSIDE form for reactivity
            st.markdown("**Goal Metrics** (select one or more):")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.session_state.track_weight = st.checkbox("Weight", value=st.session_state.track_weight, key="cb_weight")
            with col2:
                st.session_state.track_reps = st.checkbox("Reps", value=st.session_state.track_reps, key="cb_reps")
            with col3:
                st.session_state.track_sets = st.checkbox("Sets", value=st.session_state.track_sets, key="cb_sets")
            
            with st.form("add_goal"):
                # Sub-category
                sub_category = st.selectbox("Type", ["Free-Weights", "Machine", "Body-Weights"])
                
                # Exercise name with autocomplete
                weight_exercises = [ex for ex in past_exercises if any(kw in ex.lower() for kw in ['squat', 'press', 'bench', 'deadlift', 'curl', 'row', 'weight'])]
                selected_ex = st.selectbox("Exercise (select or type new)", [""] + weight_exercises, key="weight_ex_select")
                exercise_name = st.text_input("or type new name", value=selected_ex, key="weight_ex_input")
                
                # Show input fields based on checkboxes
                target_weight = None
                target_reps = None
                target_sets = None
                
                if st.session_state.track_weight:
                    target_weight = st.number_input("Target Weight (lbs)", min_value=1.0, step=5.0, value=100.0, key="weight_target")
                
                if st.session_state.track_reps:
                    target_reps = st.number_input("Target Reps", min_value=1, step=1, value=10, key="reps_target")
                
                if st.session_state.track_sets:
                    target_sets = st.number_input("Target Sets", min_value=1, step=1, value=3, key="sets_target")
                
                # Target date
                target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30))
                
                submitted = st.form_submit_button("Add Goal", type="primary")
                
                if submitted:
                    if not exercise_name:
                        st.error("Please enter an exercise name.")
                    elif not (st.session_state.track_weight or st.session_state.track_reps or st.session_state.track_sets):
                        st.error("Please select at least one goal metric.")
                    else:
                        # Create goal entries for each selected metric
                        full_name = f"Weights - {sub_category}: {exercise_name}"
                        
                        conn_add = get_conn()
                        cur_add = conn_add.cursor()
                        try:
                            if st.session_state.track_weight and target_weight:
                                goal_text = f"{full_name} - {target_weight} lbs"
                                cur_add.execute(
                                    "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                                    (st.session_state.user_id, goal_text, 'weight_lbs', target_weight, target_date)
                                )
                            
                            if st.session_state.track_reps and target_reps:
                                goal_text = f"{full_name} - {target_reps} reps"
                                cur_add.execute(
                                    "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                                    (st.session_state.user_id, goal_text, 'reps', target_reps, target_date)
                                )
                            
                            if st.session_state.track_sets and target_sets:
                                goal_text = f"{full_name} - {target_sets} sets"
                                cur_add.execute(
                                    "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                                    (st.session_state.user_id, goal_text, 'sets', target_sets, target_date)
                                )
                            
                            conn_add.commit()
                            st.success(f"Weight goal(s) added!")
                            # Reset checkboxes
                            st.session_state.track_weight = True
                            st.session_state.track_reps = False
                            st.session_state.track_sets = False
                            st.session_state.new_goal_category = None
                            # Clear the category selection
                            if 'goal_category_select' in st.session_state:
                                del st.session_state['goal_category_select']
                            st.rerun()
                        except Exception as e:
                            conn_add.rollback()
                            st.error(f"Error: {e}")
                        finally:
                            cur_add.close()
                            conn_add.close()
        
        elif category == "Free-Text":
            with st.form("add_goal"):
                # Simple free-text goal
                goal_description = st.text_area("Goal Description", placeholder="e.g., Touch my toes, Hold plank for 2 minutes, etc.")
                target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30))
                
                submitted = st.form_submit_button("Add Goal", type="primary")
                
                if submitted:
                    if not goal_description:
                        st.error("Please describe your goal.")
                    else:
                        conn_add = get_conn()
                        cur_add = conn_add.cursor()
                        try:
                            cur_add.execute(
                                "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                                (st.session_state.user_id, f"Free-Text: {goal_description}", 'free_text', 1, target_date)
                            )
                            conn_add.commit()
                            st.success("Free-text goal added!")
                            st.session_state.new_goal_category = None
                            # Clear the category selection
                            if 'goal_category_select' in st.session_state:
                                del st.session_state['goal_category_select']
                            st.rerun()
                        except Exception as e:
                            conn_add.rollback()
                            st.error(f"Error: {e}")
                        finally:
                            cur_add.close()
                            conn_add.close()
    else:
        st.info("Select a category above to begin creating your goal.")
