# pages/02_AI_Coach.py
import streamlit as st
import pandas as pd
import psycopg2
import requests
from datetime import datetime, timedelta

# ——— PAGE CONFIG ———
st.set_page_config(
    page_title="SOPHIA Coach",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ——— HIDE STREAMLIT'S AUTO NAV ———
st.markdown("""
<style>
    /* Hide Streamlit's default page navigation menu */
    [data-testid="stSidebarNav"] {display: none !important;}
    
    /* Reduce top padding */
    .block-container {padding-top: 4rem !important;}
</style>
""", unsafe_allow_html=True)

# ——— CHECK LOGIN ———
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.error("Please log in from the home page.")
    st.stop()

# ——— SIDEBAR NAVIGATION ———
st.sidebar.success(f"**{st.session_state.username}**")

# Preferred Name Setting
with st.sidebar.expander("⚙️ Settings"):
    current_name = st.session_state.get('preferred_name', st.session_state.username)
    new_preferred_name = st.text_input("What should SOPHIA call you?", value=current_name, key="pref_name_input")
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

# ---------- DB ----------
def get_db_connection():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

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

df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)
valid_df = df[df['distance'] > 0].copy()

# ---------- GOALS ----------
GOAL_RUN_MIN = st.session_state.get("goal_run_min", 18.0)
GOAL_PUSH    = st.session_state.get("goal_push",    45)
GOAL_CRUNCH  = st.session_state.get("goal_crunch", 45)
GOAL_DATE    = st.session_state.get("goal_date",    datetime.now().date())

# ---------- HORIZON ----------
today = datetime.now().date()
days_to_goal = (GOAL_DATE - today).days

if days_to_goal <= 30:
    urgency = "MAX";      intensity = 1.3; volume = 0.7; progression = "aggressive taper"
elif days_to_goal <= 90:
    urgency = "HIGH";     intensity = 1.2; volume = 0.8; progression = "linear peaking"
elif days_to_goal <= 180:
    urgency = "MEDIUM";   intensity = 1.0; volume = 1.0; progression = "periodized"
else:
    urgency = "LOW";      intensity = 0.9; volume = 1.1; progression = "base building"

# ---------- PROJECTIONS ----------
last_5 = valid_df.head(5)
last_10 = valid_df.head(10)
avg_pace = last_5['pace_min_per_mi'].mean()
proj_2mi = avg_pace * 2
proj_str = f"{int(proj_2mi):02d}:{int((proj_2mi % 1)*60):02d}"

# Calculate trends
pace_trend = valid_df['pace_min_per_mi'].diff().mean() if len(valid_df) > 1 else 0
push_trend = df['pushups'].diff().mean() if len(df) > 1 else 0
crunch_trend = df['crunches'].diff().mean() if len(df) > 1 else 0

# Get last workout date
last_workout = df['date'].iloc[0].date()
days_since_workout = (today - last_workout).days

# ---------- GROQ ----------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    st.error("Missing GROQ_API_KEY")
    st.stop()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

# ---------- PAGE HEADER ----------
st.markdown("### 🤖 SOPHIA – Smart Optimized Performance Health Intelligence Assistant")
preferred_name = st.session_state.get('preferred_name', st.session_state.username)
st.markdown(f"**Coaching {preferred_name}** | Goal Date: **{GOAL_DATE.strftime('%B %d, %Y')}** ({days_to_goal} days)")

# ---------- USER INPUT: NEXT WORKOUT ----------
st.markdown("---")
col1, col2 = st.columns([2, 1])
with col1:
    next_workout_date = st.date_input(
        "When is your next planned workout?",
        value=today + timedelta(days=1),
        min_value=today
    )
with col2:
    days_until_workout = (next_workout_date - today).days
    st.metric("Days Until Workout", days_until_workout)

