# app.py
import streamlit as st
import psycopg2
import hashlib
import os
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="RISE Fitness", page_icon="muscle", layout="centered")

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
    st.markdown("# Welcome to **RISE**")

    # ── RISE Explanation (Styled) ───────────────────────────────────────
    st.markdown("""
    <div style="background:#f0f2f6;padding:16px;border-radius:12px;margin:20px 0;">
        <p style="margin:0;font-size:1.1em;line-height:1.6;">
            <strong>RISE</strong> stands for:<br>
            <strong>R</strong>esilience • <strong>I</strong>ntensity • <strong>S</strong>trength • <strong>E</strong>ndurance
        </p>
        <p style="margin:8px 0 0;font-size:0.95em;color:#555;">
            Your personal AI-powered fitness coach — built to help you track, improve, and exceed your goals.
        </p>
    </div>
    """, unsafe_allow_html=True)

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

    # ── Sign Up Link ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("Don't have an account? [Sign up here](#)")  # Replace with actual link later

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        show_login()
    else:
        # Sidebar navigation after login
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
