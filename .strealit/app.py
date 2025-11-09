import streamlit as st
import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

# ——— DB CONNECTION ———
def get_db_connection():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— INIT DB (With ALTER for user_id) ———
def init_db():
    conn = get_db_connection()
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
        ALTER TABLE logs ADD COLUMN IF NOT EXISTS user_id INTEGER;
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ——— SESSION STATE ———
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# ——— LOGIN / SIGNUP ———
if not st.session_state.logged_in:
    st.title("SOPHIA — Login or Signup")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Login")
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            conn = None
            cur = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username = %s AND password = %s", (login_user, login_pass))
                user = cur.fetchone()
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user[0]
                    st.session_state.username = login_user
                    st.success("Logged in!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if cur: cur.close()
                if conn: conn.close()

    with col2:
        st.markdown("### Signup")
        new_user = st.text_input("New Username", key="new_user")
        new_pass = st.text_input("New Password", type="password", key="new_pass")
        if st.button("Create Account"):
            conn = None
            cur = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (new_user, new_pass))
                conn.commit()
                st.success("Account created! Now login.")
            except psycopg2.IntegrityError:
                st.error("Username already taken.")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if cur: cur.close()
                if conn: conn.close()
    st.stop()

# ——— LOGGED IN: NAV + LOG FORM ———
st.sidebar.success(f"Logged in: {st.session_state.username}")
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.sidebar.page_link("app.py", label="Home")
st.sidebar.page_link("pages/1_📊_Dashboard.py", label="Dashboard")
st.sidebar.page_link("pages/2_🤖_AI_Coach.py", label="SOPHIA Coach")

st.title(f"Log Session — {st.session_state.username}")

with st.form("log_form"):
    st.subheader("Today’s Session")
    col1, col2, col3 = st.columns(3)
    with col1:
        date = st.date_input("Date", value=datetime.today())
        distance = st.number_input("Run Distance (mi)", min_value=0.0, value=0.0, step=0.1)
    with col2:
        run_min = st.number_input("Run Minutes", min_value=0, value=0, step=1)
        run_sec = st.number_input("Run Seconds", min_value=0, max_value=59, value=0, step=1)
    with col3:
        pushups = st.number_input("Push-ups", min_value=0, value=0, step=1)
        crunches = st.number_input("Crunches", min_value=0, value=0, step=1)
    felt = st.slider("Felt Rating (1=Bad, 5=Great)", 1, 5, 3)

    if st.form_submit_button("Log Session"):
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO logs (user_id, date, distance, run_minutes, run_seconds, pushups, crunches, felt_rating)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (st.session_state.user_id, date, distance, run_min, run_sec, pushups, crunches, felt))
            conn.commit()
            st.success("Session logged!")
            st.balloons()
        except Exception as e:
            st.error(f"Error: {e}")
        finally:
            if cur: cur.close()
            if conn: conn.close()
