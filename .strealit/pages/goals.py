# pages/goals.py
import streamlit as st
from datetime import date, timedelta
import psycopg2

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def main():
    st.markdown("## Goals")
    st.markdown("Set **compound goals** like *Run 2 miles in 18 minutes*")

    # ——— ADD GOAL FORM ———
    with st.form("add_goal_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            exercise = st.text_input("Exercise", placeholder="Run, Squat, Push-up")
            metric_type = st.selectbox("Metric", ["time_min", "reps", "weight_lbs", "distance_mi"])
        with col2:
            if metric_type == "time_min":
                distance = st.number_input("Distance (mi)", min_value=0.1, step=0.1, value=2.0)
                target_time = st.number_input("Target Time (min)", min_value=1.0, step=0.5, value=18.0)
                target_value = round(target_time / distance, 2)
                st.caption(f"**Pace: {target_value:.2f} min/mi**")
            else:
                target_value = st.number_input("Target Value", min_value=0.0, step=0.1)
            
            target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30))

        submitted = st.form_submit_button("Add Goal", use_container_width=True)
        if submitted:
            if not exercise.strip():
                st.error("Enter an exercise.")
            else:
                conn = get_conn()
                cur = conn.cursor()
                try:
                    cur.execute(
                        "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                        (st.session_state.user_id, exercise, metric_type, target_value, target_date)
                    )
                    conn.commit()
                    st.success("Goal added!")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error: {e}")
                finally:
                    conn.close()

    # ——— DISPLAY GOALS ———
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, exercise, metric_type, target_value, target_date, created_at FROM goals WHERE user_id=%s ORDER BY target_date",
            (st.session_state.user_id,)
        )
        rows = cur.fetchall()
        import pandas as pd
        df = pd.DataFrame(rows, columns=['id', 'exercise', 'metric_type', 'target_value', 'target_date', 'created_at'])
    finally:
        conn.close()

    if not df.empty:
        df["Days Left"] = (df["target_date"] - date.today()).dt.days
        df["Progress"] = df["Days Left"].apply(
            lambda x: "On Track" if x > 7 else "Urgent" if x >= 0 else "Overdue"
        )
        def color_status(val):
            color = "green" if val == "On Track" else "orange" if val == "Urgent" else "red"
            return f'background-color: {color}; color: white; padding: 5px; border-radius: 8px; text-align: center;'
        
        df_display = df[["exercise", "metric_type", "target_value", "target_date", "Days Left", "Progress"]].copy()
        st.dataframe(
            df_display.style.applymap(color_status, subset=["Progress"]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No goals yet. Add one above!")
