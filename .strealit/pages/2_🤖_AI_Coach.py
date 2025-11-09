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

# ——— Analytics Engine ———
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
pace_delta = recent['pace_min_per_mi'].mean() - early['pace_min_per_mi'].mean()

# 2-Mile Projection
projected_2mi_min = avg_pace * 2
projected_2mi_time = f"{int(projected_2mi_min):02d}:{int((projected_2mi_min % 1)*60):02d}"

# Weekly Volume
df['week'] = df['date'].dt.isocalendar().week
weekly_mi = df.groupby('week')['distance'].sum().tail(4).mean()

# ——— Prompt: Scientist + Coach ———
prompt = f"""You are **Coach Riley** — biomechanics analyst and performance coach. Female. Data-driven. No hype.

Athlete: 39-year-old male. Target: June 2026 PT Test
- 2-mile ≤ 18:00
- 45 push-ups in 60s
- 45 crunches in 120s

Today: {today}
Next session: {next_off.strftime('%A, %b %d')} (Thu/Fri/Sat only)

--- DATASET ---
Sessions: {n_sessions}
Total miles: {total_mi:.1f}
Avg pace: {avg_pace:.2f} min/mi
Best pace: {best_pace:.2f} min/mi
Pace delta (recent vs early): {'+' if pace_delta > 0 else ''}{pace_delta:.2f} min/mi
Push-up max: {pushup_max}
Crunch max: {crunch_max}
Avg felt: {felt_avg:.1f}/5
Avg weekly volume: {weekly_mi:.1f} mi

--- LAST 5 SESSIONS ---
"""
for _, r in df.head(5).iterrows():
    prompt += f"{r['date'].date()}: {r['distance']} mi | {int(r['run_minutes'])}:{int(r['run_seconds']):02d} | {r['pace_min_per_mi']:.2f} min/mi | Felt {r['felt_rating']} | Push-ups {r['pushups']} | Crunches {r['crunches']}\n"

prompt += f"""
--- PRESCRIPTION ---
1. **Performance Diagnosis**: Key limiter (pace, volume, strength, recovery).
2. **Next Session Protocol**: <50 min. Include load, intensity, rest. Bodyweight only.
3. **2-Mile Forecast**: Current = {projected_2mi_time}. Required improvement: {max(0, projected_2mi_min - 18):.1f} min.
4. **Critical Actions**: 1–2 evidence-based fixes (e.g., cadence target, volume ramp, form cue).

Tone: Clinical. Metric-first. Actionable. No emojis. No motivation. Just results.
"""

# ——— Generate ———
if st.button("Get Riley's Analysis"):
    with st.spinner("Riley is processing your data..."):
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 600
            }
            response = requests.post(GROQ_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            analysis = response.json()['choices'][0]['message']['content']
            st.markdown("### Riley’s Performance Report")
            st.write(analysis)
        except Exception as e:
            st.error(f"Error: {e}")

# ——— TALK TO RILEY (Bottom of Page) ———
st.markdown("---")
st.markdown("### Talk to Riley")
user_input = st.text_area("Ask Riley anything — adjust goals, change training days, explain a metric, etc.", height=100)
if st.button("Send to Riley"):
    if user_input.strip():
        with st.spinner("Riley is thinking..."):
            try:
                riley_prompt = f"""You are Coach Riley. Athlete is 39-year-old male. Be concise, data-aware, and direct.

Context: USAF PT Test June 2026. Training Thu/Fri/Sat. Current stats: {n_sessions} sessions, {total_mi:.1f} mi total, {avg_pace:.1f} avg pace.

User asks: {user_input}

Respond in 3–5 sentences. Use metrics if relevant. No fluff."""
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                data = {
                    "model": MODEL,
                    "messages": [{"role": "user", "content": riley_prompt}],
                    "temperature": 0.6,
                    "max_tokens": 300
                }
                response = requests.post(GROQ_URL, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                reply = response.json()['choices'][0]['message']['content']
                st.markdown(f"**Riley:** {reply}")
            except Exception as e:
                st.error(f"Comms error: {e}")
    else:
        st.warning("Type a message first.")