# ---------- GENERATE ANALYSIS ----------
if st.button("🎯 Get SOPHIA's Complete Analysis & Workout Plan", use_container_width=True):
    with st.spinner("SOPHIA is analyzing your data and creating your personalized plan..."):
        
        # Build comprehensive data context
        preferred_name = st.session_state.get('preferred_name', st.session_state.username)
        data_summary = f"""
=== ATHLETE PROFILE ===
Name: {preferred_name}
Age: 39 years old, Male
Goal Date: {GOAL_DATE.strftime('%B %d, %Y')} ({days_to_goal} days remaining)
Training Urgency: {urgency}

=== PERFORMANCE GOALS ===
• 2-Mile Run: ≤ {GOAL_RUN_MIN}:00 minutes
• Push-ups: {GOAL_PUSH} reps
• Crunches: {GOAL_CRUNCH} reps

=== CURRENT PERFORMANCE (Last 5 Sessions) ===
• Average Pace: {avg_pace:.2f} min/mi
• Projected 2-Mile Time: {proj_str}
• Gap to Goal: {(proj_2mi - GOAL_RUN_MIN):.2f} minutes {"BELOW goal! ✓" if proj_2mi <= GOAL_RUN_MIN else "ABOVE goal"}
• Latest Push-ups: {df['pushups'].iloc[0]} (Goal: {GOAL_PUSH}, Gap: {df['pushups'].iloc[0] - GOAL_PUSH:+d})
• Latest Crunches: {df['crunches'].iloc[0]} (Goal: {GOAL_CRUNCH}, Gap: {df['crunches'].iloc[0] - GOAL_CRUNCH:+d})
• Average Felt Rating: {last_5['felt_rating'].mean():.1f}/5

=== TRAINING TRENDS (Session-to-Session Changes) ===
• Pace Trend: {pace_trend:+.3f} min/mi per session {"(IMPROVING ✓)" if pace_trend < 0 else "(DECLINING)" if pace_trend > 0 else "(STABLE)"}
• Push-ups Trend: {push_trend:+.1f} reps/session {"(IMPROVING ✓)" if push_trend > 0 else "(DECLINING)" if push_trend < 0 else "(STABLE)"}
• Crunches Trend: {crunch_trend:+.1f} reps/session {"(IMPROVING ✓)" if crunch_trend > 0 else "(DECLINING)" if crunch_trend < 0 else "(STABLE)"}

=== TRAINING FREQUENCY ===
• Total Sessions Logged: {len(df)}
• Last Workout: {last_workout.strftime('%B %d, %Y')} ({days_since_workout} days ago)
• Next Planned Workout: {next_workout_date.strftime('%B %d, %Y')} ({days_until_workout} days from now)
• Rest Period: {days_until_workout} days

=== DETAILED SESSION HISTORY (Last 10) ===
"""
        for idx, row in df.head(10).iterrows():
            pace = row['pace_min_per_mi'] if pd.notna(row['pace_min_per_mi']) else 0
            pace_str = f"{int(pace):02d}:{int((pace % 1)*60):02d}" if pace > 0 else "N/A"
            data_summary += f"\n{row['date'].strftime('%m/%d')} | {row['distance']:.1f}mi @ {pace_str}/mi | {row['pushups']}pu | {row['crunches']}cr | Felt: {row['felt_rating']}/5"

        # Enhanced prompt for comprehensive analysis
        prompt = f"""You are SOPHIA (Smart Optimized Performance Health Intelligence Assistant), speaking directly to your athlete.

{data_summary}

Speak directly to {preferred_name} in first and second person (I/you), as if you're having a conversation. Be warm but professional. Structure your response with these sections:

1. **PERFORMANCE ANALYSIS**
   Talk directly about where you currently stand vs each goal. Use phrases like "You're currently at..." and "I see you've been..."
   - Assess your pace trend, push-ups, and crunches
   - Point out your strengths and what needs work
   - Comment on your felt ratings and how you're recovering

2. **REST & RECOVERY ASSESSMENT**
   - Discuss the {days_until_workout}-day gap before your next workout
   - Tell you directly if I think this is too much rest, just right, or too little
   - Given it's been {days_since_workout} days since your last workout, share what adjustments you should make
   - Give you specific recommendations about training frequency

3. **HERE'S HOW WE'LL CLOSE THE GAPS**
   Give 5-7 specific steps you need to take, speaking directly:
   - "For your running, I want you to..."
   - "To hit your push-up goal, start by..."
   - "Your core work needs..."
   - Include recovery and nutrition advice
   - Mental preparation tips

4. **YOUR WORKOUT PLAN** (for {next_workout_date.strftime('%A, %B %d')})
   Write this like I'm coaching you through it:
   
   **Warm-up (10 min)**
   - "Start with..." (exact movements, duration)
   
   **Main Set (30-35 min)**
   - "Here's what you're running today..."
   - "For push-ups, I want you to..."
   - "Crunches will be..."
   - Include RPE targets: "This should feel like a 7/10"
   
   **Cool-down (5-10 min)**
   - "Finish with..."
   
   **Total Duration**: ~50 minutes

5. **REAL TALK & MOTIVATION**
   - 2-3 sentences speaking directly about where you are and what's possible
   - Reference exercise science naturally: "Your VO2max will adapt if we..."
   - Be honest but encouraging

Tone: Like a knowledgeable coach talking to their athlete. Use "I" when referring to yourself as SOPHIA, "you/your" when referring to {preferred_name}. Be direct, honest, data-driven, but supportive. No third person references.
"""

        try:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}",
                       "Content-Type": "application/json"}
            payload = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.6,
                "max_tokens": 2000
            }
            r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=45)
            r.raise_for_status()
            plan = r.json()['choices'][0]['message']['content']

            # Display the complete analysis
            st.markdown("---")
            st.markdown(plan)
            
        except Exception as e:
            st.error(f"Error generating analysis: {e}")

