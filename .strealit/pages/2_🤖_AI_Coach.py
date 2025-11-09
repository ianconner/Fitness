# pages/2_🤖_AI_Coach.py
import streamlit as st
import pandas as pd
import psycopg2
import requests
from datetime import datetime, timedelta

# ——— DATABASE CONNECTION ———
def get_db_connection():
    """Connect to Supabase PostgreSQL using Streamlit secrets."""
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def get_logs():
    """Fetch all logs for the current logged-in user."""
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT * FROM logs WHERE user_id = %s ORDER BY date DESC",
        conn,
        params=(st.session_state.user_id,)
    )
    conn.close()
    return df

# ——— DATA LOADING ———
df = get_logs()
if df.empty:
    st.warning("No sessions logged yet. Log one first!")
    st.stop()

# Process data
df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds'] / 60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)
valid_df = df[df['distance'] > 0].copy()

# ——— GOALS FROM DASHBOARD (via session_state) ———
GOAL_RUN_MIN = st.session_state.get("goal_run_min", 18.0)
GOAL_PUSH = st.session_state.get("goal_push", 45)
GOAL_CRUNCH = st.session_state.get("goal_crunch", 45)
GOAL_DATE = st.session_state.get("goal_date", datetime(2026, 6, 1).date())

# ——— HORIZON & URGENCY CALCULATION ———
today = datetime.today().date()
days_to_goal = (GOAL_DATE - today).days

if days_to_goal <= 30:
    urgency = "MAX"
    intensity_factor = 1.3
    volume_factor = 0.7
    progression = "aggressive taper"
elif days_to_goal <= 90:
    urgency = "HIGH"
    intensity_factor = 1.2
    volume_factor = 0.8
    progression = "linear peaking"
elif days_to_goal <= 180:
    urgency = "MEDIUM"
    intensity_factor = 1.0
    volume_factor = 1.0
    progression = "periodized"
else:
    urgency = "LOW"
    intensity_factor = 0.9
    volume_factor = 1.1
    progression = "base building"

# ——— PROJECTIONS ———
last_5 = valid_df.head(5)
avg_pace = last_5['pace_min_per_mi'].mean()
projected_2mi = avg_pace * 2
projected_str = f"{int(projected_2mi):02d}:{int((projected_2mi % 1) * 60):02d}"

# ——— NEXT TRAINING DAY (Thu/Fri/Sat) ———
weekday = today.weekday()
days_ahead = (3 - weekday) % 7
if days_ahead == 0:
    days_ahead = 7
next_session = today + timedelta(days=days_ahead)

# ——— GROQ API SETUP ———
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    st.error("Missing GROQ_API_KEY in secrets!")
    st.stop()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

# ——— SOPHIA PROMPT (Dynamic, Goal-Date Aware, Daily Only) ———
prompt = f"""You are **SOPHIA** — **S**mart **O**ptimized **P**erformance **H**ealth **I**ntelligence **A**ssistant.

User: {st.session_state.username}, 39 y/o male.
Goal Date: {GOAL_DATE.strftime('%B %d, %Y')} ({days_to_goal} days remaining)
Goals: 2-mile less than or equal to {GOAL_RUN_MIN}:00 | {GOAL_PUSH} push-ups | {GOAL_CRUNCH} crunches

Today: {today}
Next Session: {next_session.strftime('%A, %B %d')}
Urgency: {urgency} | Progression: {progression}

--- DATA SNAPSHOT ---
Last 5 avg pace: {avg_pace:.2f} min/mi → Projected 2-mile: {projected_str}
Push-up trend: {df['pushups'].diff().mean():+.1f}/session
Recent felt rating: {last_5['felt_rating'].mean():.1f}/5

--- TODAY'S SESSION (Only) ---
Provide **one** less than 50-minute bodyweight session for **{next_session.strftime('%A')}**.
Include:
- Warm-up (time + pace or movement)
- Main set (intervals, reps, rest)
- Cooldown
- RPE target

Then:
- One-sentence 4-week microcycle plan
- One science citation (e.g., Seiler, Daniels, Bompa)

Tone: Clinical, precise, data-driven. No emojis. No hype.
"""

# ——— GENERATE SOPHIA'S PLAN ———
if st.button("Get Today's SOPHIA Session"):
    with st.spinner("SOPHIA is analyzing your data..."):
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 500
            }
            response = requests.post(GROQ_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            plan = response.json()['choices'][0]['message']['content']

            st.markdown("### SOPHIA — Smart Optimized Performance Health Intelligence Assistant")
            st.write(plan)

        except Exception as e:
            st.error(f"Error connecting to SOPHIA: {e}")

# ——— TALK TO SOPHIA (Optional Q&A) ———
st.markdown("---")
st.markdown("### Talk to SOPHIA")
user_question = st.text_input("Ask about goals, science, or adjustments...")

if st.button("Send Question") and user_question:
    with st.spinner("SOPHIA is thinking..."):
        q_prompt = f"""SOPHIA answering: {user_question}

Context:
- Goal date: {GOAL_DATE} ({days_to_goal} days)
- Current 2-mile projection: {projected_str}
- Avg pace: {avg_pace:.2f} min/mi
- Push-up trend: {df['pushups'].diff().mean():+.1f}/session

Answer in 3–5 sentences. Cite science. Be direct."""
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": MODEL,
                "messages": [{"role": "user", "content": q_prompt}],
                "temperature": 0.6,
                "max_tokens": 300
            }
            response = requests.post(GROQ_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            reply = response.json()['choices'][0]['message']['content']
            st.markdown(f"**SOPHIA:** {reply}")
        except Exception as e:
            st.error(f"Error: {e}")
