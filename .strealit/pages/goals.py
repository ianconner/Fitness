# pages/goals.py
import streamlit as st
from datetime import date, timedelta
import psycopg2
import pandas as pd
import numpy as np

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

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
    st.markdown("Set and track your fitness targets. **Link your workouts to goals to see real progress!**")

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
                new_metric_type = st.selectbox("Metric", ["time_min", "distance_mi", "weight_lbs", "reps", "sets"], 
                                              index=["time_min", "distance_mi", "weight_lbs", "reps", "sets"].index(edit_metric) if edit_metric in ["time_min", "distance_mi", "weight_lbs", "reps", "sets"] else 0)
                new_target_value = st.number_input("Target Value", min_value=0.1, step=0.1, value=float(edit_value))
                new_target_date = st.date_input("Target Date", value=edit_date)

                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("💾 Save Changes", type="primary"):
                        try:
                            cur.execute(
                                "UPDATE goals SET exercise = %s, metric_type = %s, target_value = %s, target_date = %s WHERE id = %s AND user_id = %s",
                                (new_exercise, new_metric_type, new_target_value, new_target_date, edit_id, st.session_state.user_id))
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
        # Load goals with linked workout data
        goals_query = """
            SELECT g.id, g.exercise, g.metric_type, g.target_value, g.target_date, g.created_at,
                   COUNT(we.id) as linked_workouts,
                   MAX(CASE 
                       WHEN g.metric_type = 'reps' THEN we.reps
                       WHEN g.metric_type = 'sets' THEN we.sets
                       WHEN g.metric_type = 'weight_lbs' THEN we.weight_lbs
                       WHEN g.metric_type = 'time_min' THEN we.time_min
                       WHEN g.metric_type = 'distance_mi' THEN we.distance_mi
                   END) as best_value
            FROM goals g
            LEFT JOIN workout_exercises we ON g.id = we.goal_id
            WHERE g.user_id = %s
            GROUP BY g.id, g.exercise, g.metric_type, g.target_value, g.target_date, g.created_at
            ORDER BY g.target_date
        """
        df_goals = pd.read_sql(goals_query, conn, params=(st.session_state.user_id,))

        if not df_goals.empty:
            df_goals['target_date'] = pd.to_datetime(df_goals['target_date']).dt.date
            df_goals['target_value'] = pd.to_numeric(df_goals['target_value'], errors='coerce')
            df_goals['best_value'] = pd.to_numeric(df_goals['best_value'], errors='coerce')
        
        # ──── DISPLAY ACTIVE GOALS ────
        df_active = df_goals[df_goals['target_date'] >= date.today()].copy()
        
        st.subheader("Active Goals")
        if not df_active.empty:
            for _, row in df_active.iterrows():
                goal_id = row['id']
                exercise = row['exercise']
                metric = row['metric_type']
                target = row['target_value']
                best = row['best_value'] if not pd.isna(row['best_value']) else 0
                linked_count = int(row['linked_workouts'])
                
                days_left = (row['target_date'] - date.today()).days
                status = "🟢 On Track" if days_left > 7 else "🟡 Urgent" if days_left >= 0 else "🔴 Overdue"
                
                # Calculate progress percentage
                if best > 0 and target > 0:
                    progress_pct = min((best / target) * 100, 100)
                else:
                    progress_pct = 0
                
                with st.container(border=True):
                    col_display, col_buttons = st.columns([5, 1])

                    with col_display:
                        st.markdown(f"**{exercise}**")
                        
                        metric_label = metric.replace('_', ' ').title()
                        st.caption(f"**Goal:** {target:.1f} {metric_label}")
                        
                        if best > 0:
                            st.caption(f"**Best:** {best:.1f} {metric_label} | **Linked Workouts:** {linked_count}")
                        else:
                            st.caption(f"**Best:** No linked workouts yet | **Link workouts** when logging to track progress!")
                        
                        st.caption(f"**Due:** {row['target_date'].strftime('%b %d, %Y')} ({days_left} days) | **Status:** {status}")
                        
                        # Progress bar
                        progress_label = f"Progress: {progress_pct:.0f}%"
                        if progress_pct >= 100:
                            progress_label += " ⭐ ACHIEVED!"
                        elif progress_pct >= 75:
                            progress_label += " 🔥"
                        st.caption(progress_label)
                        st.progress(progress_pct / 100)

                    with col_buttons:
                        if st.button("✏️", key=f"edit_{goal_id}", help="Edit goal", use_container_width=True):
                            st.session_state.editing_goal_id = goal_id
                            st.rerun()

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
            
        st.markdown("---")

    except Exception as e:
        st.error(f"Error loading goals: {e}")
    finally:
        if st.session_state.editing_goal_id is None:
            cur.close()
            conn.close()

    # ───── ADD GOAL FORM ─────
    st.subheader("Add New Goal")
    
    # Initialize session state for goal form
    if 'new_goal_category' not in st.session_state:
        st.session_state.new_goal_category = None
    
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
                
                # Exercise name
                exercise_name = st.text_input("Exercise Name (e.g., 'Morning Run', '5K Training')")
                
                # Metric selection
                metric = st.selectbox("What do you want to improve?", ["distance_mi", "time_min"], format_func=lambda x: "Distance (miles)" if x == "distance_mi" else "Time (minutes)")
                
                # Target value
                target_value = st.number_input(f"Target {metric.replace('_', ' ').title()}", min_value=0.1, step=0.1, value=1.0 if metric == "distance_mi" else 10.0)
                
                # Target date
                target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30))
                
                submitted = st.form_submit_button("Add Goal", type="primary")
                
                if submitted:
                    if not exercise_name:
                        st.error("Please enter an exercise name.")
                    else:
                        full_name = f"Cardio - {sub_category}: {exercise_name}"
                        
                        conn_add = get_conn()
                        cur_add = conn_add.cursor()
                        try:
                            cur_add.execute(
                                "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                                (st.session_state.user_id, full_name, metric, target_value, target_date)
                            )
                            conn_add.commit()
                            st.success("Cardio goal added! Link your workouts to this goal when logging to track progress.")
                            st.session_state.new_goal_category = None
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
            with st.form("add_goal"):
                # Sub-category
                sub_category = st.selectbox("Type", ["Free-Weights", "Machine", "Body-Weights"])
                
                # Exercise name
                exercise_name = st.text_input("Exercise Name (e.g., 'Push-ups', 'Bench Press')")
                
                # Metric selection
                metric = st.selectbox("What do you want to improve?", ["reps", "sets", "weight_lbs"], 
                                     format_func=lambda x: "Reps" if x == "reps" else "Sets" if x == "sets" else "Weight (lbs)")
                
                # Target value
                if metric == "weight_lbs":
                    target_value = st.number_input("Target Weight (lbs)", min_value=1.0, step=5.0, value=100.0)
                else:
                    target_value = st.number_input(f"Target {metric.title()}", min_value=1, step=1, value=10)
                
                # Target date
                target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30))
                
                submitted = st.form_submit_button("Add Goal", type="primary")
                
                if submitted:
                    if not exercise_name:
                        st.error("Please enter an exercise name.")
                    else:
                        full_name = f"Weights - {sub_category}: {exercise_name}"
                        
                        conn_add = get_conn()
                        cur_add = conn_add.cursor()
                        try:
                            cur_add.execute(
                                "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                                (st.session_state.user_id, full_name, metric, target_value, target_date)
                            )
                            conn_add.commit()
                            st.success("Weight goal added! Link your workouts to this goal when logging to track progress.")
                            st.session_state.new_goal_category = None
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
                                (st.session_state.user_id, f"Free-Text: {goal_description}", 'reps', 1, target_date)
                            )
                            conn_add.commit()
                            st.success("Free-text goal added!")
                            st.session_state.new_goal_category = None
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
