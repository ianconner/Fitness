# pages/dashboard.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import date
import numpy as np
import plotly.express as px
import re

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def parse_exercise_name(exercise_str):
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

# ─────────────────────────────────────────────────────────────────────────────
# AUTO-DETECT PACE GOAL: "Run 2 miles in 18 min" → 9.0 min/mi
# ─────────────────────────────────────────────────────────────────────────────
def extract_pace_goal(goal_text):
    """
    Input: "Run 2 miles in 18 min" or "2 mile run under 20 minutes"
    Output: (distance_mi, total_time_min) or (None, None)
    """
    text = goal_text.lower()

    # Extract distance (miles)
    dist_match = re.search(r'(\d*\.?\d+)\s*(mile|mi)', text)
    distance = float(dist_match.group(1)) if dist_match and dist_match.group(1) else None

    # Extract time (minutes)
    time_match = re.search(r'(\d+)\s*(min|minute|mins)', text)
    total_time = float(time_match.group(1)) if time_match and time_match.group(1) else None

    if distance and total_time and distance > 0:
        return distance, total_time
    return None, None

def calculate_pace_min_mi(distance_mi, total_time_min):
    return total_time_min / distance_mi if distance_mi and distance_mi > 0 else None

def main():
    st.markdown("## Dashboard")
    st.markdown("Your fitness journey at a glance.")

    try:
        conn = get_conn()
        cur = conn.cursor()

        # === WORKOUTS ===
        cur.execute("""
            SELECT w.workout_date, w.duration_min, w.notes,
                   we.exercise, we.sets, we.reps, we.weight_lbs, we.time_min, we.distance_mi
            FROM workouts w
            LEFT JOIN workout_exercises we ON w.id = we.workout_id
            WHERE w.user_id = %s
            ORDER BY w.workout_date DESC
        """, (st.session_state.user_id,))
        rows = cur.fetchall()
        df_workouts = pd.DataFrame(rows, columns=[
            'workout_date', 'duration_min', 'notes', 'exercise', 'sets', 'reps',
            'weight_lbs', 'time_min', 'distance_mi'
        ])
        
        # Convert types
        df_workouts['workout_date'] = pd.to_datetime(df_workouts['workout_date']).dt.date
        for col in ['duration_min', 'sets', 'reps']:
            # Ensure duration, sets, reps are numeric for metrics
            df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
            
        for col in ['weight_lbs', 'time_min', 'distance_mi']:
            # The next steps need these as numeric objects
            df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
        
        # Calculate pace for all entries (use numeric columns)
        df_workouts['pace_min_mi'] = df_workouts.apply(
            lambda row: calculate_pace_min_mi(row['distance_mi'], row['time_min']), axis=1
        )
        
        # Clean up for display/charts (convert back to display string)
        for col in ['weight_lbs', 'time_min', 'distance_mi', 'pace_min_mi']:
            # Round first, then convert to string and replace NaT/NaN with empty string
            df_workouts[col] = df_workouts[col].round(2).astype(str).replace(['nan', '0.0'], '')
        
        for col in ['sets', 'reps']:
             df_workouts[col] = df_workouts[col].astype(str).replace(['nan', '0'], '')

        # === GOALS ===
        cur.execute("""
            SELECT id, exercise, metric_type, target_value, target_date
            FROM goals
            WHERE user_id = %s AND target_date >= %s
            ORDER BY target_date
        """, (st.session_state.user_id, date.today()))
        goals_rows = cur.fetchall()
        df_goals = pd.DataFrame(goals_rows, columns=[
            'id', 'exercise', 'metric_type', 'target_value', 'target_date'
        ])

    except Exception as e:
        st.error(f"Error loading dashboard data: {e}")
        return
    finally:
        cur.close()
        conn.close()


    # ─────────────────────────────────────────────────────────────────────────────
    # WORKOUT SUMMARY AND CHARTS
    # ─────────────────────────────────────────────────────────────────────────────
    if not df_workouts.empty:
        st.subheader("Summary Metrics")
        col1, col2, col3 = st.columns(3)
        with col1:
            total_workouts = len(df_workouts.drop_duplicates('workout_date'))
            st.metric("Total Workouts", total_workouts)
        with col2:
            # We must convert to float before summing
            total_duration = df_workouts['duration_min'].astype(float).sum()
            st.metric("Total Time", f"{int(total_duration)} min")
        with col3:
            # FIX: Removed the erroneous .astype(float) from the groupby operation.
            # Recalculate avg duration from unique workout totals
            daily_duration_sums = df_workouts.groupby('workout_date')['duration_min'].sum()
            avg_duration = daily_duration_sums.mean() if not daily_duration_sums.empty else 0
            st.metric("Avg Duration", f"{int(avg_duration)} min")

        st.subheader("Recent Workouts")
        st.dataframe(df_workouts.head(10)[["workout_date", "exercise", "sets", "reps", "weight_lbs", "pace_min_mi"]].rename(columns={'pace_min_mi': 'Pace (min/mi)'}), use_container_width=True, hide_index=True)

        freq = df_workouts.groupby('workout_date').size().reset_index(name='count')
        fig = px.bar(freq, x='workout_date', y='count', title="Workouts per Day", color_discrete_sequence=["#00FF88"])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No workouts yet. Log your first session!")


    # ─────────────────────────────────────────────────────────────────────────────
    # GOAL TRACKING
    # ─────────────────────────────────────────────────────────────────────────────
    if not df_goals.empty:
        st.subheader("Active Goals")
        
        # Prepare progress data structure and convert all workout data to numeric for fast calculation
        progress = {}
        # Only include columns that are numeric or can be numeric
        numeric_cols_for_calc = ['duration_min', 'sets', 'reps', 'weight_lbs', 'time_min', 'distance_mi', 'pace_min_mi']
        # Using a fresh numeric frame for calculations
        df_workouts_numeric = df_workouts.apply(pd.to_numeric, errors='coerce').fillna(0)
        
        for _, row in df_goals.iterrows():
            exercise = row['exercise']
            metric = row['metric_type']
            target = row['target_value']
            
            # 1. Pace Goal Logic (Lower is better)
            distance, total_time = extract_pace_goal(exercise)
            if distance and total_time:
                goal_pace = calculate_pace_min_mi(distance, total_time)
                matches = df_workouts_numeric[
                    (df_workouts_numeric['exercise'].astype(str).str.contains(exercise, case=False, na=False)) & 
                    (df_workouts_numeric['distance_mi'] >= distance) &
                    (df_workouts_numeric['time_min'] > 0)
                ]
                
                if not matches.empty:
                    current_pace = matches['pace_min_mi'].min()
                    # Simplified progress: 100% means achieving goal_pace. 0% means 20% slower than goal pace.
                    if current_pace > 0 and goal_pace > 0:
                        baseline_pace = goal_pace * 1.2 
                        
                        if current_pace <= goal_pace:
                             # Exceeding goal is > 100%
                             pct = min(100 + (goal_pace - current_pace) / goal_pace * 100, 150)
                        else:
                             # Progress relative to baseline
                             pct = max(0, (1 - (current_pace - goal_pace) / (baseline_pace - goal_pace)) * 100)
                    else:
                        pct = 0
                else:
                    current_pace = None
                    pct = 0
                
                progress[exercise] = {
                    'type': 'pace',
                    'goal_pace': goal_pace,
                    'current_pace': current_pace,
                    'pct': pct
                }

            # 2. Value Goal Logic (Higher is better)
            elif metric in numeric_cols_for_calc:
                matches = df_workouts_numeric[
                    df_workouts_numeric['exercise'].astype(str).str.contains(exercise, case=False, na=False)
                ]
                
                current = pd.to_numeric(matches[metric], errors='coerce').max()
                
                # FIX: Convert Decimal target to float for division
                target_float = float(target) 
                
                pct = min((current / target_float) * 100, 150) if target_float > 0 and current > 0 else 0
                progress[exercise] = {
                    'type': 'value',
                    'current': current,
                    'target': target,
                    'pct': pct
                }

        # Display Goals
        for _, row in df_goals.iterrows():
            exercise = row['exercise']
            data = progress.get(exercise, {'type': 'value', 'pct': 0})
            
            # Ensure target_date is a date object for calculation
            target_date = pd.to_datetime(row['target_date']).date() 
            days_left = (target_date - date.today()).days

            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{exercise}**")
                    if data['type'] == 'pace':
                        st.caption(f"Goal: {data['goal_pace']:.2f} min/mi | Best: {data['current_pace']:.2f} min/mi" if data['current_pace'] else f"Goal: {data['goal_pace']:.2f} min/mi | No data")
                    else:
                        current_display = f"{data['current']:.1f}" if pd.notna(data['current']) and data['current'] else 'No Data'
                        st.caption(f"Goal: {data['target']} {row['metric_type'].replace('_', ' ')} | Current: {current_display}")
                    
                    # FIX: Cap the progress bar value at 1.0 (100%)
                    st.progress(min(data['pct'] / 100, 1.0)) 

                with c2:
                    st.markdown(f"**{data['pct']:.1f}%**")
                    st.caption(f"{days_left} Days Left")
                    
    else:
        st.info("No active goals. Set one on the 'Goals' page to start tracking your progress!")
