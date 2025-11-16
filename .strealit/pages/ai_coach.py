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
        # Robust data processing
        workouts['workout_date'] = pd.to_datetime(workouts['workout_date']).dt.date
        numeric_cols = ['duration_min', 'sets', 'reps', 'weight_lbs', 'time_min', 'distance_mi']
        for col in numeric_cols:
            workouts[col] = pd.to_numeric(workouts[col], errors='coerce')

        total_sessions = len(workouts['workout_date'].unique())
        last_workout_date = workouts['workout_date'].max()
        days_since_workout = (datetime.now().date() - last_workout_date).days if not pd.isna(last_workout_date) else 999

        insight += f"• TOTAL SESSIONS: {total_sessions} logged. Days Since Last Session: {days_since_workout}.\n"

        # Cardio analysis with pace
        cardio = workouts[workouts['exercise'].astype(str).str.contains('Run|Walk|Cardio|Elliptical|Bike|Cycling', case=False, na=False)]
        if not cardio.empty and cardio['distance_mi'].notna().any():
            # Calculate pace for cardio workouts
            cardio['pace_min_mi'] = cardio['time_min'] / cardio['distance_mi']
            
            recent_cardio = cardio.head(3)
            insight += f"\n• RECENT CARDIO PERFORMANCE:\n"
            for _, run in recent_cardio.iterrows():
                if not pd.isna(run['distance_mi']) and not pd.isna(run['pace_min_mi']) and run['distance_mi'] > 0:
                    insight += f"  → {run['workout_date']}: {run['distance_mi']:.1f} mi in {run['time_min']:.0f} min ({run['pace_min_mi']:.2f} min/mi pace)\n"

        # Lifting analysis
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
            
            # Parse pace goals
            goal_text = g['exercise'].lower()
            dist_match = re.search(r'(\d*\.?\d+)\s*(mile|mi)', goal_text)
            time_match = re.search(r'(\d+)\s*(min|minute|mins)', goal_text)
            
            if dist_match and time_match and g['metric_type'] == 'time_min':
                distance = float(dist_match.group(1))
                time_target = float(time_match.group(1))
                target_pace = time_target / distance
                
                # Calculate current performance
                if not workouts.empty:
                    cardio = workouts[workouts['exercise'].astype(str).str.contains('Run|Walk|Cardio', case=False, na=False)]
                    if not cardio.empty and cardio['distance_mi'].notna().any():
                        cardio['pace_min_mi'] = cardio['time_min'] / cardio['distance_mi']
                        best_pace = cardio['pace_min_mi'].min()
                        longest_distance = cardio['distance_mi'].max()
                        
                        pace_gap = best_pace - target_pace if not pd.isna(best_pace) else 999
                        distance_gap = distance - longest_distance if not pd.isna(longest_distance) else distance
                        
                        insight += f"  → GOAL: {g['exercise']} by {target_date} [{status}]\n"
                        insight += f"    TARGET: {distance:.1f} mi in {time_target:.0f} min = {target_pace:.2f} min/mi pace\n"
                        insight += f"    CURRENT BEST PACE: {best_pace:.2f} min/mi (gap: {pace_gap:+.2f} min/mi)\n"
                        insight += f"    LONGEST DISTANCE: {longest_distance:.1f} mi (gap: {distance_gap:+.1f} mi)\n"
                        insight += f"    FOCUS: {'Improve pace by {:.2f} min/mi AND build endurance for {:.1f} more miles'.format(abs(pace_gap), abs(distance_gap)) if pace_gap > 0 or distance_gap > 0 else 'GOAL ACHIEVED - maintain or set new goal'}\n"
                    else:
                        insight += f"  → GOAL: {g['exercise']} by {target_date} [{status}]\n"
                        insight += f"    TARGET: {distance:.1f} mi @ {target_pace:.2f} min/mi pace\n"
                        insight += f"    STATUS: No cardio data yet - need baseline assessment\n"
            else:
                # Standard goal
                insight += f"  → {g['exercise']} to hit {g['target_value']} {g['metric_type'].replace('_', ' ')} by {target_date} [{status}]\n"

    # Include raw workout data
    insight += "\n\nRAW WORKOUT DATA (Last 20 sessions):\n" + workouts.to_string()
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
6. **MEMORY:** Always maintain context from the chat history. Remember your previous recommendations and refer to them naturally.

**PACE AS PRIMARY CARDIO METRIC (Critical):**
- For cardio goals, PACE (min/mi) is the PRIMARY performance indicator, not raw time or distance alone.
- Understand that hitting a 9 min/mi pace on a 0.5-mile run shows speed capability, but the athlete still needs to build ENDURANCE to sustain it over 2 miles.
- When giving feedback:
  - If pace is met but distance isn't: Focus on endurance building (longer runs at easier pace, tempo runs, long slow distance)
  - If distance is met but pace isn't: Focus on speed work (intervals, fartleks, tempo runs at goal pace)
  - If both are improving: Recognize progress and adjust training stimulus
- Shorter interval workouts at goal pace or better are VALUABLE training - don't discount them because distance wasn't met. They build speed that will transfer to longer distances.
- Example good feedback: "Your 5-minute intervals at 8.5 min/mi show you CAN hit the pace. Now we need to extend that endurance so you can hold it for the full 2 miles."

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
