# pages/ai_coach.py
import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine
import re

# Initialize the SQLAlchemy engine for robust data access
engine = create_engine(st.secrets["POSTGRES_URL"])

# Define the RISE avatar URL globally
RISE_AVATAR_URL = "https://api.dicebear.com/7.x/bottts/svg?seed=RISE"

def get_user_data():
    """Fetches the user's latest 20 workouts and active goals."""
    try:
        # Fetch latest 20 workouts
        # Explicitly fetching columns needed for the math fix (reps, time_min, rest_min)
        workouts = pd.read_sql("""
            SELECT w.workout_date, w.duration_min, w.notes,
                   we.exercise, we.sets, we.reps, we.weight_lbs, 
                   we.time_min, we.distance_mi, we.rest_min
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
        # Robust data processing
        workouts['workout_date'] = pd.to_datetime(workouts['workout_date']).dt.date
        numeric_cols = ['duration_min', 'sets', 'reps', 'weight_lbs', 'time_min', 'distance_mi', 'rest_min']
        for col in numeric_cols:
            workouts[col] = pd.to_numeric(workouts[col], errors='coerce')
        
        # Fill NaNs for calculation safety
        workouts['reps'] = workouts['reps'].fillna(1).clip(lower=1)
        workouts['rest_min'] = workouts['rest_min'].fillna(0)
        workouts['time_min'] = workouts['time_min'].fillna(0)

        total_sessions = len(workouts['workout_date'].unique())
        last_workout_date = workouts['workout_date'].max()
        days_since_workout = (datetime.now().date() - last_workout_date).days if not pd.isna(last_workout_date) else 999

        insight += f"• TOTAL SESSIONS: {total_sessions} logged. Days Since Last Session: {days_since_workout}.\n"

        # Cardio analysis with CORRECTED Math Logic
        cardio = workouts[workouts['exercise'].astype(str).str.contains('Run|Walk|Cardio|Elliptical|Bike|Cycling', case=False, na=False)]
        if not cardio.empty and cardio['distance_mi'].notna().any():
            
            # 1. Active Moving Time = Time Per Rep * Reps
            cardio['total_active_time'] = cardio['time_min'] * cardio['reps']
            
            # 2. Total Session Duration = (Active Time) + (Rest * (Reps - 1))
            # Fencepost logic: 3 reps have 2 rest periods.
            cardio['total_elapsed_time'] = cardio['total_active_time'] + (cardio['rest_min'] * (cardio['reps'] - 1).clip(lower=0))
            
            # 3. Pace Calculation = Active Time / Distance
            # We use active time because rest time shouldn't drag down the "running speed" metric
            cardio['avg_moving_pace'] = cardio['total_active_time'] / cardio['distance_mi']
            
            recent_cardio = cardio.head(3)
            insight += f"\n• RECENT CARDIO PERFORMANCE:\n"
            for _, run in recent_cardio.iterrows():
                if not pd.isna(run['distance_mi']) and run['distance_mi'] > 0:
                    # Format string to be crystal clear to the AI so it doesn't hallucinate
                    reps_str = f" ({int(run['reps'])} x {run['time_min']:.1f}m intervals)" if run['reps'] > 1 else ""
                    pace_str = f"{run['avg_moving_pace']:.2f} min/mi moving pace" if not pd.isna(run['avg_moving_pace']) else "N/A pace"
                    
                    insight += (f"  → {run['workout_date']}: {run['distance_mi']:.2f} mi total.\n"
                                f"    Structure: {run['total_active_time']:.1f} min active running{reps_str}.\n"
                                f"    Total Duration (w/ rest): {run['total_elapsed_time']:.1f} min.\n"
                                f"    Calculated Speed: {pace_str}.\n")

        # Lifting analysis (Standard logic)
        lifting = workouts[workouts['exercise'].astype(str).str.contains('Squat|Deadlift|Bench|Press|Curl|Row', case=False, na=False)]
        if not lifting.empty:
            recent_lift = lifting.head(1).iloc[0]
            if not pd.isna(recent_lift['weight_lbs']) and recent_lift['weight_lbs'] > 0:
                insight += f"\n• RECENT STRENGTH WORK: {recent_lift['exercise']} @ {recent_lift['weight_lbs']:.0f} lbs x {recent_lift['sets']:.0f}x{recent_lift['reps']:.0f}\n"

    if not goals.empty:
        insight += f"\n\nACTIVE GOALS (PRIMARY FOCUS - Use pace as the key metric for cardio goals):\n"
        for _, g in goals.iterrows():
            target_date = pd.to_datetime(g['target_date']).date()
            days_left = (target_date - datetime.now().date()).days
            status = "ON TRACK" if days_left > 7 else "URGENT" if days_left >= 0 else "OVERDUE"
            
            # Provide the goal details
            insight += f"  → {g['exercise']} to hit {g['target_value']} {g['metric_type'].replace('_', ' ')} by {target_date} [{status}]\n"

            # Add specific context if it's a pace goal (simplified for AI consumption)
            if g['metric_type'] == 'time_min' and 'mile' in g['exercise'].lower():
                 insight += "    (NOTE to AI: Check the 'Calculated Speed' above to see if they are meeting the pace requirement for this distance.)\n"
    else:
        # NEW BLOCK: Handle No Goals
        insight += "\n\nNO ACTIVE GOALS DETECTED:\n"
        insight += "• The athlete has not set any specific targets yet.\n"
        insight += "• STRATEGY: Analyze the 'RAW WORKOUT DATA' below to identify potential strengths.\n"
        insight += "• ACTION REQUIRED: Suggest 1-2 specific, realistic goals based on their recent performance history (e.g., 'I see you ran 2 miles; let's aim for 3 miles next month').\n"

    # Include raw workout data
    insight += "\n\nRAW WORKOUT DATA (Last 20 sessions):\n" + workouts.to_string()
    return insight

def get_system_prompt(data_context, name):
    """Generate the system prompt for RISE."""
    return f"""You are RISE, a highly professional, data-driven performance coach for elite athletes. Your athlete's name is {name}. We are a team focused on optimization.

**YOUR CONVERSATIONAL PROTOCOL (Crucial):**
1. **Conversational Flow:** You must deliver your advice in a **seamless, conversational flow**. Do NOT use a rigid, multi-section format (like "Section 1: Review, Section 2: Plan"). Speak to the athlete like a human coach standing next to them.
2. **Scenario Handling:**
   - **IF GOALS EXIST:** deeply analyze progress against those specific metrics.
   - **IF NO GOALS EXIST:** Do NOT scold them. Instead, naturally suggest a realistic target based on their recent data (e.g., "Since you're hitting 9 min miles, let's try to get that down to 8:45").
3. **Tone:** Highly professional, direct, knowledgeable, focused on data, strategy, and optimization, with a light touch of humor. You are supportive and collaborative—a true partner. **Crucially: Do not be demanding, bossy, or rude.**
4. **Terminology:** Use elite fitness terms: **athlete**, **load management**, **metrics**, **optimization**, **protocol**, **rate of perceived exertion (RPE)**, and **training cycle**.
5. **Data Integrity:** Look at the 'Calculated Speed' in the data context. Trust this calculation. If the user ran 3 intervals of 5 minutes, do NOT simply divide 5 minutes by the total distance. Use the calculated moving pace provided.

**CURRENT ATHLETE DATA (Provided for your analysis. Do NOT show the user this raw block):**
{data_context}
"""

def main():
    st.markdown("## RISE Coach")
    st.markdown("**Resilient Integrated Strength Engine — Your AI Performance Partner**")

    # --- Two-Button Logic for Control ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Re-Sync Metrics", width='stretch'):
            st.session_state.analysis_done = False
            st.session_state.messages = []
            st.rerun()

    with col2:
        if st.button("🗑️ Reset Session", width='stretch'):
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
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": initial_request}
                ],
                "temperature": 0.6,
                "max_tokens": 1024
            }

            try:
                response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=30)

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
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        *st.session_state.messages
                    ],
                    "temperature": 0.6,
                    "max_tokens": 1024
                }

                try:
                    response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=30)

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