# ---------- Q&A ----------
st.markdown("---")
st.markdown("### 💬 Ask SOPHIA Anything")
st.markdown("*Questions about goals, training science, adjustments, nutrition, recovery, etc.*")

q = st.text_input("Your question:")
if st.button("💡 Get Answer", use_container_width=True) and q:
    with st.spinner("SOPHIA is thinking…"):
        preferred_name = st.session_state.get('preferred_name', st.session_state.username)
        q_prompt = f"""You are SOPHIA, speaking directly to {preferred_name}. Answer their question in a conversational way, like you're talking to them face-to-face.

Their Question: {q}

Context About Them:
- {preferred_name}, 39M
- Goal Date: {GOAL_DATE} ({days_to_goal} days away)
- Goals: 2-mile ≤ {GOAL_RUN_MIN}:00 | {GOAL_PUSH} push-ups | {GOAL_CRUNCH} crunches
- Current Performance: Projected 2-mile is {proj_str} | Last session: {df['pushups'].iloc[0]} push-ups, {df['crunches'].iloc[0]} crunches
- Trends: Pace {pace_trend:+.3f} min/mi, Push-ups {push_trend:+.1f}/session, Crunches {crunch_trend:+.1f}/session
- Training: Last workout was {days_since_workout} days ago, next planned in {days_until_workout} days

Respond in 4-6 sentences using "I" (as SOPHIA) and "you" (speaking to them). Reference exercise science naturally when relevant. Be direct, honest, and helpful - like a knowledgeable coach having a conversation."""

        try:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}",
                       "Content-Type": "application/json"}
            payload = {
                "model": MODEL,
                "messages": [{"role": "user", "content": q_prompt}],
                "temperature": 0.6,
                "max_tokens": 400
            }
            r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            reply = r.json()['choices'][0]['message']['content']
            
            st.markdown("#### SOPHIA's Response:")
            st.info(reply)
        except Exception as e:
            st.error(f"Error: {e}")
