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
    st.warning("Log a session — Sophia needs data.")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)

valid_df = df[df['distance'] > 0].copy()
last_n = valid_df.head(5)
avg_pace = last_n['pace_min_per_mi'].mean() if not last_n.empty else pd.NA
projected_2mi_min = avg_pace * 2 if pd.notna(avg_pace) else pd.NA
projected_str = f"{int(projected_2mi_min):02d}:{int((projected_2mi_min % 1)*60):02d}" if pd.notna(projected_2mi_min) else "N/A"

# ——— LOAD GOALS FROM DASHBOARD (Shared via session_state) ———
GOAL_RUN_MIN = st.session_state.get("goal_run_min", 18.0)
GOAL_PUSH = st.session_state.get("goal_push", 45)
GOAL_CRUNCH = st.session_state.get("goal_crunch", 45)

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
pushup_max = df['pushups'].max()
crunch_max = df['crunches'].max()
vo2_estimate = 42 + (9 - (avg_pace if pd.notna(avg_pace) else 10)) if pd.notna(avg_pace) else "N/A"

# ——— SOPHIA PROMPT (Science + Dynamic Goals) ———
prompt = f"""You are **Sophia** — Smart Optimized Performance Health Intelligence Assistant. Female. Data scientist + performance coach.

Athlete: 39-year-old male. Training Thu/Fri/Sat.
**Goals**: 2-mile ≤ {GOAL_RUN_MIN}:00 | {GOAL_PUSH} push-ups | {GOAL_CRUNCH} crunches by June 2026.

Today: {today}
Next session: {next_off.strftime('%A, %b %d')}

--- DATA SNAPSHOT ---
Sessions: {n_sessions}
Last 5 avg pace: {avg_pace:.2f} min/mi → Projected 2-mile: {projected_str}
VO₂ max estimate: {vo2_estimate} mL/kg/min (Daniels' formula)
Push-up max: {pushup_max} | Crunch max: {crunch_max}

--- LAST 5 SESSIONS ---
"""
for _, r in df.head(5).iterrows():
    pace_val = f"{r['pace_min_per_mi']:.2f}" if pd.notna(r['pace_min_per_mi']) else "—"
    prompt += f"{r['date'].date()}: {r['distance']} mi | {int(r['run_minutes'])}:{int(r['run_seconds']):02d} | {pace_val} min/mi | Felt {r['felt_rating']}/5 | Push-ups {r['pushups']} | Crunches {r['crunches']}\n"

prompt += f"""
--- PRESCRIPTION (Evidence-Based) ---
1. **Limiter Diagnosis**: Aerobic capacity, lactate threshold, or neuromuscular?
2. **Next Session Protocol**: <50 min. Include intensity (HR zone, RPE), volume, rest.
3. **4-Week Microcycle**: Progression based on Seiler, Daniels, or Bompa.
4. **Key Metric to Track**: Cadence, eccentric load, or recovery HR.

Tone: Clinical. Cite science. No hype. Goal-aware.
"""

# ——— Generate ———
if st.button("Get Sophia's Protocol"):
    with st.spinner("Sophia is analyzing..."):
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
            st.markdown("### Sophia's Optimized Protocol")
            st.write(analysis)
        except Exception as e:
            st.error(f"Error: {e}")

# ——— TALK TO SOPHIA ———
st.markdown("---")
st.markdown("### Talk to Sophia")
user_q = st.text_input("Ask about goals, science, adjustments...")
if st.button("Send"):
    if user_q:
        with st.spinner("Sophia is thinking..."):
            q_prompt = f"""Sophia answering: {user_q}

Context: Goals are 2-mile ≤ {GOAL_RUN_MIN}:00, {GOAL_PUSH} push-ups, {GOAL_CRUNCH} crunches.
Current avg pace: {avg_pace:.2f} min/mi. Use science. 3–5 sentences."""
            # ... [same Groq call] ...
            reply = response.json()['choices'][0]['message']['content']
            st.markdown(f"**Sophia:** {reply}")
