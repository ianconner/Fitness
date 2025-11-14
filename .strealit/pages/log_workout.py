# pages/log_workout.py
import streamlit as st
import psycopg2
from datetime import date

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def main():
    st.markdown("## Log Workout")

    with st.form("log_workout_form", clear_on_submit=True):
        workout_date = st.date_input("Date", value=date.today())
        notes = st.text_area("Notes")
        duration_min = st.number_input("Duration (min)", min_value=1, value=30)

        exercises = st.session_state.get("exercises", [])
        if not exercises:
            exercises = [{"exercise": "", "sets": 3, "reps": 10, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0}]

        for i, ex in enumerate(exercises):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([3,1,1,1,1,1,1])
            with col1: ex["exercise"] = st.text_input(f"Exercise {i+1}", value=ex["exercise"], key=f"name_{i}")
            with col2: ex["sets"] = st.number_input("Sets", min_value=1, value=ex["sets"], key=f"sets_{i}")
            with col3: ex["reps"] = st.number_input("Reps", min_value=1, value=ex["reps"], key=f"reps_{i}")
            with col4: ex["weight_lbs"] = st.number_input("Weight", min_value=0.0, value=ex["weight_lbs"], key=f"weight_{i}")
            with col5: ex["time_min"] = st.number_input("Time", min_value=0.0, value=ex["time_min"], key=f"time_{i}")
            with col6: ex["rest_min"] = st.number_input("Rest", min_value=0.0, value=ex["rest_min"], key=f"rest_{i}")
            with col7: ex["distance_mi"] = st.number_input("Dist", min_value=0.0, value=ex["distance_mi"], key=f"dist_{i}")

        col_add, col_remove = st.columns(2)
        with col_add:
            if st.form_submit_button("Add Exercise"):
                exercises.append({"exercise": "", "sets": 3, "reps": 10, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0})
                st.session_state.exercises = exercises
                st.rerun()
        with col_remove:
            if len(exercises) > 1 and st.form_submit_button("Remove Last"):
                exercises.pop()
                st.session_state.exercises = exercises
                st.rerun()

        if st.form_submit_button("Save Workout", type="primary"):
            if not any(ex["exercise"].strip() for ex in exercises):
                st.error("Add at least one exercise.")
            elif not notes.strip():
                st.error("Add notes.")
            else:
                conn = get_conn()
                cur = conn.cursor()
                try:
                    cur.execute(
                        "INSERT INTO workouts (user_id, workout_date, notes, duration_min) VALUES (%s, %s, %s, %s) RETURNING id",
                        (st.session_state.user_id, workout_date, notes, duration_min)
                    )
                    workout_id = cur.fetchone()[0]

                    for ex in exercises:
                        if ex["exercise"].strip():
                            cur.execute(
                                "INSERT INTO workout_exercises (workout_id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                                (workout_id, ex["exercise"], ex["sets"], ex["reps"], ex["weight_lbs"], ex["time_min"], ex["rest_min"], ex["distance_mi"])
                            )
                    conn.commit()
                    st.success("Saved!")
                    st.session_state.pop("exercises", None)
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error: {e}")
                finally:
                    conn.close()
