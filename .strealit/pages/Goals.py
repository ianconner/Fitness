# pages/goals.py
import streamlit as st
from datetime import date, timedelta
import pandas as pd
from sqlalchemy import create_engine

# ——— DATABASE ENGINE ———
engine = create_engine(st.secrets["POSTGRES_URL"])

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

        # Styled Submit Button
        st.markdown("""
        <style>
        div[data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(135deg, #00FF88, #00CC66) !important;
            color: black !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 12px !important;
            font-weight: 700 !important;
            font-size: 16px !important;
            width: 100% !important;
            box-shadow: 0 4px 8px rgba(0,255,136,0.3) !important;
            transition: all 0.3s ease !important;
        }
        div[data-testid="stFormSubmitButton"] > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 12px rgba(0,255,136,0.4) !important;
        }
        </style>
        """, unsafe_allow_html=True)

        submitted = st.form_submit_button("Add Goal", use_container_width=True)
        if submitted:
            if not exercise.strip():
                st.error("Enter an exercise.")
            else:
                with engine.connect() as conn:
                    conn.execute(
                        "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                        (st.session_state.user_id, exercise, metric_type, target_value, target_date)
                    )
                    conn.commit()
                st.success("Goal added!")
                st.rerun()

    # ——— DISPLAY GOALS ———
    def get_goals():
        return pd.read_sql(
            "SELECT id, exercise, metric_type, target_value, target_date, created_at FROM goals WHERE user_id=%s ORDER BY target_date",
            engine,
            params=(st.session_state.user_id,)
        )

    df = get_goals()
    if not df.empty:
        df["Days Left"] = (df["target_date"] - date.today()).dt.days
        df["Progress"] = df["Days Left"].apply(
            lambda x: "On Track" if x > 7 else "Urgent" if x >= 0 else "Overdue"
        )
        # Color coding
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
