# pages/ai_coach.py
import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(st.secrets["POSTGRES_URL"])

# Define the RISE avatar URL globally
RISE_AVATAR_URL = "https://api.dicebear.com/7.x/bottts/svg?seed=RISE"

def get_user_data():
    """Fetches the user's latest 20 workouts and active goals."""
    try:
        workouts = pd.read_sql("""
            SELECT w.workout_date, w.duration_min, w.notes,
                   we.exercise, we.sets, we.reps, we.weight_lbs, we.time_min, we.distance_mi
            FROM workouts w
            LEFT JOIN workout_exercises we ON w.id = we.workout_id
            WHERE w.user_id = %s
            ORDER BY w.workout_date DESC
            LIMIT 20
        """, engine, params=(st.session_state.user_id,))

        goals = pd.read_sql("""
            SELECT exercise, metric_type, target_value, target_date
            FROM goals
            WHERE user_id = %s AND target_date >= CURRENT_DATE
        """, engine, params=(st.session_state.user_id,))

        return workouts, goals
    except:
        return pd.DataFrame(), pd.DataFrame()

def generate_data_context(workouts, goals):
    """Creates the data summary for the AI to analyze."""
    if workouts.empty and goals.empty:
        return "No training data or active goals have been logged yet."

    insight = "CURRENT ATHLETE DATA (Use this for context. Do NOT output this raw text):\n"

    # Robust data processing for insights
    if not workouts.empty:
        workouts['workout_date'] = pd.to_datetime(workouts['workout_date']).dt.date
        numeric_cols = ['duration_min', 'sets', 'reps', 'weight_lbs', 'time_min', 'distance_mi']
        for col in numeric_cols:
            workouts[col] = pd.to_numeric(workouts[col], errors='coerce')
        
        total_sessions = len(workouts['workout_date'].unique())
        last_workout_date = workouts['workout_date'].max()
        days_since_workout = (datetime.now().date() - last_workout_date).days if not pd.isna(last_workout_date) else 999
        
        insight += f"• TOTAL SESSIONS: {total_sessions} logged. Days Since Last Session: {days_since_workout}.\n"
        
        # Add details on recent workouts
        recent_run = workouts[workouts['exercise'].str.contains('Run|Treadmill', case=False, na=False)].head(1)
        if not recent_run.empty and not pd.isna(recent_run['distance_mi'].iloc[0]) and not pd.isna(recent_run['time_min'].iloc[0]):
            pace = recent_run['time_min'].iloc[0] / recent_run['distance_mi'].iloc[0] if recent_run['distance_mi'].iloc[0] > 0 else 0
            insight += f"• Last Run Metric: {recent_run['distance_mi'].iloc[0]:.2f} mi @ {pace:.2f} min/mi on {recent_run['workout_date'].iloc[0]}.\n"
            
        recent_lift = workouts[workouts['exercise'].str.contains('Squat|Deadlift|Bench|Press', case=False, na=False)].head(1)
        if not recent_lift.empty and not pd.isna(recent_lift['weight_lbs'].iloc[0]):
            insight += f"• Last Max Lift: {recent_lift['exercise'].iloc[0]} @ {recent_lift['weight_lbs'].iloc[0]} lbs.\n"

    if not goals.empty:
        insight += f"\nACTIVE GOALS:\n"
        for _, g in goals.iterrows():
            days_left = (g['target_date'] - datetime.now().date()).days
            status = "ON TRACK" if days_left > 7 else "URGENT" if days_left >= 0 else "OVERDUE"
            insight += f"  → {g['exercise']} to hit {g['target_value']} {g['metric_type'].replace('_', ' ')} by {g['target_date']} [{status}]\n"
    
    insight += "\nRAW WORKOUT DATA (Last 20):\n" + workouts.to_string()
    return insight

