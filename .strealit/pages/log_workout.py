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
        overall_notes = st.text_area("Overall Notes (for AI Coach context)")
        duration_min = st.number_input("Duration (min)", min_value=1, value=30)

        # Initialize exercises
        exercises = st.session_state.get("exercises", [])
        if not exercises:
            exercises = [{"category": None, "sub_category": None, "exercise": "", "sets": 3, "reps": 10, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0, "pace_min_mi": 0.0, "notes": ""}]

        for i, ex in enumerate(exercises):
            st.markdown(f"**Exercise {i+1}**")
            
            # Category Selection
            col_cat, col_sub = st.columns(2)
            with col_cat:
                category = st.selectbox("Category", ["", "Cardio", "Weights"], index=0 if not ex["category"] else ["Cardio", "Weights"].index(ex["category"]), key=f"cat_{i}")
            with col_sub:
                if category == "Cardio":
                    sub_category = st.selectbox("Sub-Category", ["Running", "Walking", "Elliptical", "Other"], index=ex["sub_category"], key=f"sub_{i}")
                    # Sub-impact: Defaults
                    if sub_category == "Running":
                        ex["distance_mi"] = 1.0  # Default for running
                    elif sub_category == "Walking":
                        ex["distance_mi"] = 0.5
                    elif sub_category == "Elliptical":
                        ex["distance_mi"] = 0.0  # Distance less relevant
                elif category == "Weights":
                    sub_category = st.selectbox("Sub-Category", ["Free-Weights", "Machine", "Body-Weights"], index=ex["sub_category"], key=f"sub_{i}")
                    # Sub-impact: Defaults
                    if sub_category == "Body-Weights":
                        ex["weight_lbs"] = 0.0  # No weight
                    elif sub_category == "Free-Weights":
                        ex["weight_lbs"] = 45.0  # Barbell default
                    elif sub_category == "Machine":
                        ex["weight_lbs"] = 50.0
                else:
                    sub_category = ""
            
            ex["category"] = category
            ex["sub_category"] = sub_category
            
            # Conditional Inputs Based on Category (Sub affects defaults above)
            if category == "Cardio":
                col_time, col_dist = st.columns(2)
                with col_time:
                    ex["time_min"] = st.number_input("Time (min)", min_value=0.0, value=ex["time_min"], key=f"time_{i}", step=0.5)
                with col_dist:
                    ex["distance_mi"] = st.number_input("Distance (mi)", min_value=0.0, value=ex["distance_mi"], key=f"dist_{i}", step=0.1)
                
                # Auto-compute Pace for accuracy
                if ex["distance_mi"] > 0:
                    ex["pace_min_mi"] = ex["time_min"] / ex["distance_mi"]
                    st.caption(f"**Pace: {ex['pace_min_mi']:.2f} min/mi** (auto-computed)")
                else:
                    ex["pace_min_mi"] = 0.0
                    st.caption("**Pace: -** (Enter distance to compute)")
                
                # Reset weights fields
                ex["sets"] = 0
                ex["reps"] = 0
                ex["weight_lbs"] = 0.0
                
            elif category == "Weights":
                col_sets, col_reps = st.columns(2)
                with col_sets:
                    ex["sets"] = st.number_input("Sets", min_value=1, value=ex["sets"], key=f"sets_{i}")
                with col_reps:
                    ex["reps"] = st.number_input("Reps", min_value=1, value=ex["reps"], key=f"reps_{i}")
                
                ex["weight_lbs"] = st.number_input("Weight (lbs)", min_value=0.0, value=ex["weight_lbs"], key=f"weight_{i}", step=5.0)
                
                # Reset cardio fields
                ex["time_min"] = 0.0
                ex["distance_mi"] = 0.0
                ex["pace_min_mi"] = 0.0
                
            else:
                st.warning("Select a category to enable inputs.")
                # Reset all fields
                ex["sets"] = 3
                ex["reps"] = 10
                ex["weight_lbs"] = 0.0
                ex["time_min"] = 0.0
                ex["distance_mi"] = 0.0
                ex["pace_min_mi"] = 0.0
            
            # Exercise Name (auto-prefix with category/sub for dashboard/AI filtering)
            base_name = st.text_input("Specific Exercise (e.g., '5K Trail' or 'Bench Press')", value=ex["exercise"].split(": ", 1)[-1] if ": " in ex["exercise"] else ex["exercise"], key=f"base_name_{i}")
            full_exercise = f"{category} - {sub_category}: {base_name}".strip(": ") if category and sub_category else base_name
            ex["exercise"] = full_exercise
            
            # Per-Exercise Notes (for AI amplification—max data accuracy)
            ex["notes"] = st.text_area("Notes (AI Context)", value=ex["notes"], key=f"notes_{i}", help="Detailed notes for RISE Coach (e.g., 'Trail was muddy, focused on form; RPE 7/10')")
            
            # Optional Rest (session-wide but per-ex for flexibility)
            ex["rest_min"] = st.number_input("Rest Between Sets (min)", min_value=0.0, value=ex["rest_min"], key=f"rest_{i}", step=0.5)
            
            st.divider()

        # Add/Remove Controls
        col_add, col_remove = st.columns(2)
        with col_add:
            if st.form_submit_button("Add Exercise"):
                exercises.append({"category": None, "sub_category": None, "exercise": "", "sets": 3, "reps": 10, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0, "pace_min_mi": 0.0, "notes": ""})
                st.session_state.exercises = exercises
                st.rerun()
        with col_remove:
            if len(exercises) > 1 and st.form_submit_button("Remove Last"):
                exercises.pop()
                st.session_state.exercises = exercises
                st.rerun()

        # Save Workout
        if st.form_submit_button("Save Workout", type="primary"):
            if not any(ex["exercise"].strip() and ex["category"] for ex in exercises):
                st.error("Add at least one exercise with category.")
            elif not overall_notes.strip():
                st.error("Add overall notes.")
            else:
                conn = get_conn()
                cur = conn.cursor()
                try:
                    # Insert workout (session-level)
                    cur.execute(
                        "INSERT INTO workouts (user_id, workout_date, notes, duration_min) VALUES (%s, %s, %s, %s) RETURNING id",
                        (st.session_state.user_id, workout_date, overall_notes, duration_min)
                    )
                    workout_id = cur.fetchone()[0]

                    # Insert individual exercises
                    for ex in exercises:
                        if ex["exercise"].strip() and ex["category"]:
                            cur.execute(
                                "INSERT INTO workout_exercises (workout_id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                (workout_id, ex["exercise"], ex["sets"], ex["reps"], ex["weight_lbs"], ex["time_min"], ex["rest_min"], ex["distance_mi"], ex["notes"])
                            )
                    conn.commit()
                    st.success("Workout session saved! Exercises logged for dashboard & RISE analysis.")
                    st.session_state.pop("exercises", None)
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error: {e}")
                finally:
                    conn.close()
