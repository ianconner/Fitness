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
    url = st.secrets.get("POSTGRES_URL") or os.getenv("POSTGRES_URL")
    if not url:
        st.error("Missing POSTGRES_URL in secrets!")
        st.stop()
    return psycopg2.connect(url)

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM logs ORDER BY date DESC LIMIT 15", conn)
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("Log a workout first — Coach Riley needs data!")
    st.stop()

df['date'] = pd.to_datetime(df['date'])
df['run_time'] = df['run_minutes'] + df['run_seconds'] / 60
df['pace'] = (df['run_time'] / df['distance'].replace(0, pd.NA)).round(2)

# Next workout day (Thu/Fri/Sat)
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
model = genai.GenerativeModel('gemini-1.5-flash')  # Stable, fast, reliable

# Build SHORT, SAFE prompt
summary = f"""
You are **Coach Riley**, a sharp, funny, female PT coach. Be warm, direct, sassy.

Goal: USAF PT Test June 2026
- 2-mile ≤18:00
- 45 push-ups
- 45 crunches

Today: {today}
Next workout: {next_off.strftime('%A, %b %d')} (Thu/Fri/Sat only)
Days to test: {(datetime(2026, 6, 1).date() - today).days}

Recent runs (pace in min/mi):
"""
for _, r in df[df['distance'] > 0].tail(5).iterrows():
    summary += f"- {r['date'].date()}: {r['distance']} mi in {int(r['run_minutes'])}:{int(r['run_seconds']):02d} → {r['pace']} min/mi | Felt {r['felt_rating']}/5\n"

summary += f"""
Strength: Push-ups {df['pushups'].iloc[-1]}, Crunches {df['crunches'].iloc[-1]}

Give:
1. Vibe check (funny + real)
2. Next workout (<50 min, bodyweight)
3. 2-mile prediction
4. Pep talk
"""

# Generate with safety OFF + robust response handling
if st.button("Get Plan from Coach Riley"):
    with st.spinner("Coach Riley is cooking..."):
        try:
            response = model.generate_content(
                summary,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.8,
                    max_output_tokens=500
                ),
                safety_settings=[
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                ]
            )

            # SAFE TEXT EXTRACTION
            if response.candidates and response.candidates[0].content.parts:
                plan = response.candidates[0].content.parts[0].text
                st.markdown("### Coach Riley’s Plan")
                st.write(plan)
            else:
                st.warning("Response blocked. Try again or simplify data.")
        except Exception as e:
            st.error(f"AI error: {e}")
