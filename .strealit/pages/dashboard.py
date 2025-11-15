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
        for col in ['weight_lbs', 'time_min', 'distance_mi', 'sets', 'reps']:
             df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
        
        # 2. Replace 0 with NaN in 'distance_mi' to prevent division by zero
        df_workouts['distance_mi'] = df_workouts['distance_mi'].replace(0, np.nan)
        
        # 3. Calculate Pace for Cardio (Pace = Time / Distance)
        df_workouts['pace_min_mi'] = (df_workouts['time_min'] / df_workouts['distance_mi'])
        # === END FIX ===

        # 4. Format numeric columns for clean display (replace 0/NaN/inf with '-')
        # Now that all are numeric, .round() will work.
        for col in ['weight_lbs', 'time_min', 'distance_mi', 'pace_min_mi']:
            df_workouts[col] = df_workouts[col].round(2).astype(str).replace(['0.0', '0', 'nan', 'inf', '<NA>'], '-')
        
        for col in ['sets', 'reps']:
             df_workouts[col] = df_workouts[col].astype(str).replace(['0.0', '0', 'nan', '<NA>'], '-')
             
        # === DISPLAY ===
        col1, col2, col3 = st.columns(3)
        with col1:
            total_workouts = len(df_workouts.drop_duplicates('workout_date'))
            st.metric("Total Workouts", total_workouts)
        with col2:
            total_duration = pd.to_numeric(df_workouts['duration_min'], errors='coerce').sum()
            st.metric("Total Time", f"{int(total_duration)} min")
        with col3:
            avg_duration = pd.to_numeric(df_workouts.groupby('workout_date')['duration_min'].sum(), errors='coerce').mean()
            st.metric("Avg Duration", f"{int(avg_duration)} min")

        # === RECENT WORKOUTS AESTHETIC UPDATE (Card Layout) ===
        st.subheader("Recent Workouts")
        
        sessions = df_workouts[['workout_date', 'duration_min', 'notes']].drop_duplicates().sort_values('workout_date', ascending=False).head(5)

        if not sessions.empty:
            for idx, session in sessions.iterrows():
                session_date = session['workout_date'].strftime('%b %d, %Y')
                session_duration = session['duration_min']
                session_notes = session['notes']
                
                session_exercises = df_workouts[df_workouts['workout_date'] == session['workout_date']]
                
                cardio_df = session_exercises[session_exercises['type'] == 'Cardio']
                weight_df = session_exercises[session_exercises['type'] == 'Weight']

                with st.container(border=True):
                    st.markdown(f"#### 🗓️ Workout on {session_date}")
                    col_d, col_n = st.columns([1, 4])
                    col_d.caption(f"**Duration:** {session_duration} min")
                    col_n.caption(f"**Notes:** {session_notes}")
                    
                    if not cardio_df.empty:
                        st.markdown("##### 🏃 Cardio")
                        st.dataframe(
                            cardio_df[['exercise', 'time_min', 'distance_mi', 'pace_min_mi']].rename(
                                columns={'time_min': 'Time (min)', 'distance_mi': 'Distance (mi)', 'pace_min_mi': 'Pace (min/mi)'}
                            ).set_index('exercise'),
                            width='stretch'
                        )

                    if not weight_df.empty:
                        st.markdown("##### 💪 Weight Training")
                        st.dataframe(
                            weight_df[['exercise', 'weight_lbs', 'sets', 'reps']].rename(
                                columns={'weight_lbs': 'Weight (lbs)', 'sets': 'Sets', 'reps': 'Reps'}
                            ).set_index('exercise'),
                            width='stretch'
                        )
                st.write("") 
        else:
             st.info("No workouts yet.")
        # === END RECENT WORKOUTS AESTHETIC UPDATE ===

        freq = df_workouts.groupby('workout_date').size().reset_index(name='count')
        fig = px.bar(freq, x='workout_date', y='count', title="Workouts per Day", color_discrete_sequence=["#00FF88"])
        
        fig.update_xaxes(tickformat="%b %d")
        
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True) # use_container_width is correct for plotly
    else:
        st.info("No workouts yet.")

    
    st.subheader("Active Goals")
    if not df_goals.empty:
        
        df_goals["target_date"] = pd.to_datetime(df_goals["target_date"])
        df_goals["Days Left"] = (df_goals["target_date"] - pd.Timestamp(date.today())).dt.days
        
        df_goals["Status"] = df_goals["Days Left"].apply(
            lambda x: "🟢 On Track" if x > 7 else "🟡 Urgent" if x >= 0 else "🔴 Overdue"
        )
        
        for idx, row in df_goals.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{row['exercise']}**")
                    metric_display = row['metric_type'].replace('_', ' ').replace('lbs', 'LBs').replace('mi', 'Mi').title()
                    st.caption(f"Goal: {row['target_value']} {metric_display}")
                with col2:
                    st.markdown(f"**{row['Status']}**")
                    st.caption(f"{row['Days Left']} days left | Due {row['target_date'].strftime('%b %d')}")
            st.write("") 
            
    else:
        st.info("No active goals.")
