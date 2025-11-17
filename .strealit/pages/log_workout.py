# pages/log_workout.py
import streamlit as st
import psycopg2
from datetime import date

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def main():
    st.markdown("## Log Workout")

    # Real-time section (outside form for reactivity)
    workout_date = st.date_input("Date", value=date.today())
    duration_min = st.number_input("Duration (min)", min_value=1, value=30)

    # Initialize exercises in session_state
    if "exercises" not in st.session_state:
        st.session_state.exercises = [{
            "category": None, "sub_category": None, "exercise": "", "sets": 1, "reps": 1,
            "weight_lbs": 0.0, "time_min": 0.0, "time_sec": 0, "rest_min": 1.5, "distance_mi": 0.0,
            "pace_min_mi": 0.0, "notes": "", "previous_category": None
        }]
    exercises = st.session_state.exercises

    # Fetch past exercise names for autocomplete
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT exercise FROM workout_exercises WHERE exercise IS NOT NULL")
        past_exercises = [row[0] for row in cur.fetchall() if row[0]]
        conn.close()
    except:
        past_exercises = []

    for i, ex in enumerate(exercises):
        with st.container(border=True):
            st.markdown(f"**Exercise {i+1}**")

            # Category
            category_key = f"cat_{i}"
            previous_category = ex.get("previous_category")
            selected_category = st.selectbox(
                "Category", ["", "Cardio", "Weights", "Free-Text"],
                index=0 if not ex.get("category") else (["Cardio", "Weights", "Free-Text"].index(ex["category"]) if ex["category"] in ["Cardio", "Weights", "Free-Text"] else 0),
                key=category_key
            )
            if previous_category != selected_category:
                ex["sub_category"] = None
                ex["previous_category"] = selected_category
            ex["category"] = selected_category

            # Sub-Category
            sub_category = ""
            if ex["category"]:
                if ex["category"] == "Cardio":
                    sub_options = ["Running", "Walking", "Elliptical", "Other"]
                    sub_index = 0 if not ex.get("sub_category") else sub_options.index(ex["sub_category"]) if ex["sub_category"] in sub_options else 0
                    sub_category = st.selectbox("Sub-Category", sub_options, index=sub_index, key=f"sub_{i}")
                elif ex["category"] == "Weights":
                    sub_options = ["Free-Weights", "Machine", "Body-Weights"]
                    sub_index = 0 if not ex.get("sub_category") else sub_options.index(ex["sub_category"]) if ex["sub_category"] in sub_options else 0
                    sub_category = st.selectbox("Sub-Category", sub_options, index=sub_index, key=f"sub_{i}")
                ex["sub_category"] = sub_category
            else:
                st.text("")

            # Conditional Inputs
            if ex["category"] == "Cardio":
                ex["reps"] = st.number_input("Reps/Intervals", min_value=1, value=ex["reps"], key=f"reps_{i}")
                if ex["reps"] > 1:
                    ex["rest_min"] = st.number_input("Rest Between Reps (min)", min_value=0.0, value=ex["rest_min"], key=f"rest_{i}", step=0.5)
                else:
                    ex["rest_min"] = 0.0

                # Time input in MM:SS format
                st.markdown("**Time per Rep**")
                col_time1, col_time2 = st.columns(2)
                with col_time1:
                    time_minutes = st.number_input("Minutes", min_value=0, step=1, value=int(ex.get("time_min", 0)), key=f"time_min_{i}")
                with col_time2:
                    time_seconds = st.number_input("Seconds", min_value=0, max_value=59, step=1, value=ex.get("time_sec", 0), key=f"time_sec_{i}")
                
                ex["time_min"] = time_minutes + (time_seconds / 60)
                ex["time_sec"] = time_seconds
                
                # Distance
                ex["distance_mi"] = st.number_input("Distance (mi)", min_value=0.0, value=ex["distance_mi"], key=f"dist_{i}", step=0.1)

                # Calculate and display pace in MM:SS format
                total_effort = (ex["time_min"] + ex["rest_min"]) * ex["reps"]
                if ex["distance_mi"] > 0:
                    pace_decimal = total_effort / ex["distance_mi"]
                    pace_min = int(pace_decimal)
                    pace_sec = int((pace_decimal - pace_min) * 60)
                    st.caption(f"**Pace: {pace_min}:{pace_sec:02d} per mile**")
                    ex["pace_min_mi"] = pace_decimal
                else:
                    st.caption("**Pace: -** (Enter distance)")
                    ex["pace_min_mi"] = 0

                ex["sets"] = 1
                ex["weight_lbs"] = 0.0

                with st.expander("Details", expanded=True):
                    base_name = st.selectbox(
                        "Specific Exercise (type to search)",
                        options=[""] + past_exercises,
                        index=0 if not ex["exercise"] else (past_exercises.index(ex["exercise"].split(": ", 1)[-1]) + 1 if ": " in ex["exercise"] and ex["exercise"].split(": ", 1)[-1] in past_exercises else 0),
                        key=f"base_name_select_{i}"
                    )
                    final_name = st.text_input("or type new name", value=base_name or ex["exercise"].split(": ", 1)[-1] if ": " in ex["exercise"] else ex["exercise"], key=f"base_name_input_{i}")
                    full_exercise = f"{ex['category']} - {ex['sub_category']}: {final_name}".strip(": ") if ex["category"] and ex["sub_category"] else final_name
                    ex["exercise"] = full_exercise
                    ex["notes"] = st.text_area("Notes (AI Amplification)", value=ex["notes"], key=f"notes_{i}")

            elif ex["category"] == "Weights":
                ex["sets"] = st.number_input("Sets", min_value=1, value=ex["sets"], key=f"sets_{i}")
                ex["reps"] = st.number_input("Reps", min_value=1, value=ex["reps"], key=f"reps_{i}")
                ex["weight_lbs"] = st.number_input("Weight (lbs)", min_value=0.0, value=ex["weight_lbs"], key=f"weight_{i}", step=5.0)
                ex["rest_min"] = st.number_input("Rest Between Sets (min)", min_value=0.0, value=ex["rest_min"], key=f"rest_{i}", step=0.5)
                ex["time_min"] = ex["distance_mi"] = 0.0
                ex["time_sec"] = 0

                with st.expander("Details", expanded=True):
                    base_name = st.selectbox(
                        "Specific Exercise (type to search)",
                        options=[""] + past_exercises,
                        index=0 if not ex["exercise"] else (past_exercises.index(ex["exercise"].split(": ", 1)[-1]) + 1 if ": " in ex["exercise"] and ex["exercise"].split(": ", 1)[-1] in past_exercises else 0),
                        key=f"base_name_select_{i}"
                    )
                    final_name = st.text_input("or type new name", value=base_name or ex["exercise"].split(": ", 1)[-1] if ": " in ex["exercise"] else ex["exercise"], key=f"base_name_input_{i}")
                    full_exercise = f"{ex['category']} - {ex['sub_category']}: {final_name}".strip(": ") if ex["category"] and ex["sub_category"] else final_name
                    ex["exercise"] = full_exercise
                    ex["notes"] = st.text_area("Notes (AI Amplification)", value=ex["notes"], key=f"notes_{i}")

            elif ex["category"] == "Free-Text":
                ex["exercise"] = st.text_area("Describe Your Exercise", value=ex["exercise"], key=f"free_desc_{i}")
                
                # Time input in MM:SS format for free text too
                st.markdown("**Time (Optional)**")
                col_time1, col_time2 = st.columns(2)
                with col_time1:
                    time_minutes = st.number_input("Minutes", min_value=0, step=1, value=int(ex.get("time_min", 0)), key=f"free_time_min_{i}")
                with col_time2:
                    time_seconds = st.number_input("Seconds", min_value=0, max_value=59, step=1, value=ex.get("time_sec", 0), key=f"free_time_sec_{i}")
                
                ex["time_min"] = time_minutes + (time_seconds / 60)
                ex["time_sec"] = time_seconds
                ex["sets"] = ex["reps"] = 1
                ex["weight_lbs"] = ex["distance_mi"] = ex["rest_min"] = 0.0
                ex["notes"] = ""

            else:
                st.info("Select a category to begin.")
                ex.update({"sets": 1, "reps": 1, "weight_lbs": 0.0, "time_min": 0.0, "time_sec": 0, "rest_min": 1.5, "distance_mi": 0.0, "pace_min_mi": 0.0, "exercise": "", "notes": ""})

            st.divider()

    # Add/Remove
    col_add, col_remove = st.columns(2)
    with col_add:
        if st.button("Add Exercise"):
            exercises.append({
                "category": None, "sub_category": None, "exercise": "", "sets": 1, "reps": 1,
                "weight_lbs": 0.0, "time_min": 0.0, "time_sec": 0, "rest_min": 1.5, "distance_mi": 0.0,
                "pace_min_mi": 0.0, "notes": "", "previous_category": None
            })
            st.rerun()
    with col_remove:
        if len(exercises) > 1 and st.button("Remove Last"):
            exercises.pop()
            st.rerun()

    # Save Form
    with st.form("save_form"):
        st.info("Save partial or full session anytime.")
        submitted = st.form_submit_button("Save Workout Session", type="primary")
        if submitted:
            if not any(ex["exercise"].strip() and ex["category"] for ex in exercises):
                st.error("Add at least one exercise with category.")
            else:
                conn = get_conn()
                cur = conn.cursor()
                try:
                    cur.execute(
                        "INSERT INTO workouts (user_id, workout_date, notes, duration_min) VALUES (%s, %s, %s, %s) RETURNING id",
                        (st.session_state.user_id, workout_date, "", duration_min)
                    )
                    workout_id = cur.fetchone()[0]
                    for ex in exercises:
                        if ex["exercise"].strip() and ex["category"]:
                            cur.execute(
                                "INSERT INTO workout_exercises (workout_id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                (workout_id, ex["exercise"], ex["sets"], ex["reps"], ex["weight_lbs"], ex["time_min"], ex["rest_min"], ex["distance_mi"], ex["notes"])
                            )
                    conn.commit()
                    st.success("Workout saved! View it on the Dashboard.")
                    st.session_state.exercises = []
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error: {e}")
                finally:
                    conn.close()
