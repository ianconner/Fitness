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
        duration_min = st.number_input("Duration (min)", min_value=1, value=30)

        # Initialize exercises
        exercises = st.session_state.get("exercises", [])
        if not exercises:
            exercises = [{"category": None, "sub_category": None, "exercise": "", "sets": 3, "reps": 10, "weight_lbs": 0.0, "time_min": 0.0, "rest_min": 1.5, "distance_mi": 0.0, "pace_min_mi": 0.0, "notes": ""}]

        for i, ex in enumerate(exercises):
            st.markdown(f"**Exercise {i+1}**")
            
            # Category Selection (use session_state for persistence; changes batched until form interaction)
            category_key = f"cat_{i}"
            if category_key not in st.session_state:
                st.session_state[category_key] = ex["category"] or ""
            
            selected_category = st.selectbox("Category", ["", "Cardio", "Weights"], index=0 if not st.session_state[category_key] else ["Cardio", "Weights"].index(st.session_state[category_key]), key=category_key)
            ex["category"] = selected_category
            
            # Sub-Category (only if category selected)
            sub_category_key = f"sub_{i}"
            sub_category = ""
            if ex["category"]:
                if ex["category"] == "Cardio":
                    sub_options = ["Running", "Walking", "Elliptical", "Other"]
                    if sub_category_key not in st.session_state:
                        st.session_state[sub_category_key] = sub_options[0]
                    selected_sub = st.selectbox("Sub-Category", sub_options, index=sub_options.index(st.session_state[sub_category_key]), key=sub_category_key)
                    st.session_state[sub_category_key] = selected_sub
                    sub_category = selected_sub
                elif ex["category"] == "Weights":
                    sub_options = ["Free-Weights", "Machine", "Body-Weights"]
                    if sub_category_key not in st.session_state:
                        st.session_state[sub_category_key] = sub_options[0]
                    selected_sub = st.selectbox("Sub-Category", sub_options, index=sub_options.index(st.session_state[sub_category_key]), key=sub_category_key)
                    st.session_state[sub_category_key] = selected_sub
                    sub_category = selected_sub
                ex["sub_category"] = sub_category
            
            # Conditional Inputs Based on Category (visible after category selection; full update on form submit/add/remove)
            if ex["category"] == "Cardio":
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
                
            elif ex["category"] == "Weights":
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
                st.info("Select a category above to reveal inputs.")
                # Reset all fields
                ex["sets"] = 3
                ex["reps"] = 10
                ex["weight_lbs"] = 0.0
                ex["time_min"] = 0.0
                ex["distance_mi"] = 0.0
                ex["pace_min_mi"] = 0.0
            
            # Exercise Name (auto-prefix with category/sub for dashboard/AI filtering)
            base_name_key = f"base_name_{i}"
            base_name = st.text_input("Specific Exercise (e.g., '5K Trail' or 'Bench Press')", value=ex["exercise"].split(": ", 1)[-1] if ": " in ex["exercise"] else ex["exercise"], key=base_name_key)
            full_exercise = f"{ex['category']} - {ex['sub_category']}: {base_name}".strip(": ") if ex["category"] and ex["sub_category"] else base_name
            ex["exercise"] = full_exercise
            
            # Per-Exercise Notes (coupled with each exercise for AI accuracy)
            notes_key = f"notes_{i}"
            ex["notes"] = st.text_area("Notes (AI Context)", value=ex["notes"], key=notes_key, help="Detailed notes for RISE Coach (e.g., 'Trail was muddy, focused on form; RPE 7/10')")
            
            # Optional Rest (per-exercise)
            ex["rest_min"] = st.number_input("Rest Between Sets (min)", min_value=0.0, value=ex["rest_min"], key=f"rest_{i}", step=0.5)
            
            st.divider()

        # Add/Remove Controls (these trigger rerun for reactivity)
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
            else:
                conn = get_conn()
                cur = conn.cursor()
                try:
                    # Insert workout (session-level, empty overall notes)
                    cur.execute(
                        "INSERT INTO workouts (user_id, workout_date, notes)
