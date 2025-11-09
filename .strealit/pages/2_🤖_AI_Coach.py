import streamlit as st
import pandas as pd
import psycopg2
import google.generativeai as genai
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    url = st.secrets.get("POSTGRES_URL") or os.getenv("POSTGRES_URL")
    if not url:
        st.error("Missing POSTGRES_URL!")
        st.stop()
    return psycopg2.connect(url)

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM logs ORDER BY date", conn)
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("Log a run first — Coach Riley needs data to work with!")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time'] = df['run_minutes'] + df['run_seconds']/60
df['pace'] = df['run_time'] / df['distance'].replace(0, pd.NA)

# Valid runs only
runs = df[df['distance'] > 0].copy()

# Next off-day
today = datetime.today().date()
weekday = today.weekday()
days_ahead = (3 - weekday) % 7
if days_ahead == 0: days_ahead = 7
next_off = today + timedelta(days=days_ahead)

# Gemini
gemini_api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
if not gemini_api_key:
    st.info("Add your Gemini key in Streamlit Secrets.")
    st.stop()

genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# Build FULL history prompt
days_to_test = (datetime(2026, 6, 1).date() - today).days
recent = runs.tail(15)

summary = f"""
You are **Coach Riley** — warm, sharp, funny, female coach. No yelling. Just results.

Goal: USAF PT Test June 2026
- 2-mile ≤18:00 (9:00/mi pace)
- 45 push-ups in 1 min
- 45 crunches in 2 min

Current date: {today}
Next workout: {next_off.strftime('%A, %b %d')} (Thu/Fri/Sat only)
Days to test: {days_to_test}

--- FULL RUN HISTORY ---
"""
for _, r in runs.iterrows():
    pace_str = f"{r['pace']:.2f} min/mi" if pd.notna(r['pace']) else "—"
    summary += f"{r['date'].date()}: {r['distance']} mi in {int(r['run_minutes'])}:{int(r['run_seconds']):02d} → {pace_str} | Felt: {r['felt_rating']}/5\n"

summary += f"""
--- STRENGTH ---
Push-ups: {df['pushups'].tolist()[-10:]}
Crunches: {df['crunches'].tolist()[-10:]}

--- CUMULATIVE ---
Total miles: {runs['distance'].sum():.1f}
Total push-ups: {df['pushups'].sum()}
Total crunches: {df['crunches'].sum()}

--- PREDICTION ---
Based on current pace ({runs['pace'].iloc[-1]:.2f} min/mi) over {runs['distance'].iloc[-1]} mi:
→ Projected 2-mile: {(runs['pace'].iloc[-1] * 2):.2f} min

--- INSTRUCTIONS ---
1. Analyze pace, volume, energy (1–5), strength trends
2. If pace drops >20 sec → add intervals
3. If felt <3 → add recovery
4. Build volume gradually
5. Predict 2-mile time
6. Keep workout <50 min, bodyweight
7. Be funny, warm, direct

Respond:
1. Vibe check (funny + real)
2. Next workout (warm-up, main, cooldown)
3. 2-mile prediction
4. Pep talk
"""

if st.button("Get Plan from Coach Riley"):
    with st.spinner("Coach Riley is building your plan..."):
        response = model.generate_content(
            summary,
            generation_config=genai.types.GenerationConfig(
                temperature=0.8,
                max_output_tokens=700
            )
        )
        st.markdown("### Coach Riley’s Game Plan")
        st.write(response.text)
