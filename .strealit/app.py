# app.py
import streamlit as st
import psycopg2
from datetime import datetime

# ——— PAGE CONFIG: WIDE + NO CLIPPING ———
st.set_page_config(
    page_title="SOPHIA",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# ——— HIDE STREAMLIT'S AUTO NAV ———
st.markdown("""
<style>
    /* Hide Streamlit's default page navigation menu */
    [data-testid="stSidebarNav"] {display: none !important;}
    
    /* Reduce top padding */
    .block-container {padding-top: 2rem !important;}
</style>
""", unsafe_allow_html=True)

# ——— DATABASE ———
def get_db_connection():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT);
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
            date DATE, distance FLOAT, run_minutes INT, run_seconds INT,
            pushups INT, crunches INT, felt_rating INT
        );
        ALTER TABLE logs ADD COLUMN IF NOT EXISTS user_id INTEGER;
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ——— SESSION ———
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# ——— SIDEBAR: ONLY SHOW WHEN LOGGED IN ———
if st.session_state.get('logged_in', False):
    st.sidebar.success(f"**{st.session_state.username}**")
    
    st.sidebar.page_link("app.py", label="🏠 Home")
    st.sidebar.page_link("pages/01_Dashboard.py", label="📊 Dashboard")
    st.sidebar.page_link("pages/02_AI_Coach.py", label="🤖 SOPHIA Coach")
    
    if st.sidebar.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ——— LOGIN / SIGNUP ———
if not st.session_state.logged_in:
    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<h2 style='text-align: center; line-height: 1.2;'>"
        "WELCOME TO SOPHIA<br>"
        "<small style='color: #666;'>Smart Optimized Performance Health Intelligence Assistant</small>"
        "</h2>",
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Login")
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", use_container_width=True):
            conn = get_db_connection()
            cur = conn.cursor()
            # Case-insensitive username lookup
            cur.execute("SELECT id, username FROM users WHERE LOWER(username) = LOWER(%s) AND password = %s", 
                       (login_user, login_pass))
            user = cur.fetchone()
            if user:
                st.session_state.logged_in = True
                st.session_state.user_id = user[0]
                st.session_state.username = user[1]  # Use actual username from DB (preserves original case)
                st.success("Logged in!")
                st.rerun()
            else:
                st.error("Invalid credentials.")
            cur.close()
            conn.close()

    with col2:
        st.markdown("#### Signup")
        new_user = st.text_input("New Username", key="new_user")
        new_pass = st.text_input("New Password", type="password", key="new_pass")
        if st.button("Create Account", use_container_width=True):
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                # Check if username already exists (case-insensitive)
                cur.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s)", (new_user,))
                if cur.fetchone():
                    st.error("Username already taken (case-insensitive).")
                else:
                    cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (new_user, new_pass))
                    conn.commit()
                    st.success("Account created!")
            except psycopg2.IntegrityError:
                st.error("Username taken.")
            cur.close()
            conn.close()

    st.stop()

# ——— HOME: LOG SESSION ———
st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
st.markdown(f"### Log Session — {st.session_state.username}")

with st.form("log_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        date = st.date_input("Date", value=datetime.today())
        distance = st.number_input("Run (mi)", min_value=0.0, step=0.1)
    with c2:
        run_min = st.number_input("Min", min_value=0, step=1)
        run_sec = st.number_input("Sec", min_value=0, max_value=59, step=1)
    with c3:
        pushups = st.number_input("Push-ups", min_value=0, step=1)
        crunches = st.number_input("Crunches", min_value=0, step=1)
    felt = st.slider("Felt (1–5)", 1, 5, 3)

    if st.form_submit_button("Log Session", use_container_width=True):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO logs (user_id, date, distance, run_minutes, run_seconds, pushups, crunches, felt_rating)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (st.session_state.user_id, date, distance, run_min, run_sec, pushups, crunches, felt))
        conn.commit()
        st.success("Logged!")
        cur.close()
        conn.close()
