# app.py - Home/Log Page with Multi-User Login/Signup
import streamlit as st
import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

# ——— DATABASE INIT (Run Once) ———
def init_db():
    conn = psycopg2.connect(st.secrets["POSTGRES_URL"])
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            date DATE NOT NULL,
            distance FLOAT,
            run_minutes INT,
            run_seconds INT,
            pushups INT,
            crunches INT,
            felt_rating INT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ——— SESSION STATE ———
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# ——— LOGIN/SIGNUP UI ———
if not st.session_state.logged_in:
    st.title("SOPHIA Fitness Tracker - Login/Signup")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s AND password = %s", (username, password))
            user = cur.fetchone()
            cur.close()
            conn.close()
            if user:
                st.session_state.logged_in = True
                st.session_state.user_id = user[0]
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid credentials")
    
    with col2:
        st.markdown("### Signup")
        new_user = st.text_input("New Username", key="new_user")
        new_pass = st.text_input("New Password", type="password", key="new_pass")
        if st.button("Signup"):
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (new_user, new_pass))
                conn.commit()
                st.success("Account created! Login now.")
            except psycopg2.IntegrityError:
                st.error("Username taken.")
            finally:
                cur.close()
                conn.close()
    st.stop()

# ——— LOGGED IN UI ———
st.sidebar.success(f"Logged in: {st.session_state.username}")
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.title(f"Log Session, {st.session_state.username}")

with st.form("log_form"):
    st.subheader("Log Today’s Session")
    col1, col2, col3 = st.columns(3)
    with col1:
        date = st.date_input("Date", value=datetime.today())
        distance = st.number_input("Run Distance (miles)", min_value=0.0, value=2.0, step=0.1)
    with col2:
        run_min = st.number_input("Run Minutes", min_value=0, value=0, step=1)
        run_sec = st.number_input("Run Seconds", min_value=0, max_value=59, value=0, step=1)
    with col3:
        pushups = st.number_input("Push-ups", min_value=0, value=0, step=1)
        crunches = st.number_input("Crunches", min_value=0, value=0, step=1)
    felt = st.slider("Felt Rating (1 = Wrecked, 5 = Flying)", 1, 5, 3)
    submitted = st.form_submit_button("Log Session")
    if submitted:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO logs (user_id, date, distance, run_minutes, run_seconds, pushups, crunches, felt_rating)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (st.session_state.user_id, date, distance, run_min, run_sec, pushups, crunches, felt))
        conn.commit()
        cur.close()
        conn.close()
        st.success("Session logged!")
