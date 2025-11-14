# pages/04_AI_Coach.py
import streamlit as st
import psycopg2
import pandas as pd
import requests
from datetime import datetime

# ——— DATABASE ———
def conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— FETCH ALL USER DATA ———
c = conn()
workouts = pd.read_sql("""
    SELECT workout_date, notes, duration_min 
    FROM workouts 
    WHERE user_id = %s 
    ORDER BY workout_date DESC
""", c, params=(st.session_state.user_id,))

exercises = pd.read_sql("""
    SELECT e.exercise, e.sets, e.reps, e.weight_lbs, e.time_min, e.rest_min
    FROM workout_exercises e
    JOIN workouts w ON e.workout_id = w.id
    WHERE w.user_id = %s
    ORDER BY w.workout_date DESC
""", c, params=(st.session_state.user_id,))

goals = pd.read_sql("""
    SELECT exercise, metric_type, target_value, target_date 
    FROM goals 
    WHERE user_id = %s 
    ORDER BY target_date
""", c, params=(st.session_state.user_id,))
c.close()

# ——— PAGE ———
st.set_page_config(page_title="AI Coach - SOPHIA", layout="wide")
st.title("SOPHIA — Your AI Performance Coach")

st.markdown("""
**SOPHIA sees everything:**  
- All your workouts  
- Every rep, weight, time, and rest  
- Your goals and deadlines  
""")

# ——— BUILD PROMPT ———
today = datetime.now().date()
prompt = f"""You are SOPHIA — Smart Optimized Performance Health Intelligence Assistant.

User: {st.session_state.username}
Today: {today}

--- ACTIVE GOALS ---
{goals.to_markdown(index=False) if not goals.empty else "No goals set."}

--- RECENT WORKOUTS (last 7) ---
{workouts.head(7)[['workout_date', 'notes']].to_markdown(index=False) if not workouts.empty else "No workouts yet."}

--- PARSED EXERCISE HISTORY ---
{exercises.head(20).to_markdown(index=False) if not exercises.empty else "No parsed data."}

--- INSTRUCTIONS ---
1. Summarize training volume, frequency, and trends over the past 30 days.
2. For each goal: calculate current best vs. target. Be honest.
3. Give 3 specific, science-backed next steps (e.g., "Add 1 set of squats at 80% 1RM").
4. Design a complete <50 min workout for the next session (warm-up, main, cooldown, RPE).
5. End by asking: "When is your next planned workout?"

Tone: direct, encouraging, data-driven. Use U.S. units (lb, min, mi).
"""

# ——— GET SOPHIA'S RESPONSE ———
if st.button("Get Today's SOPHIA Session", use_container_width=True):
    with st.spinner("SOPHIA is analyzing your full history..."):
        try:
            headers = {
                "Authorization": f"Bearer {st.secrets.get('GROQ_API_KEY')}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.6,
                "max_tokens": 1000
            }
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            answer = result['choices'][0]['message']['content']
            
            st.success("SOPHIA Session Ready")
            st.markdown(answer)
            
        except Exception as e:
            st.error(f"AI Error: {e}")
            st.info("Check your GROQ_API_KEY in Streamlit Secrets.")

# ——— QUICK STATS ———
if not workouts.empty:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Sessions", len(workouts))
    with col2:
        total_min = workouts['duration_min'].sum()
        st.metric("Total Time", f"{int(total_min)} min" if pd.notna(total_min) else "N/A")
    with col3:
        if not goals.empty:
            days_left = (goals['target_date'].min() - today).days
            st.metric("Next Goal Deadline", f"{days_left} days")
