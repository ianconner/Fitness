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
                ex["sets"] = st.number_input("Sets
