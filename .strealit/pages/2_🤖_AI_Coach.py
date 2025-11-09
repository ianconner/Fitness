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
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance']
df = df[df['distance'] > 0].copy()

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

# ——— Analytics ———
n_sessions = len(df)
total_mi = df['distance'].sum()
avg_pace = df['pace_min_per_mi'].mean()
best_pace = df['pace_min_per_mi'].min()
pushup_max = df['pushups'].max()
crunch_max = df['crunches'].max()
felt_avg = df['felt_rating'].mean()

# Trend: Last 3 vs First 3
recent = df.head(3)
early = df.tail(3) if len(df) > 5 else df.head(3)
pace_trend = recent['pace_min_per_mi'].mean() - early['pace_min_per_mi'].mean()

# 2-Mile Projection
projected_2mi_min = avg_pace * 2
projected_2mi_time = f"{int(projected_2mi_min):02d}:{int((projected_2mi_min % 1)*60):02d}"

# ——— Prompt: Scientist + Coach ———
prompt = f"""You are **Coach Riley** — ex-USAF biomechanics specialist turned performance coach. Female. Data-first. No fluff.

Athlete: 39-year-old male. Goal: June 2026 PT Test
- 2-mile ≤ 18:00
- 45 push-ups in 60s
- 45 crunches in 120s

Today: {today}
Next session: {next_off.strftime('%A, %b %d')} (Thu/Fri/Sat only)

--- DATA SNAPSHOT ---
Sessions: {n_sessions}
Total miles: {total_mi:.1f}
Avg pace: {avg_pace:.2f} min/mi
Best pace: {best_pace:.2f} min/mi
Pace trend (recent vs early): {'+' if pace_trend > 0 else ''}{pace_trend:.2f} min/mi
Push-up max: {pushup_max}
Crunch max: {crunch_max}
Avg felt: {felt_avg:.1f}/5

--- LAST 5 SESSIONS ---
"""
for _, r in df.head(5).iterrows():
    prompt += f"{r['date'].date()}: {r['distance']} mi | {int(r['run_minutes'])}:{int(r['run_seconds']):02d} | {r['pace_min_per_mi']:.2f} min/mi | Felt {r['felt_rating']} | Push-ups {r['pushups']} | Crunches {r['crunches']}\n"

prompt += f"""
--- ANALYSIS & PRESCRIPTION ---
1. **Trend Report**: What the numbers say (be blunt).
2. **Next Session**: <50 min, bodyweight. Include volume, intensity, rest.
3. **2-Mile Forecast**: Current projection = {projected_2mi_time}. What it takes to hit 18:00.
4. **Action Items**: 1-2 specific fixes (e.g., cadence, form, volume).

Tone: Clinical + coach. Use metrics. No emojis. No "girl." No fluff.
"""

# ——— Generate ———
if st.button("Get Riley's Analysis"):
    with st.spinner("Riley is running the numbers..."):
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.6,
                "max_tokens": 600
            }
            response = requests.post(GROQ_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            analysis = response.json()['choices'][0]['message']['content']
            st.markdown("### Riley’s Performance Report")
            st.write(analysis)
        except Exception as e:
            st.error(f"Signal lost: {e}")
