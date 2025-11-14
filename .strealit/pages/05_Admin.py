# pages/05_Admin.py
import streamlit as st
import psycopg2
import pandas as pd

# ——— DATABASE ———
def conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— ADMIN CHECK ———
if st.session_state.role != 'admin':
    st.error("Access Denied. Admin only.")
    st.stop()

# ——— PAGE ———
st.set_page_config(page_title="Admin - SOPHIA", layout="wide")
st.title("SOPHIA Admin Panel")

# ——— USER OVERVIEW ———
c = conn()
users_df = pd.read_sql("""
    SELECT 
        id, 
        username, 
        created_at::date as joined,
        role
    FROM users 
    ORDER BY created_at DESC
""", c)

workouts_per_user = pd.read_sql("""
    SELECT 
        u.username,
        COUNT(w.id) as total_workouts,
        SUM(w.duration_min) as total_minutes
    FROM users u
    LEFT JOIN workouts w ON u.id = w.user_id
    GROUP BY u.id, u.username
    ORDER BY total_workouts DESC
""", c)

goals_per_user = pd.read_sql("""
    SELECT 
        u.username,
        COUNT(g.id) as active_goals
    FROM users u
    LEFT JOIN goals g ON u.id = g.user_id
    GROUP BY u.id, u.username
""", c)
c.close()

# Merge stats
stats = users_df.merge(workouts_per_user, on='username', how='left') \
                .merge(goals_per_user, on='username', how='left') \
                .fillna({'total_workouts': 0, 'total_minutes': 0, 'active_goals': 0})

st.subheader("User Activity Dashboard")
st.dataframe(stats, use_container_width=True)

# ——— SYSTEM STATS ———
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Users", len(stats))
with col2:
    st.metric("Active Users", len(stats[stats['total_workouts'] > 0]))
with col3:
    st.metric("Total Workouts", int(stats['total_workouts'].sum()))
with col4:
    st.metric("Total Goals", int(stats['active_goals'].sum()))

# ——— RECENT ACTIVITY LOG ———
st.subheader("Latest Workouts (All Users)")
c = conn()
recent = pd.read_sql("""
    SELECT 
        u.username,
        w.workout_date,
        w.notes
    FROM workouts w
    JOIN users u ON w.user_id = u.id
    ORDER BY w.workout_date DESC, w.created_at DESC
    LIMIT 20
""", c)
c.close()

if not recent.empty:
    for _, row in recent.iterrows():
        st.caption(f"**{row['username']}** — {row['workout_date']}")
        st.code(row['notes'], language=None)
else:
    st.info("No workouts logged yet.")

# ——— MAKE ADMIN (MANUAL) ———
st.sidebar.markdown("### Admin Tools")
with st.sidebar.form("make_admin"):
    st.write("Promote User to Admin")
    target_user = st.text_input("Username")
    promote = st.form_submit_button("Make Admin")
    if promote:
        if target_user:
            c = conn()
            cur = c.cursor()
            cur.execute("UPDATE users SET role = 'admin' WHERE LOWER(username) = LOWER(%s)", (target_user,))
            if cur.rowcount > 0:
                c.commit()
                st.success(f"**{target_user}** is now admin.")
            else:
                st.error("User not found.")
            c.close()
        else:
            st.error("Enter a username.")
