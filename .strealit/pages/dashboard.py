# pages/dashboard.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import date
import plotly.express as px
import numpy as np

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def main():
    st.markdown("## Dashboard")
    st.markdown("Your fitness journey at a glance.")

    conn = get_conn()
    cur = conn.cursor()

    try:
        # === WORKOUTS ===
        cur.execute("""
            SELECT w.id, w.workout_date, w.duration_min, w.notes,
                   we.id as ex_id, we.exercise, we.sets, we.reps, we.weight_lbs, we.time_min, we.distance_mi, we.rest_min
            FROM workouts w
            LEFT JOIN workout_exercises we ON w.id = we.workout_id
            WHERE w.user_id = %s
            ORDER BY w.workout_date DESC
        """, (st.session_state.user_id,))
        rows = cur.fetchall()
        df_workouts = pd.DataFrame(rows, columns=[
            'workout_id', 'workout_date', 'duration_min', 'notes', 'ex_id', 'exercise', 'sets', 'reps',
            'weight_lbs', 'time_min', 'distance_mi', 'rest_min'
        ])

        # === GOALS ===
        cur.execute("""
            SELECT exercise, metric_type, target_value, target_date
            FROM goals
            WHERE user_id = %s AND target_date >= %s
            ORDER BY target_date
        """, (st.session_state.user_id, date.today()))
        goals_rows = cur.fetchall()
        df_goals = pd.DataFrame(goals_rows, columns=['exercise', 'metric_type', 'target_value', 'target_date'])

    finally:
        conn.close()

    # === WORKOUT DATA PROCESSING FOR DISPLAY ===
    if not df_workouts.empty:
        
        # 1. Define exercise categorization logic
        cardio_keywords = ['run', 'running', 'walk', 'walking', 'elliptical', 'rowing', 'swim', 'cycling', 'bike']
        
        def classify_exercise(exercise):
            if pd.isna(exercise):
                return 'Other'
            if any(keyword in exercise.lower() for keyword in cardio_keywords):
                return 'Cardio'
            return 'Weight'
            
        df_workouts['type'] = df_workouts['exercise'].apply(classify_exercise)
        
        # === FIX for TypeError and DivisionByZero ===
        # 1. Convert ALL relevant columns to numeric first, handling errors.
        for col in ['weight_lbs', 'time_min', 'distance_mi', 'sets', 'reps', 'rest_min']:
             df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
        
        # 2. Replace 0 with NaN in 'distance_mi' to prevent division by zero
        df_workouts['distance_mi'] = df_workouts['distance_mi'].replace(0, np.nan)
        
        # 3. Calculate Pace for Cardio (Pace = Time / Distance)
        df_workouts['pace_min_mi'] = (df_workouts['time_min'] / df_workouts['distance_mi'])
        
        # 4. Format numeric columns for clean display (replace 0/NaN/inf with '-')
        # Now that all are numeric, .round() will work.
        for col in ['weight_lbs', 'time_min', 'distance_mi', 'pace_min_mi']:
            df_workouts[col] = df_workouts[col].round(2).astype(str).replace(['0.0', '0', 'nan', 'inf', '<NA>'], '-')
        
        for col in ['sets', 'reps', 'rest_min']:
             df_workouts[col] = df_workouts[col].astype(str).replace(['0.0', '0', 'nan', '<NA>'], '-')
             
        # === DISPLAY ===
        col1, col2, col3 = st.columns(3)
        with col1:
            total_workouts = len(df_workouts.drop_duplicates('workout_id'))
            st.metric("Total Workouts", total_workouts)
        with col2:
            total_duration = pd.to_numeric(df_workouts['duration_min'], errors='coerce').sum()
            st.metric("Total Time", f"{int(total_duration)} min")
        with col3:
            avg_duration = pd.to_numeric(df_workouts.groupby('workout_id')['duration_min'].sum(), errors='coerce').mean()
            st.metric("Avg Duration", f"{int(avg_duration)} min")

        # === ENHANCED RECENT WORKOUTS (Grid Layout + Popup Edit/Delete) ===
        st.subheader("Recent Workouts")
        if "editing_workout_id" not in st.session_state:
            st.session_state.editing_workout_id = None
        if "confirm_delete_id" not in st.session_state:
            st.session_state.confirm_delete_id = None

        sessions = df_workouts[['workout_id', 'workout_date', 'duration_min', 'notes']].drop_duplicates().sort_values('workout_date', ascending=False).head(5)

        if not sessions.empty:
            # 2-Column Grid for Cards
            for idx, session in sessions.iterrows():
                col_left, col_right = st.columns(2)
                with col_left:
                    with st.container(border=True):
                        session_date = session['workout_date'].strftime('%b %d, %Y')
                        session_duration = session['duration_min']
                        session_notes = session['notes']
                        session_id = session['workout_id']
                        
                        st.markdown(f"#### 🗓️ {session_date}")
                        st.caption(f"**Duration:** {session_duration} min | **Notes:** {session_notes}")
                        
                        session_exercises = df_workouts[df_workouts['workout_id'] == session_id]
                        
                        cardio_df = session_exercises[session_exercises['type'] == 'Cardio']
                        weight_df = session_exercises[session_exercises['type'] == 'Weight']

                        if not cardio_df.empty:
                            st.markdown("##### 🏃 Cardio")
                            st.dataframe(
                                cardio_df[['exercise', 'time_min', 'distance_mi', 'pace_min_mi']].rename(
                                    columns={'time_min': 'Time (min)', 'distance_mi': 'Distance (mi)', 'pace_min_mi': 'Pace (min/mi)'}
                                ).set_index('exercise'),
                                width=400, use_container_width=True
                            )

                        if not weight_df.empty:
                            st.markdown("##### 💪 Weight Training")
                            st.dataframe(
                                weight_df[['exercise', 'weight_lbs', 'sets', 'reps', 'rest_min']].rename(
                                    columns={'weight_lbs': 'Weight (lbs)', 'sets': 'Sets', 'reps': 'Reps', 'rest_min': 'Rest (min)'}
                                ).set_index('exercise'),
                                width=400, use_container_width=True
                            )
                        
                        # Edit/Delete Buttons
                        col_edit, col_delete = st.columns(2)
                        with col_edit:
                            if st.button("✏️ Edit", key=f"edit_{session_id}"):
                                st.session_state.editing_workout_id = session_id
                                st.session_state.confirm_delete_id = None
                                st.rerun()
                        with col_delete:
                            if st.button("🗑️ Delete", key=f"del_{session_id}", type="secondary"):
                                if st.session_state.editing_workout_id != session_id:  # Prevent during edit
                                    st.session_state.confirm_delete_id = session_id
                                    st.session_state.editing_workout_id = None
                                    st.rerun()

                with col_right:
                    if idx % 2 == 1:  # Spacer for even grid
                        st.empty()

            # Confirm Delete Dialog
            if st.session_state.confirm_delete_id:
                st.warning("Are you sure you want to delete this workout? This can't be undone.")
                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("Confirm Delete"):
                        session_id = st.session_state.confirm_delete_id
                        conn_del = get_conn()
                        cur_del = conn_del.cursor()
                        try:
                            cur_del.execute("DELETE FROM workout_exercises WHERE workout_id = %s", (session_id,))
                            cur_del.execute("DELETE FROM workouts WHERE id = %s AND user_id = %s", (session_id, st.session_state.user_id))
                            conn_del.commit()
                            st.success("Workout deleted!")
                        except Exception as e:
                            st.error(f"Error: {e}")
                        finally:
                            cur_del.close()
                            conn_del.close()
                            st.session_state.confirm_delete_id = None
                            st.rerun()
                with col_cancel:
                    if st.button("Cancel"):
                        st.session_state.confirm_delete_id = None
                        st.rerun()

            # === POPUP EDIT MODE (Expander as Modal) ===
            if st.session_state.editing_workout_id:
                with st.expander(f"✏️ Edit Workout: {sessions[sessions['workout_id'] == st.session_state.editing_workout_id]['workout_date'].iloc[0].strftime('%b %d, %Y')}", expanded=True):
                    edit_session = sessions[sessions['workout_id'] == st.session_state.editing_workout_id].iloc[0]
                    edit_date = st.date_input("Date", value=edit_session['workout_date'])
                    edit_notes = st.text_area("Notes", value=edit_session['notes'])
                    edit_duration = st.number_input("Duration (min)", min_value=1, value=edit_session['duration_min'])

                    # Fetch and edit exercises
                    conn_edit = get_conn()
                    cur_edit = conn_edit.cursor()
                    cur_edit.execute("SELECT * FROM workout_exercises WHERE workout_id = %s", (st.session_state.editing_workout_id,))
                    edit_ex_rows = cur_edit.fetchall()
                    edit_exercises = [{"id": row[0], "exercise": row[2], "sets": row[3], "reps": row[4], "weight_lbs": row[5], "time_min": row[6], "rest_min": row[7], "distance_mi": row[8]} for row in edit_ex_rows]

                    if not edit_exercises:
                        edit_exercises = [{"id": None, "exercise": "", "sets": 3, "reps": 10, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0}]

                    for i, ex in enumerate(edit_exercises):
                        st.markdown(f"**Exercise {i+1}**")
                        col1, col2, col3 = st.columns([2,1,1])
                        with col1: 
                            ex["exercise"] = st.text_input("Name", value=ex["exercise"], key=f"edit_name_{i}")
                        
                        # Weight Training
                        col_w1, col_w2, col_w3, col_w4 = st.columns(4)
                        with col_w1:
                            ex["weight_lbs"] = st.number_input("Weight (lbs)", min_value=0.0, value=ex["weight_lbs"], key=f"edit_weight_{i}", step=5.0)
                        with col_w2: 
                            ex["sets"] = st.number_input("Sets", min_value=1, value=ex["sets"], key=f"edit_sets_{i}")
                        with col_w3: 
                            ex["reps"] = st.number_input("Reps", min_value=1, value=ex["reps"], key=f"edit_reps_{i}")
                        with col_w4:
                            ex["rest_min"] = st.number_input("Rest (min)", min_value=0.0, value=ex["rest_min"], key=f"edit_rest_{i}", step=0.5)

                        # Cardio
                        col_c1, col_c2 = st.columns(2)
                        with col_c1:
                            ex["distance_mi"] = st.number_input("Distance (mi)", min_value=0.0, value=ex["distance_mi"], key=f"edit_dist_{i}", step=0.1)
                        with col_c2:
                            ex["time_min"] = st.number_input("Time (min)", min_value=0.0, value=ex["time_min"], key=f"edit_time_{i}", step=1.0)
                        
                        st.divider()

                    col_add, col_remove = st.columns(2)
                    with col_add:
                        if st.button("Add Exercise"):
                            edit_exercises.append({"id": None, "exercise": "", "sets": 3, "reps": 10, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0})
                            st.rerun()
                    with col_remove:
                        if len(edit_exercises) > 1 and st.button("Remove Last"):
                            edit_exercises.pop()
                            st.rerun()

                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("💾 Save Changes", type="primary"):
                            try:
                                cur_update = conn_edit.cursor()
                                # Update workout
                                cur_update.execute(
                                    "UPDATE workouts SET workout_date=%s, notes=%s, duration_min=%s WHERE id=%s AND user_id=%s",
                                    (edit_date, edit_notes, edit_duration, st.session_state.editing_workout_id, st.session_state.user_id)
                                )
                                
                                # Delete old exercises and insert new
                                cur_update.execute("DELETE FROM workout_exercises WHERE workout_id = %s", (st.session_state.editing_workout_id,))
                                for ex in edit_exercises:
                                    if ex["exercise"].strip():
                                        cur_update.execute(
                                            "INSERT INTO workout_exercises (workout_id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                                            (st.session_state.editing_workout_id, ex["exercise"], ex["sets"], ex["reps"], ex["weight_lbs"], ex["time_min"], ex["rest_min"], ex["distance_mi"])
                                        )
                                conn_edit.commit()
                                st.success("Workout updated!")
                                st.session_state.editing_workout_id = None
                                st.rerun()
                            except Exception as e:
                                conn_edit.rollback()
                                st.error(f"Error: {e}")
                            finally:
                                cur_edit.close()
                                conn_edit.close()
                    with col_cancel:
                        if st.button("❌ Cancel"):
                            st.session_state.editing_workout_id = None
                            st.rerun()

        else:
             st.info("No workouts yet.")
    else:
        st.info("No workouts yet.")

    
    st.subheader("Active Goals")
    if not df_goals.empty:
        
        df_goals["target_date"] = pd.to_datetime(df_goals["target_date"])
        df_goals["Days Left"] = (df_goals["target_date"] - pd.Timestamp(date.today())).dt.days
        
        df_goals["Status"] = df_goals["Days Left"].apply(
            lambda x: "🟢 On Track" if x > 7 else "🟡 Urgent" if x >= 0 else "🔴 Overdue"
        )
        
        for idx, row in df_goals.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{row['exercise']}**")
                    metric_display = row['metric_type'].replace('_', ' ').replace('lbs', 'LBs').replace('mi', 'Mi').title()
                    st.caption(f"Goal: {row['target_value']} {metric_display}")
                with col2:
                    st.markdown(f"**{row['Status']}**")
                    st.caption(f"{row['Days Left']} days left | Due {row['target_date'].strftime('%b %d')}")
            st.write("") 
            
    else:
        st.info("No active goals.")
