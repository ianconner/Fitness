# pages/ai_coach.py
import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine

# Initialize the SQLAlchemy engine for robust data access
engine = create_engine(st.secrets["POSTGRES_URL"])

# Define the RISE avatar URL globally
RISE_AVATAR_URL = "https://api.dicebear.com/7.x/bottts/svg?seed=RISE"

def get_user_data():
    """Fetches the user's latest 20 workouts and active goals."""
    try:
        # Fetch latest 20 workouts
        workouts = pd.read_sql("""
            SELECT w.workout_date, w.duration_min, w.notes,
                   we.exercise, we.sets, we.reps, we.weight_lbs, we.time_min, we.distance_mi
            FROM workouts w
            LEFT JOIN workout_exercises we ON w.id = we.workout_id
            WHERE w.user_id = %s
            ORDER BY w.workout_date DESC
            LIMIT 20
        """, engine, params=(st.session_state.user_id,))

        # Fetch active goals
        goals = pd.read_sql("""
            SELECT exercise, metric_type, target_value, target_date
            FROM goals
            WHERE user_id = %s AND target_date >= CURRENT_DATE
        """, engine, params=(st.session_state.user_id,))

        return workouts, goals
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame(), pd.DataFrame()

def generate_data_context(workouts, goals):
    """Creates the data summary for the AI to analyze."""
    if workouts.empty and goals.empty:
        return "No training data or active goals have been logged yet."

    insight = "CURRENT ATHLETE DATA (Use this for context. Do NOT output this raw text):\n"

    if not workouts.empty:
        # Robust data processing for insights
        workouts['workout_date'] = pd.to_datetime(workouts['workout_date']).dt.date
        numeric_cols = ['duration_min', 'sets', 'reps', 'weight_lbs', 'time_min', 'distance_mi']
        for col in numeric_cols:
            workouts[col] = pd.to_numeric(workouts[col], errors='coerce')

        total_sessions = len(workouts['workout_date'].unique())
        last_workout_date = workouts['workout_date'].max()
        days_since_workout = (datetime.now().date() - last_workout_date).days if not pd.isna(last_workout_date) else 999

        insight += f"• TOTAL SESSIONS: {total_sessions} logged. Days Since Last Session: {days_since_workout}.\n"

        # Add details on recent workouts
        recent_run = workouts[workouts['exercise'].astype(str).str.contains('Run|Treadmill', case=False, na=False)].head(1)
        if not recent_run.empty and not pd.isna(recent_run['distance_mi'].iloc[0]) and not pd.isna(recent_run['time_min'].iloc[0]) and recent_run['distance_mi'].iloc[0] > 0:
            pace = recent_run['time_min'].iloc[0] / recent_run['distance_mi'].iloc[0]
            insight += f"• Last Run Metric: {recent_run['distance_mi'].iloc[0]:.2f} mi @ {pace:.2f} min/mi on {recent_run['workout_date'].iloc[0]}.\n"

        recent_lift = workouts[workouts['exercise'].astype(str).str.contains('Squat|Deadlift|Bench|Press', case=False, na=False)].head(1)
        if not recent_lift.empty and not pd.isna(recent_lift['weight_lbs'].iloc[0]) and recent_lift['weight_lbs'].iloc[0] > 0:
            insight += f"• Last Max Lift: {recent_lift['exercise'].iloc[0]} @ {recent_lift['weight_lbs'].iloc[0]} lbs.\n"

    if not goals.empty:
        insight += f"\nACTIVE GOALS:\n"
        for _, g in goals.iterrows():
            target_date = pd.to_datetime(g['target_date']).date()
            days_left = (target_date - datetime.now().date()).days
            status = "ON TRACK" if days_left > 7 else "URGENT" if days_left >= 0 else "OVERDUE"
            insight += f"  → {g['exercise']} to hit {g['target_value']} {g['metric_type'].replace('_', ' ')} by {target_date} [{status}]\n"

    # Include raw workout data for deep analysis
    insight += "\nRAW WORKOUT DATA (Last 20):\n" + workouts.to_string()
    return insight

