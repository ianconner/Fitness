# pages/dashboard.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import date, datetime
import numpy as np
import plotly.express as px
import re
from sqlalchemy import create_engine

engine = create_engine(st.secrets["POSTGRES_URL"]) # Ensure engine is defined

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ─────────────────────────────────────────────────────────────────────────────
# AUTO-DETECT PACE GOAL: "Run 2 miles in 18 min" → 9.0 min/mi
# ─────────────────────────────────────────────────────────────────────────────
def extract_pace_goal(goal_text):
    """
    Input: "Run 2 miles in 18 min" or "2 mile run under 20 minutes"
    Output: (distance_mi, total_time_min) or (None, None)
    """
    text = goal_text.lower()
    dist_match = re.search(r'(\d*\\.?\\d+)\\s*(mile|mi)', text)
    time_match = re.search(r'(\\d+)\\s*(min|minute|mins)', text)
    distance = float(dist_match.group(1)) if dist_match else None
    total_time = float(time_match.group(1)) if time_match else None
    if distance and total_time and distance > 0:
        return distance, total_time
    return None, None

def main():
    st.markdown("## Dashboard")
    st.markdown("Your fitness journey at a glance.")

    conn = get_conn()
    cur = conn.cursor()

    try:
        # === WORKOUTS ===
        workouts_query = """
            SELECT w.workout_date, w.duration_min, w.notes,
                   we.exercise, we.sets, we.reps, we.weight_lbs, we.time_min, we.distance_mi
            FROM workouts w
            LEFT JOIN workout_exercises we ON w.id = we.workout_id
            WHERE w.user_id = %s
            ORDER BY w.workout_date DESC
        """
        df_workouts = pd.read_sql(workouts_query, conn, params=(st.session_state.user_id,))
        
        # === ROBUST DATA TYPE CONVERSION ===
        if not df_workouts.empty:
            df_workouts['workout_date'] = pd.to_datetime(df_workouts['workout_date']).dt.date
            
            numeric_cols = ['duration_min', 'sets', 'reps', 'weight_lbs', 'time_min', 'distance_mi']
            for col in numeric_cols:
                df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
            
            df_workouts.dropna(subset=['duration_min'], inplace=True)
            
            # Recalculate pace column
            df_workouts['pace_min_mi'] = np.where(
                df_workouts['distance_mi'] > 0, 
                df_workouts['time_min'] / df_workouts['distance_mi'], 
                np.nan
            )
            df_workouts['pace_min_mi'] = pd.to_numeric(df_workouts['pace_min_mi'], errors='coerce')


        # === GOALS ===
        goals_query = """
            SELECT id, exercise, metric_type, target_value, target_date
            FROM goals
            WHERE user_id = %s
            ORDER BY target_date
        """
        df_goals = pd.read_sql(goals_query, conn, params=(st.session_state.user_id,))
        
        if not df_goals.empty:
            df_goals['target_date'] = pd.to_datetime(df_goals['target_date']).dt.date
            df_goals['target_value'] = pd.to_numeric(df_goals['target_value'], errors='coerce')

        # === GOAL PROGRESS CALCULATION (Synchronized with Goals page) ===
        progress = {}
        if not df_goals.empty and not df_workouts.empty:
            for _, goal in df_goals.iterrows():
                goal_text = goal['exercise']
                metric = goal['metric_type']
                target = goal['target_value']
                
                # Check for pace goal first
                dist, time = extract_pace_goal(goal_text)
                
                if dist and time and metric == 'time_min':
                    # Pace Goal Logic
                    target_pace = time / dist
                    matches = df_workouts[
                        (df_workouts['distance_mi'] >= dist * 0.9) & 
                        (df_workouts['distance_mi'] <= dist * 1.1)
                    ]
                    
                    best_pace = matches['pace_min_mi'].min()
                    
                    if not pd.isna(best_pace) and target_pace > 0:
                        pct = min((target_pace / best_pace) * 100, 150)
                    else:
                        best_pace = None
                        pct = 0
                        
                    progress[goal_text] = {
                        'type': 'pace', 'current_pace': best_pace, 'goal_pace': target_pace, 'pct': pct
                    }

                elif metric in ['weight_lbs', 'reps', 'distance_mi', 'time_min']:
                    # Value Goal Logic
                    matches = df_workouts[
                        df_workouts['exercise'].str.contains(goal_text, case=False, na=False)
                    ]
                    
                    if metric in ['weight_lbs', 'reps', 'distance_mi']:
                        current = pd.to_numeric(matches[metric], errors='coerce').max()
                        if not pd.isna(current) and target > 0:
                            pct = min((current / target) * 100, 150)
                        else:
                            current = 0
                            pct = 0
                    else: # metric is 'time_min' (lower is better)
                        current = pd.to_numeric(matches[metric], errors='coerce').min()
                        if not pd.isna(current) and current > 0 and target > 0:
                            pct = min((target / current) * 100, 150)
                        else:
                            current = None
                            pct = 0
                    
                    progress[goal_text] = {
                        'type': 'value', 'current': current, 'target': target, 'metric': metric, 'pct': pct
                    }

        # === DASHBOARD DISPLAY LOGIC: ACTIVE GOALS ===
        df_active_goals = df_goals[df_goals['target_date'] >= date.today()].copy()
        
        if not df_active_goals.empty:
            st.subheader("Active Goals")
            
            for _, row in df_active_goals.iterrows():
                exercise = row['exercise']
                data = progress.get(exercise, {'type': 'value', 'pct': 0, 'current': 0, 'target': row['target_value']})
                days_left = (pd.to_datetime(row['target_date']) - pd.Timestamp.today()).days

                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{exercise}**")
                        
                        # Display Goal and Current Metric
                        if data['type'] == 'pace':
                            goal_text = f"Goal: {data['goal_pace']:.2f} min/mi"
                            current_text = f"Best: {data['current_pace']:.2f} min/mi" if data['current_pace'] else "No data"
                        else:
                            metric_unit = row['metric_type'].replace('_', ' ')
                            goal_text = f"Goal: {data['target']} {metric_unit}"
                            current_text = f"Current: {data['current']}" if data['current'] else "No data"
                            
                        st.caption(f"{goal_text} | {current_text}")
                        st.progress(data['pct'] / 100)
                    with c2:
                        st.markdown(f"**{data['pct']:.1f}%**")
                        status = "On Track" if days_left > 7 else "Urgent" if days_left >= 0 else "Overdue"
                        st.caption(f"Due: {row['target_date'].strftime('%b %d, %Y')} ({days_left} days)")
                        st.markdown(f"Status: **{status}**")
        else:
            st.info("No active goals yet.")


        # --- Existing Workout Display Logic ---
        if not df_workouts.empty:
            st.subheader("Summary Metrics")
            col1, col2, col3 = st.columns(3)
            with col1:
                total_workouts = len(df_workouts.drop_duplicates('workout_date'))
                st.metric("Total Workouts", total_workouts)
            with col2:
                total_duration = df_workouts['duration_min'].sum()
                st.metric("Total Time", f"{int(total_duration)} min")
            with col3:
                avg_duration = df_workouts.groupby('workout_date')['duration_min'].sum().mean()
                st.metric("Avg Duration", f"{int(avg_duration)} min")

            st.subheader("Recent Workouts")
            st.dataframe(df_workouts.head(10)[["workout_date", "exercise", "sets", "reps", "weight_lbs"]].fillna('—'), use_container_width=True, hide_index=True)

            # Workout Frequency Plot
            freq = df_workouts.groupby('workout_date').size().reset_index(name='count')
            fig = px.bar(freq, x='workout_date', y='count', title="Workouts per Day", color_discrete_sequence=["#00FF88"])
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No workouts yet.")

    except Exception as e:
        st.error(f"Error loading dashboard data: {e}")
    finally:
        cur.close()
        conn.close()
