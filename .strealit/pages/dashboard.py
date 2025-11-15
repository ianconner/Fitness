# pages/dashboard.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import date
import numpy as np

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def parse_exercise_name(exercise_str):
    """Parse 'Cardio - Running: 5K Trail' → category, sub_category, name"""
    if not exercise_str or not isinstance(exercise_str, str):
        return None, None, exercise_str or ""
    parts = [p.strip() for p in exercise_str.split(":")]
    name = parts[-1]
    if " - " in exercise_str:
        cat_sub = exercise_str.split(" - ", 1)[0]
        if " - " in cat_sub:
            cat, sub = cat_sub.split(" - ", 1)
            return cat, sub, name
        else:
            return cat_sub, None, name
    return None, None, name

def main():
    st.markdown("## Dashboard")
    st.markdown("Your fitness journey at a glance.")

    conn = get_conn()
    cur = conn.cursor()

    try:
        # === WORKOUTS ===
        cur.execute("""
            SELECT w.id, w.workout_date, w.duration_min, w.notes,
                   we.id as ex_id, we.exercise, we.sets, we.reps, we.weight_lbs, we.time_min, we.distance_mi, we.rest_min, we.notes as ex_notes
            FROM workouts w
            LEFT JOIN workout_exercises we ON w.id = we.workout_id
            WHERE w.user_id = %s
            ORDER BY w.workout_date DESC
        """, (st.session_state.user_id,))
        rows = cur.fetchall()
        df_workouts = pd.DataFrame(rows, columns=[
            'workout_id', 'workout_date', 'duration_min', 'notes', 'ex_id', 'exercise', 'sets', 'reps',
            'weight_lbs', 'time_min', 'distance_mi', 'rest_min', 'ex_notes'
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

    # === DATA PROCESSING ===
    if not df_workouts.empty:
        cardio_keywords = ['run', 'running', 'walk', 'walking', 'elliptical', 'rowing', 'swim', 'cycling', 'bike']
        def classify_exercise(ex):
            if pd.isna(ex): return 'Other'
            return 'Cardio' if any(k in ex.lower() for k in cardio_keywords) else 'Weight'
        df_workouts['type'] = df_workouts['exercise'].apply(classify_exercise)

        for col in ['weight_lbs', 'time_min', 'distance_mi', 'sets', 'reps', 'rest_min']:
            df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
        df_workouts['distance_mi'] = df_workouts['distance_mi'].replace(0, np.nan)

        # CORRECT PACE: distance / ((time + rest) * reps)
        df_workouts['total_effort'] = (df_workouts['time_min'] + df_workouts['rest_min']) * df_workouts['reps']
        df_workouts['pace_min_mi'] = df_workouts['distance_mi'] / df_workouts['total_effort'].replace(0, np.nan)

        for col in ['weight_lbs', 'time_min', 'distance_mi', 'pace_min_mi']:
            df_workouts[col] = df_workouts[col].round(2).astype(str).replace(['0.0', '0', 'nan', 'inf', '<NA>'], '-')
        for col in ['sets', 'reps', 'rest_min']:
            df_workouts[col] = df_workouts[col].astype(str).replace(['0.0', '0', 'nan', '<NA>'], '-')

        # === METRICS ===
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

        # === RECENT WORKOUTS ===
        st.subheader("Recent Workouts")
        if "editing_workout_id" not in st.session_state:
            st.session_state.editing_workout_id = None

        sessions = df_workouts[['workout_id', 'workout_date', 'duration_min', 'notes']].drop_duplicates().sort_values('workout_date', ascending=False).head(5)

        if not sessions.empty:
            for idx, session in sessions.iterrows():
                col_left, col_right = st.columns(2)
                with col_left:
                    with st.container(border=True):
                        session_date = session['workout_date'].strftime('%b %d, %Y')
                        session_duration = session['duration_min']
                        session_notes = session['notes']
                        session_id = session['workout_id']
                        
                        st.markdown(f"#### {session_date}")
                        st.caption(f"**Duration:** {session_duration} min | **Notes:** {session_notes}")
                        
                        session_exercises = df_workouts[df_workouts['workout_id'] == session_id]
                        cardio_df = session_exercises[session_exercises['type'] == 'Cardio']
                        weight_df = session_exercises[session_exercises['type'] == 'Weight']

                        if not cardio_df.empty:
                            st.markdown("##### Cardio")
                            st.dataframe(
                                cardio_df[['exercise', 'time_min', 'distance_mi', 'pace_min_mi']].rename(
                                    columns={'time_min': 'Time (min)', 'distance_mi': 'Distance (mi)', 'pace_min_mi': 'Pace (min/mi)'}
                                ).set_index('exercise'),
                                use_container_width=True
                            )
                        if not weight_df.empty:
                            st.markdown("##### Weight Training")
                            st.dataframe(
                                weight_df[['exercise', 'weight_lbs', 'sets', 'reps', 'rest_min']].rename(
                                    columns={'weight_lbs': 'Weight (lbs)', 'sets': 'Sets', 'reps': 'Reps', 'rest_min': 'Rest (min)'}
                                ).set_index('exercise'),
                                use_container_width=True
                            )
                        
                        col_edit, col_delete = st.columns(2)
                        with col_edit:
                            if st.button("Edit", key=f"edit_{session_id}"):
                                st.session_state.editing_workout_id = session_id
                                st.rerun()
                        with col_delete:
                            if st.button("Delete", key=f"del_{session_id}", type="secondary"):
                                if st.button("Confirm Delete", key=f"confirm_del_{session_id}"):
                                    conn_del = get_conn()
                                    cur_del = conn_del.cursor()
                                    try:
                                        cur_del.execute("DELETE FROM workout_exercises WHERE workout_id = %s", (session_id,))
                                        cur_del.execute("DELETE FROM workouts WHERE id = %s AND user_id = %s", (session_id, st.session_state.user_id))
                                        conn_del.commit()
                                        st.success("Deleted!")
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                                    finally:
                                        cur_del.close()
                                        conn_del.close()
                                    st.rerun()

                with col_right:
                    if idx % 2 == 1: st.empty()

            # === FULL EDIT MODE (Mirror Log Workout) ===
            if st.session_state.editing_workout_id:
                workout_id = st.session_state.editing_workout_id
                edit_session = sessions[sessions['workout_id'] == workout_id].iloc[0]

                with st.expander(f"Edit Workout: {edit_session['workout_date'].strftime('%b %d, %Y')}", expanded=True):
                    edit_date = st.date_input("Date", value=edit_session['workout_date'])
                    edit_notes = st.text_area("Notes", value=edit_session['notes'])
                    edit_duration = st.number_input("Duration (min)", min_value=1, value=int(edit_session['duration_min']))

                    # Load exercises
                    conn_edit = get_conn()
                    cur_edit = conn_edit.cursor()
                    cur_edit.execute("SELECT id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi, notes FROM workout_exercises WHERE workout_id = %s", (workout_id,))
                    rows = cur_edit.fetchall()
                    edit_exercises = []
                    for row in rows:
                        ex_id, ex_name, sets, reps, weight, time, rest, dist, notes = row
                        cat, sub, name = parse_exercise_name(ex_name)
                        edit_exercises.append({
                            "id": ex_id, "category": cat, "sub_category": sub, "base_name": name,
                            "sets": int(sets or 1), "reps": int(reps or 1), "weight_lbs": float(weight or 0),
                            "time_min": float(time or 0), "rest_min": float(rest or 0), "distance_mi": float(dist or 0),
                            "notes": notes or "", "previous_category": cat
                        })

                    if not edit_exercises:
                        edit_exercises = [{"id": None, "category": None, "sub_category": None, "base_name": "", "sets": 1, "reps": 1, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0, "notes": "", "previous_category": None}]

                    # === EDIT FORM (Same as Log Workout) ===
                    for i, ex in enumerate(edit_exercises):
                        with st.container(border=True):
                            st.markdown(f"**Exercise {i+1}**")
                            cat_key = f"edit_cat_{i}"
                            prev_cat = ex.get("previous_category")
                            cat_options = ["", "Cardio", "Weights", "Free-Text"]
                            cat_index = cat_options.index(ex["category"]) if ex["category"] in cat_options else 0
                            selected_cat = st.selectbox("Category", cat_options, index=cat_index, key=cat_key)
                            if prev_cat != selected_cat:
                                ex["sub_category"] = None
                                ex["previous_category"] = selected_cat
                            ex["category"] = selected_cat

                            sub_cat = ""
                            if ex["category"] == "Cardio":
                                sub_opts = ["Running", "Walking", "Elliptical", "Other"]
                                sub_idx = sub_opts.index(ex["sub_category"]) if ex["sub_category"] in sub_opts else 0
                                sub_cat = st.selectbox("Sub-Category", sub_opts, index=sub_idx, key=f"edit_sub_{i}")
                            elif ex["category"] == "Weights":
                                sub_opts = ["Free-Weights", "Machine", "Body-Weights"]
                                sub_idx = sub_opts.index(ex["sub_category"]) if ex["sub_category"] in sub_opts else 0
                                sub_cat = st.selectbox("Sub-Category", sub_opts, index=sub_idx, key=f"edit_sub_{i}")
                            ex["sub_category"] = sub_cat

                            if ex["category"] == "Cardio":
                                ex["reps"] = st.number_input("Reps/Intervals", min_value=1, value=ex["reps"], key=f"edit_reps_{i}")
                                if ex["reps"] > 1:
                                    ex["rest_min"] = st.number_input("Rest (min)", min_value=0.0, value=ex["rest_min"], key=f"edit_rest_{i}", step=0.5)
                                col_t, col_d = st.columns(2)
                                with col_t:
                                    ex["time_min"] = st.number_input("Time (min)", min_value=0.0, value=ex["time_min"], key=f"edit_time_{i}", step=0.5)
                                with col_d:
                                    ex["distance_mi"] = st.number_input("Distance (mi)", min_value=0.0, value=ex["distance_mi"], key=f"edit_dist_{i}", step=0.1)
                                total_effort = (ex["time_min"] + ex["rest_min"]) * ex["reps"]
                                pace = total_effort / ex["distance_mi"] if ex["distance_mi"] > 0 else 0
                                st.caption(f"**Pace: {pace:.2f} min/mi**" if ex["distance_mi"] > 0 else "**Pace: -**")
                                ex["sets"] = 1; ex["weight_lbs"] = 0.0
                            elif ex["category"] == "Weights":
                                ex["sets"] = st.number_input("Sets", min_value=1, value=ex["sets"], key=f"edit_sets_{i}")
                                ex["reps"] = st.number_input("Reps", min_value=1, value=ex["reps"], key=f"edit_reps_{i}")
                                ex["weight_lbs"] = st.number_input("Weight (lbs)", min_value=0.0, value=ex["weight_lbs"], key=f"edit_weight_{i}", step=5.0)
                                ex["rest_min"] = st.number_input("Rest (min)", min_value=0.0, value=ex["rest_min"], key=f"edit_rest_{i}", step=0.5)
                                ex["time_min"] = ex["distance_mi"] = 0.0
                            elif ex["category"] == "Free-Text":
                                ex["base_name"] = st.text_area("Full Description", value=ex["base_name"], key=f"edit_free_{i}")
                                ex["time_min"] = st.number_input("Time (min)", min_value=0.0, value=ex["time_min"], key=f"edit_free_time_{i}", step=0.5)
                                ex["sets"] = ex["reps"] = 1; ex["weight_lbs"] = ex["distance_mi"] = ex["rest_min"] = 0.0
                            else:
                                st.info("Select category to edit.")

                            with st.expander("Details", expanded=True):
                                base_name = st.text_input("Specific Name", value=ex["base_name"], key=f"edit_name_{i}")
                                full_name = f"{ex['category']} - {ex['sub_category']}: {base_name}".strip(": ") if ex["category"] and ex["sub_category"] else base_name
                                ex["base_name"] = base_name
                                ex["exercise"] = full_name
                                ex["notes"] = st.text_area("Notes", value=ex["notes"], key=f"edit_notes_{i}")

                            st.divider()

                    col_add, col_rem = st.columns(2)
                    with col_add:
                        if st.button("Add Exercise", key=f"add_edit_{i}"):
                            edit_exercises.append({"id": None, "category": None, "sub_category": None, "base_name": "", "sets": 1, "reps": 1, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0, "notes": "", "previous_category": None})
                            st.rerun()
                    with col_rem:
                        if len(edit_exercises) > 1 and st.button("Remove Last", key=f"rem_edit_{i}"):
                            edit_exercises.pop()
                            st.rerun()

                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("Save Changes", type="primary"):
                            try:
                                cur_up = conn_edit.cursor()
                                cur_up.execute("UPDATE workouts SET workout_date=%s, notes=%s, duration_min=%s WHERE id=%s AND user_id=%s",
                                               (edit_date, edit_notes, edit_duration, workout_id, st.session_state.user_id))
                                cur_up.execute("DELETE FROM workout_exercises WHERE workout_id = %s", (workout_id,))
                                for ex in edit_exercises:
                                    if ex["exercise"].strip() and ex["category"]:
                                        cur_up.execute("""
                                            INSERT INTO workout_exercises 
                                            (workout_id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi, notes)
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        """, (workout_id, ex["exercise"], ex["sets"], ex["reps"], ex["weight_lbs"], ex["time_min"], ex["rest_min"], ex["distance_mi"], ex["notes"]))
                                conn_edit.commit()
                                st.success("Updated!")
                                st.session_state.editing_workout_id = None
                                st.rerun()
                            except Exception as e:
                                conn_edit.rollback()
                                st.error(f"Error: {e}")
                            finally:
                                cur_edit.close()
                                conn_edit.close()
                    with col_cancel:
                        if st.button("Cancel"):
                            st.session_state.editing_workout_id = None
                            st.rerun()

        else:
            st.info("No workouts yet.")
    else:
        st.info("No workouts yet.")

    # === GOALS ===
    st.subheader("Active Goals")
    if not df_goals.empty:
        df_goals["target_date"] = pd.to_datetime(df_goals["target_date"])
        df_goals["Days Left"] = (df_goals["target_date"] - pd.Timestamp(date.today())).dt.days
        df_goals["Status"] = df_goals["Days Left"].apply(lambda x: "On Track" if x > 7 else "Urgent" if x >= 0 else "Overdue")
        for _, row in df_goals.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{row['exercise']}**")
                    metric = row['metric_type'].replace('_', ' ').title()
                    st.caption(f"Goal: {row['target_value']} {metric}")
                with col2:
                    st.markdown(f"**{row['Status']}**")
                    st.caption(f"{row['Days Left']} days left")
    else:
        st.info("No active goals.")
