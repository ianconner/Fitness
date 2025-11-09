import streamlit as st
import pandas as pd
import psycopg2
import google.generativeai as genai
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------
# DB Connection
# -------------------------------------------------
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        database=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASS"),
        port=os.getenv("PG_PORT", "5432")
    )

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM logs ORDER BY date", conn)
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("Log some workouts first, then come back for the coach!")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time'] = df['run_minutes'] + df['run_seconds']/60

# -------------------------------------------------
# Gemini Setup
# -------------------------------------------------
gemini_api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
if not gemini_api_key:
    st.info("Paste your Google Gemini API key above or add to Streamlit secrets.")
    st.stop()

genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# -------------------------------------------------
# Schedule Logic: Next Off-Day (Thu/Fri/Sat)
# -------------------------------------------------
today = datetime.today().date()
weekday = today.weekday()  # 0=Mon, 3=Thu, 4=Fri, 5=Sat
days_ahead = (3 - weekday) % 7
if days_ahead == 0:
    days_ahead = 7
next_off = today + timedelta(days=days_ahead)

# -------------------------------------------------
# Build Prompt
# -------------------------------------------------
days_to_test = (datetime(2026, 6, 1).date() - today).days

summary = f"""
You are **Sgt. Spark**, a witty, motivational female coach — think upbeat gym buddy with sass, not a drill sergeant.

Goal: USAF PT test June 2026
- 2-mile run in ≤18:00
- 45 push-ups in 1 min
- 45 cross-leg reverse crunches in 2 min

Current date: {today}
Next workout day: {next_off.strftime('%A, %b %d')} (user trains only Thu/Fri/Sat)
Days until test: {days_to_test}

--- LAST 10 LOGS ---
"""
recent = df.tail(10)
for _, r in recent.iterrows():
    run = f"{int(r['run_minutes'])}:{int(r['run_seconds']):02d}" if pd.notna(r['run_minutes']) else "—"
    summary += f"{r['date'].date()}: Run {run} | Push-ups {r['pushups']} | Crunches {r['crunches']}\n"

summary += f"""
--- CUMULATIVE (Year) ---
Total miles run: {df['run_minutes'].count() * 2}
Total push-ups: {df['pushups'].sum()}
Total crunches: {df['crunches'].sum()}
"""

summary += f"""
Respond in this format:
1. Vibe check (funny, encouraging)
2. Next workout for {next_off.strftime('%A, %b %d')} — warm-up, main, cooldown (bodyweight, <50 min)
3. Short pep talk

Tone: Female, humorous, confident, a little sassy.
"""

# -------------------------------------------------
# Generate Plan
# -------------------------------------------------
if st.button("Get Next Workout Plan"):
    with st.spinner("Sgt. Spark is cooking up your plan…"):
        response = model.generate_content(
            summary,
            generation_config=genai.types.GenerationConfig(
                temperature=0.8,
                max_output_tokens=600
            )
        )
        plan = response.text
        st.markdown("### Sgt. Spark’s Custom Plan")
        st.write(plan)
