# pages/admin.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

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
        use_container_width=True,  # Fix deprecation
        hide_index=True
    )

    if st.button("Save Role Changes", type="primary", use_container_width=True):  # Fix deprecation
        try:
            with engine.connect() as conn:
                # Start a transaction
                with conn.begin():
                    for idx, row in edited_df.iterrows():
                        original_row = users_df.iloc[idx]
                        # Basic validation
                        if len(str(row["username"])) > 50 or row["username"].strip() == "":
                            st.error(f"Invalid username for row {idx}")
                            return
                        if row["role"] != original_row["role"] or row["username"] != original_row["username"]:
                            conn.execute(
                                text("UPDATE users SET role = :role, username = :username WHERE id = :id"),
                                {"role": row["role"], "username": row["username"], "id": row["id"]}
                            )
                st.success("Changes saved!")
                st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    # ——— DATABASE RESET ———
    st.subheader("Danger Zone")
    with st.expander("Reset Database (Irreversible)", expanded=False):
        st.warning("This will delete **all** workouts, goals, and reset schema.")
        password = st.text_input("Enter admin password to confirm", type="password")
        if st.button("NUKE DATABASE", type="secondary", use_container_width=True):  # Fix deprecation
            if password == st.secrets.get("ADMIN_NUKE_PASS", "default_nuke_pass"):
                try:
                    with engine.connect() as conn:
                        with conn.begin():  # Use a transaction
                            conn.execute(text("DROP TABLE IF EXISTS workout_exercises, workouts, goals, users CASCADE"))
                            conn.execute(text("""
                                CREATE TABLE users (
                                    id SERIAL PRIMARY KEY,
                                    username TEXT UNIQUE NOT NULL,
                                    password TEXT NOT NULL,
                                    role TEXT DEFAULT 'user',
                                    created_at TIMESTAMP DEFAULT NOW()
                                );
                                CREATE TABLE goals (
                                    id SERIAL PRIMARY KEY,
                                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                                    exercise TEXT NOT NULL,
                                    metric_type TEXT NOT NULL CHECK (metric_type IN ('time_min', 'reps', 'weight_lbs', 'distance_mi')),
                                    target_value NUMERIC NOT NULL,
                                    target_date DATE NOT NULL,
                                    created_at TIMESTAMP DEFAULT NOW()
                                );
                                CREATE TABLE workouts (
                                    id SERIAL PRIMARY KEY,
                                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                                    workout_date DATE NOT NULL,
                                    notes TEXT NOT NULL,
                                    duration_min INTEGER,
                                    created_at TIMESTAMP DEFAULT NOW()
                                );
                                CREATE TABLE workout_exercises (
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
                                -- Re-create admin user
                                INSERT INTO users (username, password, role) VALUES ('ianconner', 'admin123', 'admin');
                            """))
                    st.success("Database nuked and reset. App will restart.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
            else:
                st.error("Incorrect password.")

    # ——— SYSTEM STATS ———
    st.subheader("System Stats")
    col1, col2, col3 = st.columns(3)
    try:
        with col1:
            total_users = pd.read_sql("SELECT COUNT(*) FROM users", engine).iloc[0,0]
            st.metric("Total Users", total_users, delta=None, delta_color="normal")
        with col2:
            total_workouts = pd.read_sql("SELECT COUNT(*) FROM workouts", engine).iloc[0,0]
            st.metric("Total Workouts", total_workouts, delta=None, delta_color="normal")
        with col3:
            total_goals = pd.read_sql("SELECT COUNT(*) FROM goals", engine).iloc[0,0]
            st.metric("Total Goals", total_goals, delta=None, delta_color="normal")
    except Exception as e:
        st.error(f"Could not load stats: {e}")

    # ——— RAW DATA VIEW ———
    with st.expander("View Raw Tables", expanded=False):
        tab1, tab2, tab3, tab4 = st.tabs(["Users", "Workouts", "Exercises", "Goals"])
        try:
            with tab1:
                st.dataframe(pd.read_sql("SELECT * FROM users ORDER BY id", engine), use_container_width=True)  # Fix deprecation
            with tab2:
                st.dataframe(pd.read_sql("SELECT * FROM workouts ORDER BY workout_date DESC", engine), use_container_width=True)  # Fix deprecation
            with tab3:
                st.dataframe(pd.read_sql("SELECT * FROM workout_exercises ORDER BY id DESC", engine), use_container_width=True)  # Fix deprecation
            with tab4:
                st.dataframe(pd.read_sql("SELECT * FROM goals ORDER BY target_date", engine), use_container_width=True)  # Fix deprecation
        except Exception as e:
            st.error(f"Could not load tables: {e}")
