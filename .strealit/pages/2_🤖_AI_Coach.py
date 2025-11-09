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
model = genai.GenerativeModel('gemini-2.5-flash')  # Your upgrade — correct!

# Build prompt
summary = f"""
You are Coach Riley, a witty, motivational female coach — upbeat gym buddy with sass.

Goal: USAF PT test June 2026
- 2-mile in ≤18:00
- 45 push-ups
- 45 crunches

Today: {today}
Next workout: {next_off.strftime('%A, %b %d')}
Days to test: {(datetime(2026, 6, 1).date() - today).days}

Recent runs (pace min/mi):
"""
for _, r in df[df['distance'] > 0].tail(5).iterrows():
    summary += f"- {r['date'].date()}: {r['distance']} mi in {int(r['run_minutes'])}:{int(r['run_seconds']):02d} → {r['pace']} | Felt {r['felt_rating']}/5\n"

summary += """
Give:
1. Vibe check (funny, encouraging)
2. Next workout (<50 min, bodyweight)
3. 2-mile prediction
4. Pep talk
"""

# Generate with retry on block
if st.button("Get Plan from Coach Riley"):
    with st.spinner("Coach Riley is cooking..."):
        for attempt in range(3):
            try:
                response = model.generate_content(
                    summary,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.8 + (attempt * 0.1),  # Increase temp on retry
                        max_output_tokens=500
                    ),
                    safety_settings=[
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    ]
                )

                # Safe text extraction
                if response.candidates and response.candidates[0].content.parts and response.candidates[0].content.parts[0].text:
                    plan = response.candidates[0].content.parts[0].text
                    st.markdown("### Coach Riley’s Plan")
                    st.write(plan)
                    break  # Success!
                else:
                    st.warning("Response blocked — retrying...")
            except Exception as e:
                st.error(f"Error on attempt {attempt+1}: {e}")
