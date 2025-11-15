# app.py
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

        -- Add notes to workout_exercises if missing
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='workout_exercises' AND column_name='notes') THEN
                ALTER TABLE workout_exercises ADD COLUMN notes TEXT;
            END IF;
        END $$;
        """
        cur.execute(schema_sql)

        # Check for ianconner and promote him to admin if he exists (setup logic)
        cur.execute("SELECT id FROM users WHERE username = 'ianconner'")
        if cur.fetchone():
            cur.execute("UPDATE users SET role = 'admin' WHERE username = 'ianconner' AND role != 'admin'")
        
        conn.commit()
        st.session_state['db_initialized'] = True
    except Exception as e:
        st.error(f"DB Error: {e}")
    finally:
        cur.close()
        conn.close()

if 'db_initialized' not in st.session_state:
    init_db()

# ——— AUTHENTICATION LOGIC ———

def check_password(username, password):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, role, password FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        
        if user and user[3] == password: # Simple plaintext comparison
            st.session_state.user_id = user[0]
            st.session_state.username = user[1]
            st.session_state.role = user[2]
            return True
    finally:
        conn.close()
    return False

def logout():
    st.session_state.clear()
    st.rerun()

def render_sidebar():
    with st.sidebar:
        # === FIX FOR DOUBLE BUTTONS ===
        # This CSS hack hides the default Streamlit sidebar navigation
        st.markdown("""
        <style>
            [data-testid="stSidebarNav"] { display: none !important; }
        </style>
        """, unsafe_allow_html=True)
        # === END FIX ===

        st.markdown(f"## Welcome, **{st.session_state.username}**")
        st.caption(f"Role: {st.session_state.role.upper()}")
        st.markdown("---")

        # Navigation
        st.markdown("### Navigation")
        
        # This is the ONLY set of navigation buttons.
        if st.sidebar.button("📊 Dashboard", key="nav_dashboard", use_container_width=True):
            st.session_state.current_page = "dashboard"
            st.rerun()
        if st.sidebar.button("🏋️ Log Workout", key="nav_log_workout", use_container_width=True):
            st.session_state.current_page = "log_workout"
            st.rerun()
        if st.sidebar.button("🎯 Goals", key="nav_goals", use_container_width=True):
            st.session_state.current_page = "goals"
            st.rerun()
        if st.sidebar.button("🤖 AI Coach (RISE)", key="nav_ai_coach", use_container_width=True):
            st.session_state.current_page = "ai_coach"
            st.rerun()

        if st.session_state.role == 'admin':
            st.markdown("### Admin")
            if st.sidebar.button("⚙️ Admin Panel", key="nav_admin", use_container_width=True):
                st.session_state.current_page = "admin"
                st.rerun()

        st.markdown("---")
        if st.button("Logout", key="logout_button", use_container_width=True):
            logout()

# ——— MAIN APP FLOW ———

st.set_page_config(
    page_title="RISE Fitness Tracker",
    page_icon="🏋️",
    layout="wide"
)

if 'user_id' not in st.session_state:
    st.title("RISE Fitness Tracker")
    st.info("Log in or sign up to get started.")

    login_tab, signup_tab = st.tabs(["Login", "Sign Up"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In", type="primary")

            if submitted:
                if check_password(username, password):
                    st.session_state.just_logged_in = True
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    with signup_tab:
        with st.form("signup_form"):
            new_user = st.text_input("New Username")
            new_pass = st.text_input("New Password", type="password")
            confirm_pass = st.text_input("Confirm Password", type="password", key="confirm_pass")
            submitted_signup = st.form_submit_button("Create Account", type="primary")

            if submitted_signup:
                if not new_user or not new_pass or not confirm_pass:
                    st.error("All fields are required.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match.")
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

    # Set default page to dashboard and handle routing
    page = st.session_state.get("current_page", "dashboard")

    if page == "dashboard":
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
        # Default to dashboard if current_page is somehow invalid
        st.session_state.current_page = "dashboard"
        import pages.dashboard as p
        p.main()
