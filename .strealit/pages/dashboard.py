# pages/dashboard.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import date
import plotly.express as px

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

    # === DISPLAY ===
    if not df_workouts.empty:
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
        st.dataframe(df_workouts.head(10)[["workout_date", "exercise", "sets", "reps", "weight_lbs"]], use_container_width=True, hide_index=True)

        freq = df_workouts.groupby('workout_date').size().reset_index(name='count')
        fig = px.bar(freq, x='workout_date', y='count', title="Workouts per Day", color_discrete_sequence=["#00FF88"])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No workouts yet.")

    
    st.subheader("Active Goals")
    if not df_goals.empty:
        
        # Convert target_date to datetime objects before using .dt accessor
        df_goals["target_date"] = pd.to_datetime(df_goals["target_date"])
        # Use pd.Timestamp for compatible subtraction
        df_goals["Days Left"] = (df_goals["target_date"] - pd.Timestamp(date.today())).dt.days
        
        # === AESTHETIC UPDATE ===
        # Use the status logic with emojis from goals.py
        df_goals["Status"] = df_goals["Days Left"].apply(
            lambda x: "🟢 On Track" if x > 7 else "🟡 Urgent" if x >= 0 else "🔴 Overdue"
        )
        
        # Loop and display each goal in its own "card"
        for idx, row in df_goals.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{row['exercise']}**")
                    # Clean up the metric type display
                    metric_display = row['metric_type'].replace('_', ' ').replace('lbs', 'LBs').replace('mi', 'Mi').title()
                    st.caption(f"Goal: {row['target_value']} {metric_display}")
                with col2:
                    st.markdown(f"**{row['Status']}**")
                    st.caption(f"{row['Days Left']} days left | Due {row['target_date'].strftime('%b %d')}")
            st.write("") # Adds a small space between cards
        # === END AESTHETIC UPDATE ===
            
    else:
        st.info("No active goals.")

}
