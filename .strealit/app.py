# app.py
import streamlit as st
import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

# ——— DATABASE INIT ———
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

# ——— LOGIN SYSTEM ———
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("SOPHIA — Login")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            conn = psycopg2.connect(st.secrets["POSTGRES_URL"])
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
                st.error("Invalid username or password")
    
    with col2:
        st.markdown("### New User?")
        new_user = st.text_input("Choose Username", key="new_user")
        new_pass = st.text_input("Choose Password", type="password", key="new_pass")
        if st.button("Create Account"):
            try:
                conn = psycopg2.connect(st.secrets["POSTGRES_URL"])
                cur = conn.cursor()
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (new_user, new_pass))
                conn.commit()
                st.success("Account created! Now login.")
            except psycopg2.IntegrityError:
                st.error("Username already taken.")
            finally:
                cur.close()
                conn.close()
    st.stop()

# ——— LOGGED IN: SHOW NAV ———
st.sidebar.success(f"Logged in: {st.session_state.username}")
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ——— NAVIGATION ———
st.sidebar.page_link("app.py", label="Home")
st.sidebar.page_link("pages/1_📊_Dashboard.py", label="Dashboard")
st.sidebar.page_link("pages/2_🤖_AI_Coach.py", label="SOPHIA Coach")

st.title(f"Welcome, {st.session_state.username}")
st.write("Use the sidebar to navigate.")
