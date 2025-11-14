# pages/goals.py
import streamlit as st
from datetime import date, timedelta
import psycopg2
import pandas as pd
import time

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def main():
    st.markdown("## Goals")
    st.markdown("Set **compound goals** like *Run 2 miles in 18 minutes*")

    # Initialize session state for form submission
    if 'goal_submitted' not in st.session_state:
        st.session_state.goal_submitted = False
    if 'editing_goal_id' not in st.session_state:
        st.session_state.editing_goal_id = None

    # ——— ADD GOAL FORM ———
    st.subheader("Add New Goal")
    
    exercise = st.text_input("Exercise", placeholder="Run, Squat, Push-up", key="goal_exercise")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        metric_type = st.selectbox("Metric", ["time_min", "reps", "weight_lbs", "distance_mi"], key="goal_metric")
    
    with col2:
        if metric_type == "time_min":
            distance = st.number_input("Distance (mi)", min_value=0.1, step=0.1, value=2.0, key="goal_distance")
            target_value = st.number_input("Time (min)", min_value=0.1, step=0.5, value=18.0, key="goal_value")
            pace = target_value / distance
            st.caption(f"**Pace: {pace:.2f} min/mi**")
        elif metric_type == "reps":
            target_value = st.number_input("Reps", min_value=1.0, step=1.0, value=10.0, key="goal_value")
        elif metric_type == "weight_lbs":
            target_value = st.number_input("Weight (lbs)", min_value=0.1, step=5.0, value=135.0, key="goal_value")
        else:  # distance_mi
            target_value = st.number_input("Distance (mi)", min_value=0.1, step=0.1, value=5.0, key="goal_value")
    
    with col3:
        target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30), key="goal_date")

    # Button with callback
    def handle_submit():
        st.session_state.goal_submitted = True
    
    st.button("Add Goal", type="primary", use_container_width=True, on_click=handle_submit, key="add_goal_btn")

    # Process submission
    if st.session_state.goal_submitted:
        st.write(f"🔍 DEBUG: Submitting - exercise='{exercise}', metric={metric_type}, value={target_value}")
        
        if not exercise.strip():
            st.error("Please enter an exercise name.")
            st.session_state.goal_submitted = False
        else:
            conn = get_conn()
            cur = conn.cursor()
            try:
                # Check current count BEFORE insert
                cur.execute("SELECT COUNT(*) FROM goals WHERE user_id=%s", (st.session_state.user_id,))
                before_count = cur.fetchone()[0]
                st.write(f"🔍 DEBUG: Goals BEFORE insert: {before_count}")
                
                # Check all existing goals
                cur.execute("SELECT id, exercise FROM goals WHERE user_id=%s", (st.session_state.user_id,))
                existing = cur.fetchall()
                st.write(f"🔍 DEBUG: Existing goals: {existing}")
                
                st.write("🔍 DEBUG: Executing INSERT...")
                cur.execute(
                    "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                    (st.session_state.user_id, exercise, metric_type, target_value, target_date)
                )
                conn.commit()
                st.write("🔍 DEBUG: Committed!")
                
                # Verify count AFTER insert
                cur.execute("SELECT COUNT(*) FROM goals WHERE user_id=%s", (st.session_state.user_id,))
                count = cur.fetchone()[0]
                st.write(f"🔍 DEBUG: Goals AFTER insert: {count}")
                
                # Check all goals again
                cur.execute("SELECT id, exercise FROM goals WHERE user_id=%s", (st.session_state.user_id,))
                after = cur.fetchall()
                st.write(f"🔍 DEBUG: All goals after insert: {after}")
                
                st.success(f"✓ Goal added: {exercise}")
                st.session_state.goal_submitted = False
                st.balloons()
                
                st.warning("⚠️ Auto-refresh disabled - manually refresh page")
                
            except Exception as e:
                conn.rollback()
                st.error(f"Error adding goal: {e}")
                import traceback
                st.code(traceback.format_exc())
                st.session_state.goal_submitted = False
            finally:
                cur.close()
                conn.close()

    st.divider()

    # ——— DISPLAY GOALS ———
    st.subheader("Active Goals")
    
    # Temporary debug
    conn_debug = get_conn()
    cur_debug = conn_debug.cursor()
    cur_debug.execute("SELECT COUNT(*) FROM goals WHERE user_id=%s", (st.session_state.user_id,))
    total = cur_debug.fetchone()[0]
    st.write(f"🔍 DEBUG: Total goals in database for user {st.session_state.user_id}: {total}")
    cur_debug.close()
    conn_debug.close()
    
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, exercise, metric_type, target_value, target_date, created_at FROM goals WHERE user_id=%s ORDER BY target_date",
            (st.session_state.user_id,)
        )
        rows = cur.fetchall()
        
        st.write(f"🔍 DEBUG: Query returned {len(rows)} rows")
        if rows:
            for r in rows:
                st.write(f"🔍 DEBUG: Row - id={r[0]}, exercise={r[1]}, metric={r[2]}, value={r[3]}")
        
        if rows:
            df = pd.DataFrame(rows, columns=['id', 'exercise', 'metric_type', 'target_value', 'target_date', 'created_at'])
            
            # Calculate days left
            df["target_date"] = pd.to_datetime(df["target_date"])
            df["Days Left"] = (df["target_date"] - pd.Timestamp(date.today())).dt.days
            df["Progress"] = df["Days Left"].apply(
                lambda x: "🟢 On Track" if x > 7 else "🟡 Urgent" if x >= 0 else "🔴 Overdue"
            )
            
            # Display each goal
            for idx, row in df.iterrows():
                goal_id = row['id']
                
                # Check if this goal is being edited
                if st.session_state.editing_goal_id == goal_id:
                    # Edit mode
                    st.markdown(f"### ✏️ Editing: {row['exercise']}")
                    
                    edit_exercise = st.text_input("Exercise", value=row['exercise'], key=f"edit_ex_{goal_id}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        edit_metric = st.selectbox("Metric", ["time_min", "reps", "weight_lbs", "distance_mi"], 
                                                   index=["time_min", "reps", "weight_lbs", "distance_mi"].index(row['metric_type']),
                                                   key=f"edit_metric_{goal_id}")
                    with col2:
                        if edit_metric == "time_min":
                            st.text_input("Distance (mi)", value="2.0", disabled=True, help="For pace calculation")
                            edit_value = st.number_input("Time (min)", value=float(row['target_value']), min_value=0.1, step=0.1, key=f"edit_val_{goal_id}")
                        elif edit_metric == "reps":
                            edit_value = st.number_input("Reps", value=float(row['target_value']), min_value=1.0, step=1.0, key=f"edit_val_{goal_id}")
                        elif edit_metric == "weight_lbs":
                            edit_value = st.number_input("Weight (lbs)", value=float(row['target_value']), min_value=0.1, step=5.0, key=f"edit_val_{goal_id}")
                        else:  # distance_mi
                            edit_value = st.number_input("Distance (mi)", value=float(row['target_value']), min_value=0.1, step=0.1, key=f"edit_val_{goal_id}")
                    with col3:
                        edit_date = st.date_input("Target Date", value=row['target_date'].date(), key=f"edit_date_{goal_id}")
                    
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("💾 Save Changes", key=f"save_{goal_id}", use_container_width=True, type="primary"):
                            conn_edit = get_conn()
                            cur_edit = conn_edit.cursor()
                            try:
                                cur_edit.execute(
                                    "UPDATE goals SET exercise=%s, metric_type=%s, target_value=%s, target_date=%s WHERE id=%s AND user_id=%s",
                                    (edit_exercise, edit_metric, edit_value, edit_date, goal_id, st.session_state.user_id)
                                )
                                conn_edit.commit()
                                st.success("Goal updated!")
                                st.session_state.editing_goal_id = None
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                            finally:
                                cur_edit.close()
                                conn_edit.close()
                    with col_cancel:
                        if st.button("❌ Cancel", key=f"cancel_{goal_id}", use_container_width=True):
                            st.session_state.editing_goal_id = None
                            st.rerun()
                    
                    st.divider()
                else:
                    # Display mode
                    st.markdown(f"### {row['exercise']}")
                    
                    col_info, col_buttons = st.columns([5, 1])
                    with col_info:
                        st.write(f"**{row['metric_type'].replace('_', ' ').title()}:** {row['target_value']} | **Due:** {row['target_date'].strftime('%b %d, %Y')} | **Status:** {row['Progress']}")
                    
                    with col_buttons:
                        if st.button("✏️", key=f"edit_{goal_id}", help="Edit goal"):
                            st.session_state.editing_goal_id = goal_id
                            st.rerun()
                        if st.button("🗑️", key=f"delete_{goal_id}", help="Delete goal"):
                            conn_del = get_conn()
                            cur_del = conn_del.cursor()
                            try:
                                cur_del.execute("DELETE FROM goals WHERE id=%s AND user_id=%s", (goal_id, st.session_state.user_id))
                                conn_del.commit()
                                st.success("Goal deleted!")
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                            finally:
                                cur_del.close()
                                conn_del.close()
                    
                    st.divider()
        else:
            st.info("No goals yet. Add one above!")
            
    except Exception as e:
        st.error(f"Error loading goals: {e}")
    finally:
        cur.close()
        conn.close()
