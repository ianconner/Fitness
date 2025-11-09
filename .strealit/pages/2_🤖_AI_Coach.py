import streamlit as st
import pandas as pd
import psycopg2
import google.generativeai as genai
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------
# DB Connection – Uses POSTGRES_URL
# -------------------------------------------------
def get_db_connection():
    url = st.secrets.get("POSTGRES_URL") or os.getenv("POSTGRES_URL")
    if not url:
        st.error("Missing POSTGRES_URL in secrets!")
        st.stop()
    return psycopg2.connect(url)

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
df['pace'] = df['run_time'] / df['distance'].replace(0, pd.NA)

# Filter valid runs
runs = df[df['distance'] > 0].copy()

# Gemini Setup
gemini_api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
if not gemini_api_key:
    st.info("Paste your Google Gemini API key above or add to Streamlit secrets.")
    st.stop()

genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-2.5-flash')  # Your upgrade – good call!

# Schedule Logic: Next Off-Day (Thu/Fri/Sat)
today = datetime.today().date()
weekday = today.weekday()  # 0=Mon, 3=Thu, 4=Fri, 5=Sat
days_ahead = (3 - weekday) % 7
if days_ahead == 0: days_ahead = 7
next_off = today + timedelta(days=days_ahead)

# Build Prompt
days_to_test = (datetime(2026, 6, 1).date() - today).days

summary = f"""
You are **Coach Riley**, a witty, motivational female coach — think upbeat gym buddy with sass, not a drill sergeant.

Goal: USAF PT test June 2026
- 2-mile run in ≤18:00
- 45 push-ups in 1 min
- 45 crunches in 2 min

Current date: {today}
Next workout day: {next_off.strftime('%A, %b %d')} (user trains only Thu/Fri/Sat)
Days until test: {days_to_test}

--- LAST 10 LOGS ---
"""
recent = df.tail(10)
for _, r in recent.iterrows():
    run = f"{int(r['run_minutes'])}:{int(r['run_seconds']):02d}" if pd.notna(r['run_minutes']) else "—"
    summary += f"{r['date'].date()}: Run {run} | Push {r['pushups']} | Crunch {r['crunches']} | Felt {r['felt_rating']}/5\n"

summary += f"""
--- CUMULATIVE ---
Total miles run: {df['run_minutes'].count() * 2}
Total push-ups: {df['pushups'].sum()}
Total crunches: {df['crunches'].sum()}
"""

summary += """
Give:
1. Quick vibe check (progress, wins, funny nudge).
2. **Next workout** for the *next available off-day* (list date). Include warm-up, main sets, cooldown.
3. Keep it under 50 min, bodyweight only, scalable.
4. End with a short pep-talk.

Tone: Female, humorous, encouraging, a little sassy.
"""

# -------------------------------------------------
# Generate Plan – WITH SAFETY FIX
# -------------------------------------------------
if st.button("Get My Next Workout Plan"):
    with st.spinner("Coach Riley is crunching the numbers…"):
        response = model.generate_content(
            summary,
            generation_config=genai.types.GenerationConfig(
                temperature=0.8,
                max_output_tokens=600
            ),
            safety_settings=[
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            ]
        )
        if not response.parts:
            st.warning("Response blocked by safety filters—retrying with adjustments.")
        else:
            plan = response.text
            st.markdown("### Coach Riley’s Plan")
            st.write(plan)
