import psycopg2
import streamlit as st

conn = psycopg2.connect(st.secrets["POSTGRES_URL"])
c = conn.cursor()
c.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS felt_rating INTEGER DEFAULT 3;")
c.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS distance REAL DEFAULT 2.0;")
conn.commit()
conn.close()
st.success("Migration complete! Ready for distance + felt rating.")
