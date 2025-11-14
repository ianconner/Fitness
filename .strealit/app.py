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
        box-shadow: 0 4px 8px rgba(0,255,