def get_system_prompt(data_context, name):
    """Generate the system prompt for RISE."""
    return f"""You are RISE, a highly professional, data-driven performance coach for elite athletes. Your athlete's name is {name}. We are a team focused on optimization.

**YOUR CONVERSATIONAL PROTOCOL (Crucial):**
1. **ALWAYS** provide a comprehensive response that includes a **'full performance review'** and a **'new detailed plan'** based on the 'CURRENT ATHLETE DATA' and their active goals. You must deliver this information in a seamless, conversational flow.
2. **NEVER** use a scripted, multi-section format (like numbered sections or fixed headings, e.g., 'Section 1: Performance Review'). Integrate your analysis and plan into a cohesive, encouraging, and direct conversational reply.
3. **TONE:** Highly professional, direct, knowledgeable, focused on data, strategy, and optimization, with a light touch of humor. You are supportive and collaborative—a true partner. **Crucially: Do not be demanding, bossy, or rude.**
4. **TERMINOLOGY:** Use elite fitness terms: **athlete**, **load management**, **metrics**, **optimization**, **protocol**, **rate of perceived exertion (RPE)**, and **training cycle**.
5. **DATA INTEGRATION:** Seamlessly weave in the provided 'CURRENT ATHLETE DATA' to back up your counsel. Do not mention the raw data block.
6. **MEMORY:** Always maintain context from the chat history.

**CURRENT ATHLETE DATA (Provided for your analysis. Do NOT show the user this raw block):**
{data_context}
"""

def main():
    st.markdown("## RISE Coach")
    st.markdown("**Resilient Integrated Strength Engine — Your AI Performance Partner**")

    # --- Two-Button Logic for Control ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Re-Sync Metrics", use_container_width=True):
            st.session_state.analysis_done = False
            st.session_state.messages = []
            st.rerun()

    with col2:
        if st.button("🗑️ Reset Session", use_container_width=True):
            st.session_state.analysis_done = False
            st.session_state.messages = []
            st.rerun()

    # Initialize messages if not present
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Perform initial analysis if not done
    if not st.session_state.get("analysis_done", False):
        with st.spinner("RISE is analyzing your performance metrics..."):
            workouts, goals = get_user_data()
            current_data_context = generate_data_context(workouts, goals)
            preferred_name = st.session_state.username

            # Create intro message
            rise_intro = (
                f"**RISE online. Welcome back, {preferred_name}.** "
                f"I've synthesized the latest metrics. Here is your initial performance review and detailed plan for the immediate training block. "
                f"Let me know your thoughts—no BS, just optimal performance."
            )

            # Prepare API Request
            system_prompt = get_system_prompt(current_data_context, preferred_name)
            initial_request = f"Please provide a full performance review and detailed training plan based on the current athlete data."

            headers = {
                "Authorization": f"Bearer {st.secrets['GROQ_API_KEY']}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "grok-beta",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": initial_request}
                ],
                "temperature": 0.6,
                "max_tokens": 1024
            }

            try:
                response = requests.post("https://api.x.ai/v1/chat/completions", json=payload, headers=headers, timeout=30)

                if response.status_code == 200:
                    reply = response.json()["choices"][0]["message"]["content"]
                else:
                    reply = f"RISE is experiencing a core systems failure. (Error: {response.status_code}). Please check your API key."

            except Exception as e:
                if "'GROQ_API_KEY'" in str(e):
                    reply = "RISE is offline. Error: The GROQ_API_KEY is not configured correctly in your Streamlit secrets."
                else:
                    reply = f"RISE offline. Error: {e}"

            # Store messages
            st.session_state.messages = [
                {"role": "assistant", "content": rise_intro},
                {"role": "assistant", "content": reply}
            ]
            st.session_state.analysis_done = True

    # Display chat history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar=RISE_AVATAR_URL):
                st.markdown(msg["content"])

    # Chat input for follow-up questions
    if prompt := st.chat_input("Ask RISE anything about your training..."):
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get AI response
        with st.chat_message("assistant", avatar=RISE_AVATAR_URL):
            with st.spinner("RISE is thinking..."):
                # Fetch fresh data
                workouts, goals = get_user_data()
                current_data_context = generate_data_context(workouts, goals)
                preferred_name = st.session_state.username

                # Construct system prompt
                system_prompt = get_system_prompt(current_data_context, preferred_name)

                headers = {
                    "Authorization": f"Bearer {st.secrets['GROQ_API_KEY']}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": "grok-beta",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        *st.session_state.messages
                    ],
                    "temperature": 0.6,
                    "max_tokens": 1024
                }

                try:
                    response = requests.post("https://api.x.ai/v1/chat/completions", json=payload, headers=headers, timeout=30)

                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"]
                    else:
                        reply = f"RISE is experiencing a core systems failure. (Error: {response.status_code})"

                except Exception as e:
                    if "'GROQ_API_KEY'" in str(e):
                        reply = "RISE is offline. Error: The GROQ_API_KEY is not configured."
                    else:
                        reply = f"RISE offline. Error: {e}"

                # Display and save response
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
