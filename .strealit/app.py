# app.py
import streamlit as st
import psycopg2
import os

# ——— DATABASE CONNECTION ———
def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— FORCE RECREATE DATABASE (EVERY START) ———
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    
    # Read and execute schema.sql
    schema_path = "../schema.sql"
    if os.path.exists(schema_path):
        with open(schema_path, "r") as f:
            sql = f.read()
            cur.execute(sql)
        st.success("Database schema loaded from schema.sql")
    else:
        st.error("schema.sql not found!")
    
    conn.commit()
    conn.close()

# ——— RUN INIT_DB ON EVERY LOAD ———
init_db()  # This runs every time the app starts

# ——— SESSION STATE ———
for key in ['logged_in', 'user_id', 'username', 'role']:
    if key not in st.session_state:
        st.session_state[key] = None
st.session_state.logged_in = st.session_state.user_id is not None

# ——— SIDEBAR ———
def sidebar():
    st.sidebar.success(f"**{st.session_state.username}**")
    st.sidebar.page_link("../app.py", label="Home")
    st.sidebar.page_link("../pages/01_Dashboard.py", label="Dashboard")
    st.sidebar.page_link("../pages/02_Log_Workout.py", label="Log Workout")
    st.sidebar.page_link("../pages/03_Goals.py", label="Goals")
    st.sidebar.page_link("../pages/04_AI_Coach.py", label="SOPHIA Coach")
    if st.session_state.role == 'admin':
        st.sidebar.page_link("../pages/05_Admin.py", label="Admin")
    if st.sidebar.button("Logout", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ——— LOGIN / SIGNUP ———
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>SOPHIA</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Smart Optimized Performance Health Intelligence Assistant</p>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Signup"])

    with tab1:
        with st.form("login_form"):
            st.write("### Login")
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            login_btn = st.form_submit_button("Login")
            if login_btn:
                if not username or not password:
                    st.error("Please fill in both fields.")
                else:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id, username, COALESCE(role, 'user') FROM users WHERE LOWER(username)=LOWER(%s) AND password=%s",
                        (username, password)
                    )
                    user = cur.fetchone()
                    conn.close()
                    if user:
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1]
                        st.session_state.role = user[2]
                        st.session_state.logged_in = True
                        st.success("Logged in!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")

    with tab2:
        with st.form("signup_form"):
            st.write("### Create Account")
            new_user = st.text_input("Choose Username", key="signup_user")
            new_pass = st.text_input("Choose Password", type="password", key="signup_pass")
            signup_btn = st.form_submit_button("Signup")
            if signup_btn:
                if not new_user or not new_pass:
                    st.error("Please fill in both fields.")
                else:
                    conn = get_conn()
                    cur = conn.cursor()
                    try:
                        cur.execute(
                            "INSERT INTO users (username, password, role) VALUES (%s, %s, 'user') RETURNING id, username",
                            (new_user, new_pass)
                        )
                        user = cur.fetchone()
                        conn.commit()
                        st.success(f"Account created for **{user[1]}**! Please log in.")
                    except psycopg2.IntegrityError:
                        st.error("Username already taken.")
                    finally:
                        conn.close()

else:
    sidebar()
    st.markdown(f"## Welcome, **{st.session_state.username}**")
    st.info("Use the sidebar to navigate.")

    # ——— ADMIN PROMOTION BUTTON ———
    if st.session_state.username == "ianconner":  # CHANGE TO YOUR USERNAME
        st.sidebar.markdown("---")
        st.sidebar.markdown("### DEV MODE")
        if st.sidebar.button("PROMOTE TO ADMIN", type="primary", use_container_width=True):
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE users SET role='admin' WHERE id=%s", (st.session_state.user_id,))
            conn.commit()
            conn.close()
            st.session_state.role = 'admin'
            st.sidebar.success("ADMIN UNLOCKED")
            st.balloons()
            st.rerun()
