# pages/03_Goals.py
import streamlit as st
import psycopg2
from datetime import date

# ——— DATABASE ———
def conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— PAGE ———
st.set_page_config(page_title="Goals - SOPHIA", layout="wide")
st.title("Set Your Goals")

# ——— ADD GOAL FORM ———
with st.form("add_goal"):
    st.write("### Add a New Goal")
    col1, col2 = st.columns(2)
    with col1:
        exercise = st.text_input("Exercise", placeholder="e.g. Run, Squat, Push-up")
        metric = st.selectbox(
            "Metric",
            ["Time (min)", "Reps", "Weight (lbs)", "Distance (mi)"]
        )
    with col2:
        target_value = st.number_input("Target Value", min_value=0.0, step=0.1)
        target_date = st.date_input("Target Date", value=date.today() + st.timedelta(days=30))

    submitted = st.form_submit_button("Add Goal", use_container_width=True)
    
    if submitted:
        if not exercise.strip():
            st.error("Please enter an exercise.")
        elif target_value <= 0:
            st.error("Target value must be greater than 0.")
        else:
            metric_map = {
                "Time (min)": "time_min",
                "Reps": "reps",
                "Weight (lbs)": "weight_lbs",
                "Distance (mi)": "distance_mi"
            }
            metric_type = metric_map[metric]
            
            c = conn()
            cur = c.cursor()
            cur.execute(
                """INSERT INTO goals 
                   (user_id, exercise, metric_type, target_value, target_date)
                   VALUES (%s, %s, %s, %s, %s)""",
                (st.session_state.user_id, exercise.strip().title(), metric_type, target_value, target_date)
            )
            c.commit()
            c.close()
            st.success(f"Goal added: **{exercise} → {target_value} {metric}** by **{target_date}**")
            st.balloons()

# ——— CURRENT GOALS ———
c = conn()
cur = c.cursor()
cur.execute(
    """SELECT exercise, metric_type, target_value, target_date 
       FROM goals WHERE user_id = %s ORDER BY target_date ASC""",
    (st.session_state.user_id,)
)
goals = cur.fetchall()
c.close()

if goals:
    st.subheader("Your Active Goals")
    for ex, mt, tv, td in goals:
        metric_label = mt.replace("_", " ").title()
        days_left = (td - date.today()).days
        color = "🟢" if days_left > 14 else "🟡" if days_left > 0 else "🔴"
        st.markdown(f"{color} **{ex}** → **{tv} {metric_label}** by **{td}** ({days_left} days left)")
else:
    st.info("No goals yet. Add one above to get started!")

# ——— PROGRESS TIP ———
if goals:
    st.caption("SOPHIA will analyze your progress in the **AI Coach** tab.")
