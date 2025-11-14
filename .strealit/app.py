# .strealit/app.py
import streamlit as st
import psycopg2
from sqlalchemy import create_engine

# ——— DATABASE ENGINE ———
engine = create_engine(st.secrets["POSTGRES_URL"])
def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— INITIALIZE DATABASE ———
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    schema_sql = """
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='role') THEN
            ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';
        END IF;
    END $$;
    UPDATE users SET role = 'user' WHERE role IS NULL;
    DROP TABLE IF EXISTS workout_exercises, workouts, goals CASCADE;
    CREATE TABLE goals (
        id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        exercise TEXT NOT NULL, metric_type TEXT NOT NULL CHECK (metric_type IN ('time_min','reps','weight_lbs','distance_mi')),
        target_value NUMERIC NOT NULL, target_date DATE NOT NULL, created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE workouts (
        id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        workout_date DATE NOT NULL, notes TEXT NOT NULL, duration_min INTEGER, created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE workout_exercises (
        id SERIAL PRIMARY KEY, workout_id INTEGER REFERENCES workouts(id) ON DELETE CASCADE,
        exercise TEXT NOT NULL, sets INTEGER, reps INTEGER, weight_lbs NUMERIC,
        time_min NUMERIC, rest_min NUMERIC, distance_mi NUMERIC
    );
    """
    cur.execute(schema_sql)
    st.success("Database schema loaded!")
    conn.commit()
    conn.close()

init_db()

# ——— SESSION STATE ———
for key in ['logged_in', 'user_id', 'username', 'role', 'just_logged_in']:
    if key not in st.session_state:
        st.session_state[key] = None
st.session_state.logged_in = st.session_state.user_id is not None

# ——— AUTO-PROMOTE ianconner TO ADMIN ———
if st.session_state.logged_in and st.session_state.username == "ianconner" and st.session_state.role != "admin":
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET role='admin' WHERE username='ianconner'")
    conn.commit()
    conn.close()
    st.session_state.role = 'admin'
    st.rerun()

# ——— STYLED SIDEBAR ———
def sidebar():
    st.sidebar.success(f"**{st.session_state.username}**")
    
    st.markdown("""
    <style>
    .sidebar .stButton > button {
        background-color: #1E1E1E !important;
        color: white !important;
        border: 1px solid #333 !important;
        border-radius: 8px !important;
        padding: 10px !important;
        font-weight: 500 !important;
        margin: 5px 0 !important;
        width: 100% !important;
    }
    .sidebar .stButton > button:hover {
        background-color: #333 !important;
        border-color: #555 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    if st.sidebar.button("Home", key="nav_home", use_container_width=True):
        st.rerun()
    if st.sidebar.button("Dashboard", key="nav_dash", use_container_width=True):
        st.switch_page("pages/01_Dashboard.py")
    if st.sidebar.button("Log Workout", key="nav_log", use_container_width=True):
        st.switch_page("pages/02_Log_Workout.py")
    if st.sidebar.button("Goals", key="nav_goals", use_container_width=True):
        st.switch_page("pages/03_Goals.py")
    if st.sidebar.button("SOPHIA Coach", key="nav_coach", use_container_width=True):
        st.switch_page("pages/04_AI_Coach.py")
    if st.session_state.role == 'admin':
        if st.sidebar.button("Admin", key="nav_admin", use_container_width=True):
            st.switch_page("pages/05_Admin.py")
    
    if st.sidebar.button("Logout", key="nav_logout", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ——— LOGIN / SIGNUP ———
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>SOPHIA</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Smart Optimized Performance Health Intelligence Assistant</p>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Signup"])
    with tab1:
        with st.form("main_login_form"):  # UNIQUE KEY
            st.write("### Login")
            username = st.text_input("Username", key="main_login_user")
            password = st.text_input("Password", type="password", key="main_login_pass")
            if st.form_submit_button("Login"):
                if not username or not password:
                    st.error("Fill both fields.")
                else:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("SELECT id, username, COALESCE(role,'user') FROM users WHERE LOWER(username)=LOWER(%s) AND password=%s", (username, password))
                    user = cur.fetchone()
                    conn.close()
                    if user:
                        st.session_state.update(dict(zip(['user_id','username','role'], user)))
                        st.session_state.logged_in = True
                        st.session_state.just_logged_in = True
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
    with tab2:
        with st.form("main_signup_form"):  # UNIQUE KEY
            st.write("### Signup")
            new_user = st.text_input("Username", key="main_signup_user")
            new_pass = st.text_input("Password", type="password", key="main_signup_pass")
            if st.form_submit_button("Signup"):
                if not new_user or not new_pass:
                    st.error("Fill both fields.")
                else:
                    conn = get_conn()
                    cur = conn.cursor()
                    try:
                        cur.execute("INSERT INTO users (username,password,role) VALUES (%s,%s,'user') RETURNING id,username", (new_user,new_pass))
                        user = cur.fetchone()
                        conn.commit()
                        st.success(f"Created {user[1]}! Log in.")
                    except psycopg2.IntegrityError:
                        st.error("Username taken.")
                    finally:
                        conn.close()
else:
    if st.session_state.get("just_logged_in"):
        del st.session_state["just_logged_in"]
        st.success("Logged in!")
        st.rerun()
    sidebar()
    st.markdown(f"## Welcome, **{st.session_state.username}**")
    st.info("Use the sidebar to navigate.")
