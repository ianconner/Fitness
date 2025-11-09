import streamlit as st
import pandas as pd
import psycopg2
import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ——— DB Connection ———
def get_db_connection():
    url = st.secrets.get("POSTGRES_URL") or os.getenv("POSTGRES_URL")
    if not url:
        st.error("Missing POSTGRES_URL!")
        st.stop()
    return psycopg2.connect(url)

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM logs ORDER BY date DESC", conn)
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("Log a session first — Coach Riley needs fuel!")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time'] = df['run_minutes'] + df['run_seconds']/60
df['pace'] = df['run_time'] / df['distance'].replace(0, pd.NA)

# ——— Next Off-Day ———
today = datetime.today().date()
weekday = today.weekday()
days_ahead = (3 - weekday) % 7
if days_ahead == 0: days_ahead = 7
next_off = today + timedelta(days=days_ahead)

# ——— Groq API (FREE, NO BLOCKS) ———
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or st.text_input("Groq API Key", type="password")
if not GROQ_API_KEY:
    st.info("Get your **free** key at [groq.com](https://console.groq.com/keys) → paste in secrets.")
    st.stop()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"  # Free, fast, smart

# ——— Build Prompt (Neutral + Full Data) ———
days_to_test = (datetime(2026, 6, 1).date() - today).days
recent = df[df['distance'] > 0].tail(10)

prompt = f"""You are **Coach Riley**, a sharp, funny, female fitness coach — think upbeat gym buddy with sass.

Goal: USAF PT Test June 2026
- 2-mile run ≤18:00
- 45 push-ups in 1 min
- 45 crunches in 2 min

Today: {today}
Next workout: {next_off.strftime('%A, %b %d')} (Thu/Fri/Sat only)
Days to test: {days_to_test}

--- LAST 10 LOGS ---
"""
for _, r in recent.iterrows():
    pace = f"{r['pace']:.2f}" if pd.notna(r['pace']) else "—"
    prompt += f"{r['date'].date()}: {r['distance']} mi in {int(r['run_minutes'])}:{int(r['run_seconds']):02d} → {pace} min/mi | Felt {r['felt_rating']}/5 | Push-ups {r['pushups']} | Crunches {r['crunches']}\n"

prompt += f"""
--- STATS ---
Total miles: {df['distance'].sum():.1f}
Avg pace: {df['pace'].mean():.1f} min/mi
Total push-ups: {df['pushups'].sum()}
Total crunches: {df['crunches'].sum()}

Give:
1. Vibe check (funny, real)
2. Next workout (<50 min, bodyweight)
3. 2-mile prediction
4. Pep talk

Tone: Female, humorous, confident, sassy.
"""

# ——— Generate Plan ———
if st.button("Get Plan from Coach Riley"):
    with st.spinner("Coach Riley is cooking..."):
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 600
            }
            response = requests.post(GROQ_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            plan = response.json()['choices'][0]['message']['content']
            st.markdown("### Coach Riley's Game Plan")
            st.write(plan)
        except Exception as e:
            st.error(f"AI error: {e}. Check key or try again.")
