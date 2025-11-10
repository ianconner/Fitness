import streamlit as st
import sqlite3
from datetime import date

if 'user_id' not in st.session_state or st.session_state.user_id is None:
    st.error("Please login first.")
    st.stop()

user_id = st.session_state.user_id

st.title("Log a Run")

run_date = st.date_input("Date", value=date.today())
distance = st.number_input("Distance (km)", min_value=0.0, step=0.1)
time = st.number_input("Time (minutes)", min_value=0.0, step=0.1)

if st.button("Log Run"):
    if distance > 0 and time > 0:
        pace = time / distance
        conn = sqlite3.connect('running_logs.db')
        cur = conn.cursor()
        cur.execute("INSERT INTO logs (user_id, date, distance, time, pace) VALUES (?, ?, ?, ?, ?)",
                    (user_id, run_date.strftime("%Y-%m-%d"), distance, time, pace))
        conn.commit()
        conn.close()
        st.success("Run logged successfully!")
    else:
        st.error("Distance and time must be greater than 0.")

# Sidebar
with st.sidebar:
    st.title("Navigation")
    st.page_link("app.py", label="Home")
    st.page_link("pages/01_Dashboard.py", label="Dashboard")
    st.page_link("pages/02_Log_Run.py", label="Log a Run")
    st.page_link("pages/04_Coach.py", label="Coach")
    if st.session_state.role == 'admin':
        st.page_link("pages/03_Admin.py", label="Admin")
    if st.button("Logout"):
        del st.session_state.user_id
        del st.session_state.role
        st.experimental_rerun()
