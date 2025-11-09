import psycopg2
import streamlit as st

# Connect using POSTGRES_URL from secrets
conn = psycopg2.connect(st.secrets["POSTGRES_URL"])
c = conn.cursor()

# Add missing columns (safe: won't fail if they exist)
c.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS distance REAL DEFAULT 2.0;")
c.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS felt_rating INTEGER DEFAULT 3;")
c.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS run_minutes REAL;")
c.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS run_seconds REAL;")

conn.commit()
conn.close()

st.success("Migration complete! 'distance' and 'felt_rating' added.")
st.balloons()
