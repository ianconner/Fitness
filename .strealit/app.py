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
for key in ['logged_in', 'user_id', 'username', 'role', 'just_logged_in', 'current_page']:
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

# ——— GORGEOUS SIDEBAR WITH NUCLEAR AUTO-NAV KILLER ———
def render_sidebar():
    # === INJECT CSS + JS TO KILL STREAMLIT'S AUTO-NAV ===
    st.markdown("""
    <style>
    /* HIDE DEFAULT SIDEBAR NAVIGATION */
    section[data-testid="stSidebar"] > div:first-child > div:first-child > div:first-child,
    [data-testid="stSidebarNav"],
    a[href^="/?page="],
    [data-testid="stSidebar"] [kind="secondary"] {
        display: none !important;
    }
    /* STYLE OUR BUTTONS */
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

    # === JS: NUKE ANY RESIDUAL NAV (RUN AFTER RENDER) ===
    st.markdown("""
    <script>
    document.addEventListener("DOMContentLoaded", () => {
        setTimeout(() => {
            // Remove any auto-generated links
            document.querySelectorAll('a[href*="page="]').forEach(el => el.remove());
            document.querySelectorAll('[data-testid="stSidebarNav"]').forEach(el => el.remove());
            // Ensure only our content remains
            const sidebar = document.querySelector('[data-testid="stSidebar"]');
            if (sidebar) {
                const children = sidebar.children;
                for (let i = children.length - 1;
