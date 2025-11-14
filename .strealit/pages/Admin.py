# pages/admin.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

# ——— DATABASE ENGINE ———
engine = create_engine(st.secrets["POSTGRES_URL"])

def main():
    if st.session_state.role != 'admin':
        st.error("Access denied.")
        return

    st.markdown("## Admin Panel")
    st.markdown("System management and user oversight.")

    # ——— USER MANAGEMENT ———
    st.subheader("User Management")
    users_df = pd.read_sql("SELECT id, username, role FROM users ORDER BY username", engine)
    edited_df = st.data_editor(
        users_df,
        column_config={
            "role": st.column_config.SelectboxColumn(
                "Role",
                options=["user", "admin"],
                required=True
            )
        },
        use_container_width=True,
        hide_index=True
    )

    if st.button("Save Role Changes", type="primary"):
        try:
            with engine.connect() as conn:
                for idx, row in edited_df.iterrows():
                    if row["role"] != users_df.iloc[idx]["role"]:
                        conn.execute(
                            "UPDATE users SET role = %s WHERE id = %s",
                            (row["role"], row["id"])
                        )
                conn.commit()
            st.success("Roles updated!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    # ——— DATABASE RESET ———
    st.subheader("Danger Zone")
    with st.expander("Reset Database (Irreversible)", expanded=False):
        st.warning("This will delete **all** workouts, goals, and reset schema.")
        password = st.text_input("Enter admin password to confirm", type="password")
        if st.button("NUKE DATABASE", type="secondary"):
            if password == st.secrets.get("ADMIN_NUKE_PASS", "default_nuke_pass"):
                try:
                    with engine.connect() as conn:
                        conn.execute("DROP TABLE IF EXISTS workout_exercises, workouts, goals, users CASCADE")
                        conn.execute("""
                            CREATE TABLE users (
                                id SERIAL PRIMARY KEY,
                                username TEXT UNIQUE NOT NULL,
                                password TEXT NOT NULL,
                                role TEXT DEFAULT 'user'
                            );
                            INSERT INTO users (username, password, role) VALUES ('ianconner', 'admin123', 'admin');
                        """)
                        conn.commit()
                    st.success("Database nuked and reset. App will restart.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
            else:
                st.error("Incorrect password.")

    # ——— SYSTEM STATS ———
    st.subheader("System Stats")
    col1, col2, col3 = st.columns(3)
    with col1:
        total_users = pd.read_sql("SELECT COUNT(*) FROM users", engine).iloc[0,0]
        st.metric("Total Users", total_users)
    with col2:
        total_workouts = pd.read_sql("SELECT COUNT(*) FROM workouts", engine).iloc[0,0]
        st.metric("Total Workouts", total_workouts)
    with col3:
        total_goals = pd.read_sql("SELECT COUNT(*) FROM goals", engine).iloc[0,0]
        st.metric("Total Goals", total_goals)

    # ——— RAW DATA VIEW ———
    with st.expander("View Raw Tables"):
        tab1, tab2, tab3, tab4 = st.tabs(["Users", "Workouts", "Exercises", "Goals"])
        with tab1:
            st.dataframe(pd.read_sql("SELECT * FROM users", engine), use_container_width=True)
        with tab2:
            st.dataframe(pd.read_sql("SELECT * FROM workouts", engine), use_container_width=True)
        with tab3:
            st.dataframe(pd.read_sql("SELECT * FROM workout_exercises", engine), use_container_width=True)
        with tab4:
            st.dataframe(pd.read_sql("SELECT * FROM goals", engine), use_container_width=True)
