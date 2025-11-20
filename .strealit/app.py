# .streamlit/app.py
import streamlit as st
import psycopg2
from sqlalchemy import create_engine

# ─── DATABASE ENGINE ───
engine = create_engine(st.secrets["POSTGRES_URL"])
def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ─── INITIALIZE DATABASE ───
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    try:
        schema_sql = """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='role') THEN
                ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='theme_preference') THEN
                ALTER TABLE users ADD COLUMN theme_preference TEXT DEFAULT 'dark';
            END IF;
        END $$;

        UPDATE users SET role = 'user' WHERE role IS NULL;
        UPDATE users SET theme_preference = 'dark' WHERE theme_preference IS NULL;

        CREATE TABLE IF NOT EXISTS goals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            exercise TEXT NOT NULL,
            metric_type TEXT NOT NULL CHECK (metric_type IN ('time_min','reps','weight_lbs','distance_mi','sets')),
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
            distance_mi NUMERIC,
            notes TEXT,
            goal_id INTEGER REFERENCES goals(id) ON DELETE SET NULL
        );

        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='workout_exercises' AND column_name='goal_id') THEN
                ALTER TABLE workout_exercises ADD COLUMN goal_id INTEGER REFERENCES goals(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
        cur.execute(schema_sql)

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

# ─── THEME MANAGEMENT ───
def get_user_theme():
    """Fetch user's theme preference from database"""
    if 'user_id' not in st.session_state:
        return 'dark'
    
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT theme_preference FROM users WHERE id = %s", (st.session_state.user_id,))
        result = cur.fetchone()
        return result[0] if result and result[0] else 'dark'
    except:
        return 'dark'
    finally:
        cur.close()
        conn.close()

def update_user_theme(theme):
    """Update user's theme preference in database"""
    if 'user_id' not in st.session_state:
        return
    
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET theme_preference = %s WHERE id = %s", (theme, st.session_state.user_id))
        conn.commit()
        st.session_state.theme = theme
    except Exception as e:
        st.error(f"Failed to save theme: {e}")
    finally:
        cur.close()
        conn.close()

def apply_theme_styles():
    """Apply custom CSS based on theme preference"""
    theme = st.session_state.get('theme', 'dark')
    
    if theme == 'dark':
        bg_color = '#0E1117'
        secondary_bg = '#1E2130'
        text_color = '#FAFAFA'
        border_color = '#2D3139'
        hover_bg = '#262B3A'
    else:
        bg_color = '#FFFFFF'
        secondary_bg = '#F0F2F6'
        text_color = '#262730'
        border_color = '#E0E3E8'
        hover_bg = '#E8EBF0'
    
    st.markdown(f"""
    <style>
        /* Hide default Streamlit nav */
        [data-testid="stSidebarNav"] {{ display: none !important; }}
        
        /* Orange accent color throughout */
        .stButton > button[kind="primary"] {{
            background-color: #FF6B35 !important;
            color: white !important;
            border: none !important;
            font-weight: 600 !important;
            min-height: 44px !important;
        }}
        
        .stButton > button[kind="primary"]:hover {{
            background-color: #E55A2B !important;
        }}
        
        /* Progress bars */
        .stProgress > div > div > div {{
            background-color: #FF6B35 !important;
        }}
        
        /* Mobile optimization */
        @media (max-width: 768px) {{
            .stButton > button {{
                min-height: 44px !important;
                font-size: 16px !important;
                padding: 12px 20px !important;
            }}
            
            .stTextInput > div > div > input,
            .stNumberInput > div > div > input,
            .stSelectbox > div > div > div,
            .stDateInput > div > div > input {{
                min-height: 44px !important;
                font-size: 16px !important;
            }}
            
            /* Larger touch targets for forms */
            .stCheckbox > label {{
                min-height: 44px !important;
                display: flex !important;
                align-items: center !important;
            }}
        }}
        
        /* Container styling */
        [data-testid="stContainer"] {{
            background-color: {secondary_bg};
            border: 1px solid {border_color};
            border-radius: 8px;
            padding: 16px;
        }}
        
        /* Metric styling with orange accents */
        [data-testid="stMetricValue"] {{
            color: #FF6B35 !important;
            font-weight: 700 !important;
        }}
        
        /* Navigation buttons with orange highlight for active */
        .stButton > button[data-testid*="nav_"] {{
            width: 100% !important;
            text-align: left !important;
            background-color: transparent !important;
            border: 1px solid {border_color} !important;
            color: {text_color} !important;
            min-height: 44px !important;
        }}
        
        .stButton > button[data-testid*="nav_"]:hover {{
            background-color: {hover_bg} !important;
            border-color: #FF6B35 !important;
        }}
        
        /* Theme toggle styling */
        .theme-toggle {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px;
            background-color: {secondary_bg};
            border: 1px solid {border_color};
            border-radius: 8px;
            margin-bottom: 16px;
        }}
        
        /* Responsive table styling */
        @media (max-width: 768px) {{
            [data-testid="stDataFrame"] {{
                font-size: 14px !important;
            }}
            
            .stMarkdown h1 {{
                font-size: 24px !important;
            }}
            
            .stMarkdown h2 {{
                font-size: 20px !important;
            }}
            
            .stMarkdown h3 {{
                font-size: 18px !important;
            }}
        }}
        
        /* Form submit buttons */
        .stFormSubmitButton > button {{
            background-color: #FF6B35 !important;
            color: white !important;
            min-height: 44px !important;
            font-weight: 600 !important;
        }}
        
        .stFormSubmitButton > button:hover {{
            background-color: #E55A2B !important;
        }}
    </style>
    """, unsafe_allow_html=True)

# ─── AUTHENTICATION LOGIC ───
def check_password(username, password):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, role, password, theme_preference FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        
        if user and user[3] == password:
            st.session_state.user_id = user[0]
            st.session_state.username = user[1]
            st.session_state.role = user[2]
            st.session_state.theme = user[4] if user[4] else 'dark'
            return True
    finally:
        conn.close()
    return False

def logout():
    st.session_state.clear()
    st.rerun()

def render_sidebar():
    with st.sidebar:
        st.markdown(f"## Welcome, **{st.session_state.username}**")
        st.caption(f"Role: {st.session_state.role.upper()}")
        
        # Theme Toggle
        st.markdown("---")
        current_theme = st.session_state.get('theme', 'dark')
        theme_label = "🌙 Dark Mode" if current_theme == 'dark' else "☀️ Light Mode"
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{theme_label}**")
        with col2:
            if st.button("🔄", key="theme_toggle", help="Toggle theme"):
                new_theme = 'light' if current_theme == 'dark' else 'dark'
                update_user_theme(new_theme)
                st.rerun()
        
        st.markdown("---")

        # Navigation
        st.markdown("### Navigation")
        
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

# ─── MAIN APP FLOW ───
st.set_page_config(
    page_title="RISE Fitness Tracker",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize theme before anything else
if 'theme' not in st.session_state and 'user_id' in st.session_state:
    st.session_state.theme = get_user_theme()

# Apply theme styles
apply_theme_styles()

if 'user_id' not in st.session_state:
    st.title("Welcome to RISE (Resilience, Intensity, Strength, Endurance)")
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
                            "INSERT INTO users (username,password,role,theme_preference) VALUES (%s,%s,'user','dark') RETURNING id,username",
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
        st.session_state.current_page = "dashboard"
        import pages.dashboard as p
        p.main()
