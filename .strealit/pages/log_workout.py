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

    # Initialize exercises in session_state for persistence
    if "exercises" not in st.session_state:
        st.session_state.exercises = [{"category": None, "sub_category": None, "exercise": "", "sets": 1, "reps": 1, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0, "pace_min_mi": 0.0, "notes": "", "previous_category": None}]
    exercises = st.session_state.exercises

    for i, ex in enumerate(exercises):
        with st.container(border=True):
            st.markdown(f"**Exercise {i+1}**")
            
            # Category Selection
            category_key = f"cat_{i}"
            previous_category = ex.get("previous_category")
            selected_category = st.selectbox("Category", ["", "Cardio", "Weights", "Free-Text"], index=0 if not ex.get("category") else (["Cardio", "Weights", "Free-Text"].index(ex["category"]) if ex["category"] in ["Cardio", "Weights", "Free-Text"] else 0), key=category_key)
            
            # Reset sub_category if category changed
            if previous_category != selected_category:
                ex["sub_category"] = None
                ex["previous_category"] = selected_category
            
            ex["category"] = selected_category
            
            # Sub-Category (appears immediately after category select)
            sub_category_key = f"sub_{i}"
            sub_category = ""
            if ex["category"]:
                if ex["category"] == "Cardio":
                    sub_options = ["Running", "Walking", "Elliptical", "Other"]
                    sub_index = 0 if not ex.get("sub_category") else sub_options.index(ex["sub_category"]) if ex["sub_category"] in sub_options else 0
                    selected_sub = st.selectbox("Sub-Category", sub_options, index=sub_index, key=sub_category_key)
                    sub_category = selected_sub
                elif ex["category"] == "Weights":
                    sub_options = ["Free-Weights", "Machine", "Body-Weights"]
                    sub_index = 0 if not ex.get("sub_category") else sub_options.index(ex["sub_category"]) if ex["sub_category"] in sub_options else 0
                    selected_sub = st.selectbox("Sub-Category", sub_options, index=sub_index, key=sub_category_key)
                    sub_category = selected_sub
                elif ex["category"] == "Free-Text":
                    # No sub-category for Free-Text
                    st.text("")  # Placeholder
                ex["sub_category"] = sub_category
            else:
                st.text("")  # Placeholder for alignment
            
            # Conditional Inputs Based on Category
            if ex["category"] == "Cardio":
                # Reps/Intervals (if >1, show rest)
                reps_key = f"reps_{i}"
                ex["reps"] = st.number_input("Reps/Intervals", min_value=1, value=ex["reps"], key=reps_key)
                if ex["reps"] > 1:
                    rest_key = f"rest_{i}"
                    ex["rest_min"] = st.number_input("Rest Between Reps (min)", min_value=0.0, value=ex["rest_min"], key=rest_key, step=0.5)
                else:
                    ex["rest_min"] = 0.0
                
                col_time, col_dist = st.columns(2)
                with col_time:
                    time_key = f"time_{i}"
                    ex["time_min"] = st.number_input("Time (min)", min_value=0.0, value=ex["time_min"], key=time_key, step=0.5)
                with col_dist:
                    dist_key = f"dist_{i}"
                    ex["distance_mi"] = st.number_input("Distance (mi)", min_value=0.0, value=ex["distance_mi"], key=dist_key, step=0.1)
                
                # Auto-compute Pace
                if ex["distance_mi"] > 0:
                    ex["pace_min_mi"] = ex["time_min"] / ex["distance_mi"]
                    st.caption(f"**Pace: {ex['pace_min_mi']:.2f} min/mi** (auto-computed)")
                else:
                    ex["pace_min_mi"] = 0.0
                    st.caption("**Pace: -** (Enter distance to compute)")
                
                # Reset weights/sets
                ex["sets"] = 1
                ex["weight_lbs"] = 0.0
                
            elif ex["category"] == "Weights":
                # Sets
                sets_key = f"sets_{i}"
                ex["sets"] = st.number_input("Sets", min_value=1, value=ex["sets"], key=sets_key)
                
                # Reps
                reps_key = f"reps_{i}"
                ex["reps"] = st.number_input("Reps", min_value=1, value=ex["reps"], key=reps_key)
                
                # Weight
                weight_key = f"weight_{i}"
                ex["weight_lbs"] = st.number_input("Weight (lbs)", min_value=0.0, value=ex["weight_lbs"], key=weight_key, step=5.0)
                
                # Rest (always for weights)
                rest_key = f"rest_{i}"
                ex["rest_min"] = st.number_input("Rest Between Sets (min)", min_value=0.0, value=ex["rest_min"], key=rest_key, step=0.5)
                
                # Reset cardio
                ex["time_min"] = 0.0
                ex["distance_mi"] = 0.0
                ex["pace_min_mi"] = 0.0
                
            elif ex["category"] == "Free-Text":
                # Free description text box
                free_desc_key = f"free_desc_{i}"
                ex["exercise"] = st.text_area("Describe Your Exercise", value=ex["exercise"], key=free_desc_key, help="Full description of the custom exercise (e.g., 'Yoga flow: Sun salutations with 5-min hold')")
                
                # Optional time (generic for free-text)
                time_key = f"time_{i}"
                ex["time_min"] = st.number_input("Time (min) - Optional", min_value=0.0, value=ex["time_min"], key=time_key, step=0.5)
                
                # Reset other fields
                ex["sets"] = 1
                ex["reps"] = 1
                ex["weight_lbs"] = 0.0
                ex["distance_mi"] = 0.0
                ex["pace_min_mi"] = 0.0
                ex["rest_min"] = 0.0
                
            else:
                st.info("Select a category above to reveal inputs.")
                # Reset all
                ex["sets"] = 1
                ex["reps"] = 1
                ex["weight_lbs"] = 0.0
                ex["time_min"] = 0.0
                ex["rest_min"] = 1.5
                ex["distance_mi"] = 0.0
                ex["pace_min_mi"] = 0.0
                ex["exercise"] = ""
            
            # Specific Exercise Name (after inputs)
            base_name_key = f"base_name_{i}"
            base_name = st.text_input("Specific Exercise (e.g., '5K Trail' or 'Bench Press')", value=ex["exercise"].split(": ", 1)[-1] if ": " in ex["exercise"] else ex["exercise"], key=base_name_key)
            full_exercise = f"{ex['category']} - {ex['sub_category']}: {base_name}".strip(": ") if ex["category"] and ex["sub_category"] else base_name
            ex["exercise"] = full_exercise
            
            # Per-Exercise Notes (amplification for all categories)
            notes_key = f"notes_{i}"
            ex["notes"] = st.text_area("Notes (AI Amplification)", value=ex["notes"], key=notes_key, help="Amplifying details for RISE Coach (e.g., 'Trail was muddy, focused on form; RPE 7/10')")
            
            st.divider()

    # Add/Remove Controls (outside form for reactivity)
    col_add, col_remove = st.columns(2)
    with col_add:
        if st.button("Add Exercise"):
            exercises.append({"category": None, "sub_category": None, "exercise": "", "sets": 1, "reps": 1, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0, "pace_min_mi": 0.0, "notes": "", "previous_category": None})
            st.session_state.exercises = exercises
            st.rerun()
    with col_remove:
        if len(exercises) > 1 and st.button("Remove Last"):
            exercises.pop()
            st.session_state.exercises = exercises
            st.rerun()

    # Separate Save Form (partial save allowed)
    with st.form("save_form"):
        st.info("Preview exercises above; save partial or full session anytime.")
        submitted = st.form_submit_button("Save Workout Session", type="primary")
        if submitted:
            if not any(ex["exercise"].strip() and ex["category"] for ex in exercises):
                st.error("Add at least one exercise with category.")
            else:
                conn = get_conn()
                cur = conn.cursor()
                try:
                    # Insert workout (session-level)
                    cur.execute(
                        "INSERT INTO workouts (user_id, workout_date, notes, duration_min) VALUES (%s, %s, %s, %s) RETURNING id",
                        (st.session_state.user_id, workout_date, "", duration_min)
                    )
                    workout_id = cur.fetchone()[0]

                    # Insert individual exercises with per-ex notes
                    for ex in exercises:
                        if ex["exercise"].strip() and ex["category"]:
                            cur.execute(
                                "INSERT INTO workout_exercises (workout_id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                (workout_id, ex["exercise"], ex["sets"], ex["reps"], ex["weight_lbs"], ex["time_min"], ex["rest_min"], ex["distance_mi"], ex["notes"])
                            )
                    conn.commit()
                    st.success(f"Partial session saved! {len([e for e in exercises if e['exercise'].strip() and e['category']])} exercises logged.")
                    # Clear for next partial
                    st.session_state.exercises = []
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error: {e}")
                finally:
                    conn.close()
