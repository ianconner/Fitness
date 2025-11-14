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
    try:
        schema_sql = """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='role') THEN
                ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';
            END IF;
        END $$;

        UPDATE users SET role = 'user' WHERE role IS NULL;

        DROP TABLE IF EXISTS workout_exercises, workouts, goals CASCADE;

        CREATE TABLE IF NOT EXISTS goals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            exercise TEXT NOT NULL,
            metric_type TEXT NOT NULL CHECK (metric_type IN ('time_min','reps','weight_lbs','distance_mi')),
            target_value NUMERIC NOT NULL,
            target_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS workouts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            workout_date DATE NOT NULL,
            notes TEXT NOT NULL,
            duration_min INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS workout_exercises (
            id SERIAL PRIMARY KEY,
            workout_id INTEGER REFERENCES workouts(id) ON DELETE CASCADE,
            exercise TEXT NOT NULL,
            sets INTEGER,
            reps INTEGER,
            weight_lbs NUMERIC,
            time_min NUMERIC,
            rest_min NUMERIC,
            distance_mi NUMERIC
        );
        """
        cur.execute(schema_sql)
        conn.commit()
        st.success("Database schema initialized!")
    except Exception as e:
        conn.rollback()
        st.error(f"Schema error: {e}")
    finally:
        cur.close()
        conn.close()

init_db()

# ——— SESSION STATE ———
for key in ['logged_in', 'user_id', 'username', 'role', 'just_logged_in', 'current_page', 'goals_updated']:
    if key not in st.session_state:
        st.session_state[key] = None
st.session_state.logged_in = st.session_state.user_id is not None

# ——— AUTO-PROMOTE ianconner TO ADMIN ———
if st.session_state.logged_in and st.session_state.username == "ianconner" and st.session_state.role != "admin":
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET role='admin' WHERE username='ianconner'")
        conn.commit()
        st.session_state.role = 'admin'
    finally:
        conn.close()
    st.rerun()

# ——— RISE SIDEBAR ———
def render_sidebar():
    st.markdown("""
    <style>
    [data-testid="stSidebarNav"] { display: none !important; }
    a[href*="?page="] { display: none !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { display: none !important; }

    .sidebar .stButton > button {
        background: linear-gradient(135deg, #1E1E1E, #2A2A2A) !important;
        color: white !important;
        border: 1px solid #333 !important;
        border-radius: 12px !important;
        padding: 14px !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        margin: 10px 0 !important;
        width: 100% !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
        transition: all 0.3s ease !important;
    }
    .sidebar .stButton > button:hover {
        background: linear-gradient(135deg, #333, #444) !important;
        border-color: #00FF88 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 8px rgba(0,255,136,0.2) !important;
    }
    .sidebar .stSuccess {
        background: #0A0A0A !important;
        color: #00FF88 !important;
        border: 1px solid #00FF88 !important;
        border-radius: 12px !important;
        padding: 12px !important;
        text-align: center !important;
        font-weight: 700 !important;
        font-size: 18px !important;
        margin-bottom: 20px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.sidebar.success(f"**{st.session_state.username}**")

    if st.sidebar.button("Home", key="nav_home", use_container_width=True):
        st.session_state.current_page = "home"
        st.rerun()
    if st.sidebar.button("Dashboard", key="nav_dash", use_container_width=True):
        st.session_state.current_page = "dashboard"
        st.rerun()
    if st.sidebar.button("Log Workout", key="nav_log", use_container_width=True):
        st.session_state.current_page = "log_workout"
        st.rerun()
    if st.sidebar.button("Goals", key="nav_goals", use_container_width=True):
        st.session_state.current_page = "goals"
        st.rerun()
    if st.sidebar.button("RISE Coach", key="nav_coach", use_container_width=True):
        st.session_state.current_page = "ai_coach"
        st.rerun()
    if st.session_state.role == 'admin':
        if st.sidebar.button("Admin", key="nav_admin", use_container_width=True):
            st.session_state.current_page = "admin"
            st.rerun()
    
    if st.sidebar.button("Logout", key="nav_logout", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ——— LOGIN / SIGNUP ———
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>RISE</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Resilient Integrated Strength Engine</p>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Signup"])

    with tab1:
        with st.form("main_login_form"):
            st.write("### Login")
            username = st.text_input("Username", key="main_login_user")
            password = st.text_input("Password", type="password", key="main_login_pass")
            if st.form_submit_button("Login"):
                if not username or not password:
                    st.error("Fill both fields.")
                else:
                    conn = get_conn()
                    cur = conn.cursor()
                    try:
                        cur.execute(
                            "SELECT id, username, COALESCE(role,'user') FROM users WHERE LOWER(username)=LOWER(%s) AND password=%s",
                            (username, password)
                        )
                        user = cur.fetchone()
                        if user:
                            st.session_state.update(dict(zip(['user_id','username','role'], user)))
                            st.session_state.logged_in = True
                            st.session_state.just_logged_in = True
                            st.session_state.current_page = "home"
                            st.session_state.force_goal_refresh = False
                            st.rerun()
                        else:
                            st.error("Invalid credentials")
                    finally:
                        conn.close()

    with tab2:
        with st.form("main_signup_form"):
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
                        cur.execute(
                            "INSERT INTO users (username,password,role) VALUES (%s,%s,'user') RETURNING id,username",
                            (new_user, new_pass)
                        )
                        user = cur.fetchone()
                        conn.commit()
                        st.success(f"Created {user[1]}! Log in.")
                    except psycopg2.IntegrityError:
                        st.error("Username taken.")
                        conn.rollback()
                    finally:
                        conn.close()
else:
    render_sidebar()

    if st.session_state.get("just_logged_in"):
        del st.session_state["just_logged_in"]
        st.success("Logged in!")
        st.rerun()

    page = st.session_state.get("current_page", "home")

    if page == "home":
        st.markdown(f"## Welcome, **{st.session_state.username}**")
        st.info("Use the sidebar to navigate.")
    
    elif page == "dashboard":
        import pages.dashboard as p
        p.main()
    elif page == "log_workout":
        import pages.log_workout as p
        p.main()
    elif page == "goals":
        import pages.goals as p
        p.main()
    elif page == "ai_coach":
        import pages.ai_coach as p
        p.main()
    elif page == "admin":
        import pages.admin as p
        p.main()
    else:
        st.session_state.current_page = "home"
        st.rerun()
