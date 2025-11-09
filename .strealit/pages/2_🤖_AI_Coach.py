import streamlit as st
import pandas as pd
import psycopg2
import google.generativeai as genai
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# DB Connection
def get_db_connection():
    url = st.secrets.get("POSTGRES_URL") or os.getenv("POSTGRES_URL")
    if not url:
        st.error("Missing POSTGRES_URL!")
        st.stop()
    return psycopg2.connect(url)

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM logs ORDER BY date DESC LIMIT 8", conn)  # Short for free tier
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("Log a session first — Coach Riley needs data!")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time'] = df['run_minutes'] + df['run_seconds']/60
df['pace'] = df['run_time'] / df['distance'].replace(0, pd.NA)

# Next off-day
today = datetime.today().date()
weekday = today.weekday()
days_ahead = (3 - weekday) % 7
if days_ahead == 0: days_ahead = 7
next_off = today + timedelta(days=days_ahead)

# Gemini (Free Tier)
gemini_api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
if not gemini_api_key:
    st.info("Add your free Gemini key in Streamlit Secrets.")
    st.stop()

genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-2.5-flash')  # Free, top performer

# Neutral prompt (renamed terms)
summary = f"""
You are Coach Riley, a witty, motivational female coach — upbeat health buddy with sass.

Goal: USAF health enhancement test June 2026
- Endurance distance ≤18:00
- 45 upper body holds in 1 min
- 45 core stability exercises in 2 min

Today: {today}
Next session: {next_off.strftime('%A, %b %d')} (Thu/Fri/Sat only)
Days until test: {(datetime(2026, 6, 1).date() - today).days}

Recent sessions:
"""
for _, r in df[df['distance'] > 0].tail(4).iterrows():  # Ultra-short
    summary += f"- {r['date'].date()}: {r['distance']} miles endurance, {int(r['run_minutes'])}:{int(r['run_seconds']):02d} time, pace {r['pace']:.1f} min/mile, energy {r['felt_rating']}/5, upper holds {r['pushups']}, core exercises {r['crunches']}\n"

summary += """
Suggest a 45-min session: warm-up, main activities, cool-down. Bodyweight only. Predict endurance time.

Format:
1. Vibe check (funny, encouraging)
2. Next session details
3. Prediction & tips
4. Pep talk

Tone: Female, humorous, confident, sassy.
"""

# Generate (tuned for free tier)
if st.button("Get Plan from Coach Riley"):
    with st.spinner("Coach Riley is prepping your session..."):
        response = model.generate_content(
            summary,
            generation_config=genai.types.GenerationConfig(
                temperature=0.8,
                max_output_tokens=400
            ),
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        )
        if response.candidates and response.candidates[0].content.parts:
            plan = response.candidates[0].content.parts[0].text
            st.markdown("### Coach Riley's Session Plan")
            st.write(plan)
        else:
            st.warning("Quick retry—Gemini being picky. Log more data!")
