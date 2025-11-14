# .strealit/pages/03_Goals.py
import streamlit as st
import psycopg2
from datetime import date, timedelta  # ← CORRECT IMPORT
import pandas as pd

# ——— DATABASE CONNECTION ———
def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— FETCH GOALS ———
def get_goals():
    conn = get_conn()
    df = pd.read_sql(
        "SELECT exercise, metric_type, target_value, target_date FROM goals WHERE user_id=%s ORDER BY target_date",
        conn,
        params=(st.session_state.user_id,)
    )
    conn.close()
    return df

# ——— MAIN ———
st.title("Goals")

# ——— ADD GOAL FORM ———
with st.form("add_goal"):
    col1, col2 = st.columns(2)
    with col1:
        exercise = st.text_input("Exercise")
        metric_type = st.selectbox("Metric", ["time_min", "reps", "weight_lbs", "distance_mi"])
    with col2:
        target_value = st.number_input("Target Value", min_value=0.0, step=0.1)
        target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30))  # ← FIXED

    submitted = st.form_submit_button("Add Goal", use_container_width=True)
    if submitted:
        if not exercise:
            st.error("Enter an exercise.")
        else:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                (st.session_state.user_id, exercise, metric_type, target_value, target_date)
            )
            conn.commit()
            conn.close()
            st.success("Goal added!")
            st.rerun()

# ——— DISPLAY GOALS ———
df = get_goals()
if not df.empty:
    st.subheader("Your Goals")
    df["Days Left"] = (df["target_date"] - date.today()).dt.days
    df = df[["exercise", "metric_type", "target_value", "target_date", "Days Left"]]
    st.dataframe(df, use_container_width=True)
else:
    st.info("No goals yet. Add one above!")