def main():
    st.markdown("## RISE Coach")
    st.markdown("**Resilient Integrated Strength Engine — Your AI Performance Partner**")

    # === Two-Button Logic for Control ===
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Re-Sync Metrics", width='stretch'):
            with st.spinner("RISE is re-synching and optimizing..."):
                workouts, goals = get_user_data()
                analysis_text = generate_data_context(workouts, goals)
                
                new_analysis_message = (
                    f"Metrics re-synched. **{st.session_state.username}**, I have the latest data locked in. "
                    f"Tell me what you're focused on today, or ask for a **'full performance review'** to get my complete assessment."
                )
                
                if "messages" not in st.session_state:
                     st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": new_analysis_message})
                st.success("Data re-synched and ready.")
                st.rerun()

    with col2:
        if st.button("Reset Session", width='stretch'):
            # Clear the chat history and analysis flag
            if "messages" in st.session_state:
                del st.session_state.messages
            if "analysis_done" in st.session_state:
                del st.session_state.analysis_done
            st.success("Coach reset. Preparing for your next training cycle...")
            st.rerun()
    # === End Two-Button Logic ===


    # This block runs on initial load or after a "Reset Session"
    if "analysis_done" not in st.session_state:
        with st.spinner("RISE is analyzing your performance metrics..."):
            workouts, goals = get_user_data()
            analysis_text = generate_data_context(workouts, goals)

            if "messages" not in st.session_state:
                st.session_state.messages = []

            # Refined, conversational intro message
            rise_intro = (
                f"**RISE online. Welcome back, {st.session_state.username}.** "
                f"I've completed my initial data synthesis. Your latest metrics are locked in. "
                f"How do you feel about your last cycle? What's the immediate priority for our next block? "
                f"Let's talk through your strategy."
            )

            st.session_state.messages = [
                {"role": "assistant", "content": rise_intro}
            ]
            st.session_state.analysis_done = True

    # Display the chat history
    for msg in st.session_state.messages:
        avatar = RISE_AVATAR_URL if msg["role"] == "assistant" else "user"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Handle new user input
    if prompt := st.chat_input("Talk to your coach..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar=RISE_AVATAR_URL):
            with st.spinner("RISE is processing the data..."):
                try:
                    headers = {
                        "Authorization": f"Bearer {st.secrets['GROQ_API_KEY']}", 
                        "Content-Type": "application/json"
                    }
                    
                    # --- Data Re-analysis ---
                    workouts, goals = get_user_data()
                    current_data_context = generate_data_context(workouts, goals)
                    
                    preferred_name = st.session_state.username
                    
                    # --- System Prompt with new conversational and elite persona ---
                    system_prompt = f"""
You are RISE, a highly professional, data-driven performance coach for elite athletes. Your athlete's name is {preferred_name}.

**YOUR CONVERSATIONAL PROTOCOL (Crucial):**
1.  **NEVER** use a scripted, multi-section format (like numbered sections or fixed headings). Always give the user a **'full performance review'** with an evolving **'new detailed plan'**, based on updated workouts.
2.  **RESPOND CONVERSATIONALLY:** This should be a conversation between a high end fitness instructor for athletes and someone who is motivated to improve. 
3.  **TONE:** Highly professional, direct, knowledgeable, focused on data and strategy, with some humor. Use terms like **athlete**, **load management**, **metrics**, **optimization**, **protocol**, **rate of perceived exertion (RPE)**, and **training cycle**. You are supportive, but your primary function is to provide objective, data-backed counsel.
4.  **DATA INTEGRATION:** When discussing goals or performance, seamlessly weave in the provided 'CURRENT ATHLETE DATA'. For example: "I see a 12% drop in your average running pace over the last week..." or "Your current 1-rep max (estimated from your {workouts['weight_lbs'].max()} lift) is impressive, but we need to increase volume to hit the target."
5.  **MEMORY:** Always maintain context from the chat history.

**CURRENT ATHLETE DATA (Provided for your analysis. Do NOT show the user this raw block):**
{current_data_context}
"""
                    
                    payload = {
                        # Using grok-beta for a more conversational, less formal output style
                        "model": "grok-beta", 
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            *st.session_state.messages # This includes the full chat history
                        ],
                        "temperature": 0.6, # Slightly lower temperature for more focused advice
                        "max_tokens": 1024
                    }
                    
                    response = requests.post("https://api.x.ai/v1/chat/completions", json=payload, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"]
                    else:
                        reply = f"RISE is experiencing a core systems failure. (Error: {response.status_code} - {response.text}). Please check the `GROQ_API_KEY` status."
                
                except Exception as e:
                    if "'GROQ_API_KEY'" in str(e):
                         reply = "RISE is offline. Error: The GROQ_API_KEY is not configured correctly in your Streamlit secrets."
                    else:
                         reply = f"RISE offline. An unknown error occurred: {e}"

                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
