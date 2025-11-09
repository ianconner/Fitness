import streamlit as st
import pandas as pd
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------
# PostgreSQL Connection
# -------------------------------------------------
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        database=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASS"),
        port=os.getenv("PG_PORT", "5432")
    )

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            run_minutes REAL,
            run_seconds REAL,
            pushups INTEGER,
            crunches INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def add_log(date, run_min, run_sec, pushups, crunches):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO logs (date, run_minutes, run_seconds, pushups, crunches)
        VALUES (%s, %s, %s, %s, %s)
    ''', (date, run_min, run_sec, pushups, crunches))
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
st.title("USAF PT Tracker – Log Your Grind")

init_db()

with st.form("log_form"):
    st.subheader("Log Today’s Session")
    col1, col2 = st.columns(2)

    with col1:
        date = st.date_input("Date", value=datetime.today())
        run_min = st.number_input("Run – minutes", min_value=0, value=0, step=1)
        run_sec = st.number_input("Run – seconds", min_value=0, max_value=59, value=0, step=1)
    with col2:
        pushups = st.number_input("Push-ups (1 min max)", min_value=0, value=0, step=1)
        crunches = st.number_input("Crunches (2 min max)", min_value=0, value=0, step=1)

    submitted = st.form_submit_button("Save Log")
    if submitted:
        add_log(str(date), run_min, run_sec, pushups, crunches)
        st.success("Logged! Head to Dashboard or AI Coach.")
