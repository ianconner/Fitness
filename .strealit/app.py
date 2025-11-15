# app.py
import streamlit as st
import psycopg2
import hashlib

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="RISE Fitness", page_icon="flexed biceps", layout="centered")

# ─────────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────
def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# ─────────────────────────────────────────────────────────────────────────────
# LOGIN PAGE
# ─────────────────────────────────────────────────────────────────────────────
def show_login():
    # NEW TITLE
    st.markdown("# Welcome to **RISE**")
    st.markdown("### *(Resilience, Intensity, Strength, Endurance)*")

    st.markdown("### Log in to continue")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Log In")

        if submit:
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                try:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id, password_hash FROM users WHERE email = %s",
                        (email.lower(),)
                    )
                    result = cur.fetchone()
                    if result and result[1] == hash_password(password):
                        st.session_state.user_id = result[0]
                        st.session_state.logged_in = True
                        st.success("Logged in!")
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")
                    conn.close()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    st.markdown("---")
    st.markdown("Don't have an account? [Sign up here](#)")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        show_login()
    else:
        st.sidebar.success(f"Logged in as User #{st.session_state.user_id}")
        page = st.sidebar.radio("Go to", ["Dashboard", "Log Workout", "Goals", "Profile"])

        if page == "Dashboard":
            import pages.dashboard as p
            p.main()
        elif page == "Log Workout":
            import pages.log_workout as p
            p.main()
        elif page == "Goals":
            import pages.goals as p
            p.main()
        elif page == "Profile":
            st.write("Profile page coming soon...")

if __name__ == "__main__":
    main()
