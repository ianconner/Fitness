# .strealit/pages/05_Admin.py
import streamlit as st
import psycopg2
import pandas as pd

# ——— DATABASE CONNECTION ———
def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— CHECK ADMIN ———
if st.session_state.role != 'admin':
    st.error("Access denied.")
    st.stop()

st.markdown("## Admin Panel")
st.markdown("Manage users, reset passwords, and modify data.")

# ——— USER LIST ———
conn = get_conn()
users = pd.read_sql("SELECT id, username, role FROM users", conn)
conn.close()

selected_user = st.selectbox("Select User", users["username"])
user_row = users[users["username"] == selected_user].iloc[0]

# ——— USER ACTIONS ———
col1, col2 = st.columns(2)
with col1:
    if st.button("Reset Password", use_container_width=True):
        new_pass = st.text_input("New Password", type="password", key="reset_pass")
        if st.button("Confirm Reset"):
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE users SET password=%s WHERE id=%s", (new_pass, user_row["id"]))
            conn.commit()
            conn.close()
            st.success(f"Password reset for **{selected_user}**")
            st.rerun()

with col2:
    new_role = st.selectbox("Change Role", ["user", "admin"], index=0 if user_row["role"] == "user" else 1)
    if st.button("Update Role", use_container_width=True):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE users SET role=%s WHERE id=%s", (new_role, user_row["id"]))
        conn.commit()
        conn.close()
        st.success(f"Role updated to **{new_role}**")
        st.rerun()

# ——— DELETE USER ———
if st.button("Delete User (Irreversible)", type="secondary", use_container_width=True):
    if st.checkbox("I understand this deletes all data"):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id=%s", (user_row["id"],))
        conn.commit()
        conn.close()
        st.success(f"User **{selected_user}** deleted.")
        st.rerun()

# ——— RAW DB VIEW ———
st.markdown("### Raw Database")
tab1, tab2, tab3 = st.tabs(["Users", "Workouts", "Goals"])
with tab1:
    df_users = pd.read_sql("SELECT * FROM users", get_conn())
    st.dataframe(df_users)
with tab2:
    df_workouts = pd.read_sql("SELECT * FROM workouts", get_conn())
    st.dataframe(df_workouts)
with tab3:
    df_goals = pd.read_sql("SELECT * FROM goals", get_conn())
    st.dataframe(df_goals)
