# pages/02_AI_Coach.py
import streamlit as st
import pandas as pd
import psycopg2
import requests
from datetime import datetime, timedelta

# ---------- FIX: get_db_connection moved to top ----------
def get_db_connection():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="SOPHIA Coach", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebarNav"] {display: none !important;}
.block-container {padding-top: 4rem !important;}
</style>
""", unsafe_allow_html=True)

# ---------- AUTH ----------
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.error("Please log in from the home page.")
    st.stop()

# ---------- SIDEBAR ----------
st.sidebar.success(f"**{st.session_state.username}**")

# Preferred Name Setting
with st.sidebar.expander("⚙️ Settings"):
    current_name = st.session_state.get('preferred_name', st.session_state.username)
    new_preferred_name = st.text_input("What should SOPHIA call you?", value=current_name)
    if st.button("Save Name", key="save_pref_name"):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET preferred_name = %s WHERE id = %s",
                    (new_preferred_name, st.session_state.user_id))
        conn.commit()
        cur.close()
        conn.close()
        st.session_state.preferred_name = new_preferred_name
        st.success(f"SOPHIA will now call you {new_preferred_name}!")

st.sidebar.page_link("app.py", label="🏠 Home")
st.sidebar.page_link("pages/01_Dashboard.py", label="📊 Dashboard")
st.sidebar.page_link("pages/02_AI_Coach.py", label="🤖 SOPHIA Coach")

if st.sidebar.button("Logout", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.switch_page("app.py")

# ---------- DATA ----------
def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT * FROM logs WHERE user_id = %s ORDER BY date DESC",
        conn, params=(st.session_state.user_id,)
    )
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("Log a session first to get personalized coaching from SOPHIA.")
    st.stop()

# ---------- ANALYSIS ----------
df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds'] / 60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)
valid_df = df[df['distance'] > 0].copy()

GOAL_RUN_MIN = st.session_state.get("goal_run_min", 18.0)
GOAL_PUSH = st.session_state.get("goal_push", 45)
GOAL_CRUNCH = st.session_state.get("goal_crunch", 45)
GOAL_DATE = st.session_state.get("goal_date", datetime.now().date())

today = datetime.now().date()
days_to_goal = (GOAL_DATE - today).days

# ---------- HEADER ----------
st.markdown("### 🤖 SOPHIA – Smart Optimized Performance Health Intelligence Assistant")

preferred_name = st.session_state.get('preferred_name', st.session_state.username)
st.markdown(f"**Coaching {preferred_name}** | Goal Date: **{GOAL_DATE.strftime('%B %d, %Y')}** ({days_to_goal} days remaining)")

# ---------- PERFORMANCE SUMMARY ----------
col1, col2, col3 = st.columns(3)
with col1:
    last_date = df['date'].max()
    st.metric("Last Session", last_date.strftime("%b %d, %Y"))
with col2:
    avg_pace = valid_df['pace_min_per_mi'].mean()
    pace_str = f"{int(avg_pace):02d}:{int((avg_pace % 1) * 60):02d}" if pd.notna(avg_pace) else "N/A"
    st.metric("Average Pace", pace_str)
with col3:
    total_miles = valid_df['distance'].sum()
    st.metric("Total Miles Logged", f"{total_miles:.1f}")

st.markdown("---")

# ---------- INSIGHT GENERATION ----------
st.subheader("📈 Performance Summary")

# Calculate trend stats
recent_df = valid_df.head(5).copy()
if not recent_df.empty:
    avg_pace_recent = recent_df['pace_min_per_mi'].mean()
    avg_push_recent = df['pushups'].head(5).mean()
    avg_crunch_recent = df['crunches'].head(5).mean()
else:
    avg_pace_recent, avg_push_recent, avg_crunch_recent = pd.NA, pd.NA, pd.NA

trend_summary = f"""
- **Average pace (last 5 runs):** {avg_pace_recent:.2f} min/mi  
- **Average push-ups:** {avg_push_recent:.0f}  
- **Average crunches:** {avg_crunch_recent:.0f}  
- **Days until goal:** {days_to_goal}  
"""

st.markdown(trend_summary)

# ---------- AI ANALYSIS ----------
st.markdown("### 🧠 SOPHIA's Personalized Feedback")

# Load GROQ API key
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    st.error("Missing GROQ_API_KEY in Streamlit secrets. Please add it to .streamlit/secrets.toml.")
    st.stop()

# LLM parameters
MODEL = "llama-3.1-8b-instant"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Data summary for LLM context
summary_context = f"""
Athlete Name: {preferred_name}
Total Logs: {len(df)}
Recent Average Pace: {avg_pace_recent:.2f} min/mi
Goal: 2-mile in {GOAL_RUN_MIN:.1f} min by {GOAL_DATE}
Push-ups Goal: {GOAL_PUSH}
Crunches Goal: {GOAL_CRUNCH}
Days Remaining: {days_to_goal}

Recent Performance (Last 5):
{recent_df[['date', 'distance', 'run_minutes', 'run_seconds', 'pushups', 'crunches', 'felt_rating']].to_string(index=False)}
"""

# ---------- SOPHIA’s COACHING PROMPT ----------
system_prompt = """
You are SOPHIA, an AI fitness coach trained for Air Force fitness readiness.
Your job is to:
1. Analyze the athlete’s recent run, push-up, and crunch data.
2. Identify physical strengths and weaknesses.
3. Offer specific, tactical recommendations for the next 7 days.
4. Provide encouragement using a professional tone with Air Force-style precision.
Keep responses concise but insightful.
"""

# Display prompt for debug
with st.expander("🪶 Raw AI Input Context"):
    st.code(summary_context)

# ---------- AI RESPONSE ----------
if st.button("🎯 Generate Full SOPHIA Coaching Plan", use_container_width=True):
    with st.spinner("Analyzing performance and generating your tailored plan..."):
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": summary_context}
            ],
            "temperature": 0.7,
            "max_tokens": 900,
        }

        try:
            response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            ai_reply = data["choices"][0]["message"]["content"]

            st.success("✅ SOPHIA’s 7-Day Plan Generated:")
            st.markdown(ai_reply)

        except Exception as e:
            st.error(f"Failed to get AI response: {e}")

st.markdown("---")

# ---------- CUSTOM Q&A WITH SOPHIA ----------
st.subheader("💬 Ask SOPHIA a Custom Question")
user_query = st.text_area("Type your question or request (e.g., 'How can I improve my run time in 2 weeks?')", height=100)

if st.button("Ask SOPHIA", use_container_width=True):
    if not user_query.strip():
        st.warning("Please enter a question first.")
        st.stop()
    with st.spinner("SOPHIA is preparing your answer..."):
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "You are SOPHIA, a U.S. Air Force fitness AI coach."},
                    {"role": "user", "content": f"Context:\n{summary_context}\n\nQuestion:\n{user_query}"}
                ],
                "temperature": 0.8,
                "max_tokens": 800,
            }

            response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            ai_data = response.json()
            answer = ai_data["choices"][0]["message"]["content"]

            st.markdown("### 🧭 SOPHIA’s Response:")
            st.markdown(answer)

        except Exception as e:
            st.error(f"Error getting SOPHIA’s response: {e}")

# ---------- FOOTER ----------
st.markdown("---")
st.caption("SOPHIA AI Fitness Coach • Built for operational readiness and data-informed performance improvement.")
