import streamlit as st
import pandas as pd
import psycopg2
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ——— DB ———
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
    st.warning("Log a session — Riley needs data.")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time'] = df['run_minutes'] + df['run_seconds']/60
df['pace'] = df['run_time'] / df['distance'].replace(0, pd.NA)

# ——— Next Training Day ———
today = datetime.today().date()
weekday = today.weekday()
days_ahead = (3 - weekday) % 7
if days_ahead == 0: days_ahead = 7
next_off = today + timedelta(days=days_ahead)

# ——— Groq (FREE, NO BLOCKS) ———
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or st.text_input("Groq API Key", type="password")
if not GROQ_API_KEY:
    st.info("Get your **free** key: [groq.com](https://console.groq.com/keys) → Add to secrets.")
    st.stop()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

# ——— Build Prompt (No Fluff, No "Girl") ———
days_to_test = (datetime(2026, 6, 1).date() - today).days
runs = df[df['distance'] > 0].tail(10)

prompt = f"""You are **Coach Riley**, ex-USAF PT instructor. Female. Direct. No drama. No fluff.

Mission: Get this 39-year-old man to crush the June 2026 PT test:
- 2-mile run ≤18:00
- 45 push-ups in 1 min
- 45 crunches in 2 min

Today: {today}
Next training day: {next_off.strftime('%A, %b %d')} (Thu/Fri/Sat only)
Days to test: {days_to_test}

--- LAST 10 RUNS ---
"""
for _, r in runs.iterrows():
    pace = f"{r['pace']:.2f}" if pd.notna(r['pace']) else "—"
    prompt += f"{r['date'].date()}: {r['distance']} mi | {int(r['run_minutes'])}:{int(r['run_seconds']):02d} | {pace} min/mi | Felt {r['felt_rating']}/5 | Push-ups {r['pushups']} | Crunches {r['crunches']}\n"

prompt += f"""
--- STATS ---
Total miles: {df['distance'].sum():.1f}
Avg pace: {df['pace'].mean():.1f} min/mi
Total push-ups: {df['pushups'].sum()}
Total crunches: {df['crunches'].sum()}

Give:
1. Quick read (no sugar, just truth)
2. Next session (<50 min, bodyweight only)
3. 2-mile prediction
4. One-line fire

Tone: Straight talk. Military sharp. Dry humor. Zero "girl" or "queen" energy.
"""

# ——— Generate ———
if st.button("Get Plan from Coach Riley"):
    with st.spinner("Riley’s reviewing your log..."):
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 500
            }
            response = requests.post(GROQ_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            plan = response.json()['choices'][0]['message']['content']
            st.markdown("### Riley’s Orders")
            st.write(plan)
        except Exception as e:
            st.error(f"Comms down: {e}")
