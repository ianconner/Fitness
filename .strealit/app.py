import streamlit as st
import sqlite3
from datetime import datetime

# Initialize the database
def init_db():
    conn = sqlite3.connect('running_logs.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            distance REAL NOT NULL,
            time REAL NOT NULL,
            pace REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    # Add role column if it doesn't exist
    cur.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cur.fetchall()]
    if 'role' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    conn.commit()
    conn.close()

init_db()

# Session state for logged-in user
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'role' not in st.session_state:
    st.session_state.role = None

# Sidebar for navigation (shown after login)
def show_sidebar():
    with st.sidebar:
        st.title("Navigation")
        st.page_link("app.py", label="Home")
        st.page_link("pages/01_Dashboard.py", label="Dashboard")
        st.page_link("pages/02_Log_Run.py", label="Log a Run")
        st.page_link("pages/04_Coach.py", label="Coach")  # Assuming Coach is 04
        if st.session_state.role == 'admin':
            st.page_link("pages/03_Admin.py", label="Admin")
        if st.button("Logout"):
            del st.session_state.user_id
            del st.session_state.role
            st.experimental_rerun()  # Redirect to homepage

# Main app
st.title("Running Pace Dashboard")

if st.session_state.user_id is None:
    # Login/Signup form
    tab1, tab2 = st.tabs(["Login", "Signup"])

    with tab1:
        st.subheader("Login")
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            conn = sqlite3.connect('running_logs.db')
            cur = conn.cursor()
            cur.execute("SELECT id, role FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", (login_user, login_pass))
            user = cur.fetchone()
            conn.close()
            if user:
                st.session_state.user_id = user[0]
                st.session_state.role = user[1]
                st.success("Logged in successfully!")
                st.experimental_rerun()
            else:
                st.error("Invalid username or password")

    with tab2:
        st.subheader("Signup")
        new_user = st.text_input("New Username", key="new_user")
        new_pass = st.text_input("New Password", type="password", key="new_pass")
        if st.button("Signup"):
            conn = sqlite3.connect('running_logs.db')
            cur = conn.cursor()
            try:
                cur.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (new_user,))
                if cur.fetchone():
                    st.error("Username already exists")
                else:
                    cur.execute("INSERT INTO users (username, password, created_at, role) VALUES (?, ?, ?, 'user')",
                                (new_user, new_pass, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success("Account created! Please login.")
            except sqlite3.IntegrityError:
                st.error("Username already exists")
            conn.close()
else:
    show_sidebar()
    st.write(f"Welcome back, {st.session_state.user_id}!")  # Placeholder; can customize
