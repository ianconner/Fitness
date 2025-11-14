# .strealit/pages/03_Goals.py
import streamlit as st
from datetime import date, timedelta
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(st.secrets["POSTGRES_URL"])

# ——— FETCH GOALS ———
def get_goals():
    return pd.read_sql(
        "SELECT id, exercise, metric_type, target_value, target_date, created_at FROM goals WHERE user_id=%s ORDER BY target_date",
        engine,
        params=(st.session_state.user_id,)
    )

# ——— MAIN ———
st.markdown("## Goals")
st.markdown("Set **compound goals** like *Run 2 miles in 18 minutes*")

# ——— ADD GOAL FORM ———
with st.form("add_goal", clear_on_submit=True):
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

    # Toned-down button
    st.markdown("""
    <style>
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #2E2E2E !important;
        color: white !important;
        border: 1px solid #444 !important;
        border-radius: 8px !important;
        padding: 10px !important;
        font-weight: 500 !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #3E3E3E !important;
        border-color: #555 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    submitted = st.form_submit_button("Add Goal", use_container_width=True)
    if submitted:
        if not exercise:
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
df = get_goals()
if not df.empty:
    df["Days Left"] = (df["target_date"] - date.today()).dt.days
    df["Progress"] = df["Days Left"].apply(lambda x: "On Track" if x > 7 else "Urgent" if x >= 0 else "Overdue")
    df["Progress"] = df["Progress"].map({"On Track": "On Track", "Urgent": "Urgent", "Overdue": "Overdue"})
    df = df[["exercise", "metric_type", "target_value", "target_date", "Days Left", "Progress"]]
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No goals yet. Add one above!")
