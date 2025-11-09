import streamlit as st
import pandas as pd
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------
# DB Connection – POSTGRES_URL ONLY
# -------------------------------------------------
def get_db_connection():
    url = st.secrets.get("POSTGRES_URL") or os.getenv("POSTGRES_URL")
    if not url:
        st.error("Missing POSTGRES_URL in Streamlit secrets!")
        st.stop()
    return psycopg2.connect(url)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            distance REAL DEFAULT 2.0,
            run_minutes REAL,
            run_seconds REAL,
            pushups INTEGER DEFAULT 0,
            crunches INTEGER DEFAULT 0,
            felt_rating INTEGER DEFAULT 3 CHECK (felt_rating BETWEEN 1 AND 5)
        )
    ''')
    # Safe upgrades
    for col in [
        "ALTER TABLE logs ADD COLUMN IF NOT EXISTS distance REAL DEFAULT 2.0;",
        "ALTER TABLE logs ADD COLUMN IF NOT EXISTS run_minutes REAL;",
        "ALTER TABLE logs ADD COLUMN IF NOT EXISTS run_seconds REAL;",
        "ALTER TABLE logs ADD COLUMN IF NOT EXISTS felt_rating INTEGER DEFAULT 3;"
    ]:
        try: c.execute(col)
        except: pass
    conn.commit()
    conn.close()

def add_log(date, distance, run_min, run_sec, pushups, crunches, felt):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO logs (date, distance, run_minutes, run_seconds, pushups, crunches, felt_rating)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (date, distance, run_min, run_sec, pushups, crunches, felt))
    conn.commit()
    conn.close()

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM logs ORDER BY date", conn)
    conn.close()
    return df

# -------------------------------------------------
# UI
# -------------------------------------------------
st.set_page_config(page_title="USAF PT Tracker", layout="wide")
st.title("USAF PT Tracker – Log Your Run")

init_db()

with st.form("log_form"):
    st.subheader("Log Today’s Session")
    col1, col2, col3 = st.columns(3)
    with col1:
        date = st.date_input("Date", value=datetime.today())
        distance = st.number_input("Run Distance (miles)", min_value=0.0, value=2.0, step=0.1)
    with col2:
        run_min = st.number_input("Run Time – minutes", min_value=0, value=0, step=1)
        run_sec = st.number_input("Run Time – seconds", min_value=0, max_value=59, value=0, step=1)
    with col3:
        pushups = st.number_input("Push-ups", min_value=0, value=0, step=1)
        crunches = st.number_input("Crunches", min_value=0, value=0, step=1)
    felt = st.slider("How did you feel? (1 = wrecked, 5 = flying)", 1, 5, 3)
    submitted = st.form_submit_button("Log It")
    if submitted:
        add_log(str(date), distance, run_min, run_sec, pushups, crunches, felt)
        st.success("Logged! Coach Riley is analyzing your pace.")
        st.balloons()
