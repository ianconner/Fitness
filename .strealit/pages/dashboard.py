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
        df_workouts['pace_min_mi']
