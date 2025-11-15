# pages/ai_coach.py
import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine
import numpy as np
import re

# Initialize the SQLAlchemy engine for robust data access
engine = create_engine(st.secrets["POSTGRES_URL"])

# Define the RISE avatar URL globally
RISE_AVATAR_URL = "https://api.dicebear.com/7.x/bottts/svg?seed=RISE"

# --- Groq API Configuration ---
# Use a highly capable Groq-available model as the default
GROQ_MODEL = "mixtral-8x7b-32768"
GROQ_API_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
# --- End Groq API Configuration ---

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
    except Exception:
        # Return empty DataFrames on connection or query failure
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
        # Calculate days since last workout using pandas/numpy for robustness
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
            # Ensure target_date is a datetime.date object for calculation
            target_date = pd.to_datetime(g['target_date']).date()
            days_left_status = (target_date - datetime.now().date()).days
            status = "ON TRACK" if days_left_status > 7 else "URGENT" if days_left_status >= 0 else "OVERDUE"
            
            insight += f"  → {g['exercise']} to hit {g['target_value']} {g['metric_type'].replace('_', ' ')} by {target_date} [{status}]\n"
    
    # Include raw workout data for deep analysis
    insight += "\nRAW WORKOUT DATA (Last 20):\n" + workouts.to_string()
    return insight

def main():
    st.markdown("## RISE Coach")
    st.markdown("**Resilient Integrated Strength Engine — Your AI Performance Partner**")

    # --- Two-Button Logic for Control ---
    col1, col2 = st.columns(2)
    with col1:
        # Re-Sync forces the AI to re-run the full analysis on current data
        if st.button("Re-Sync Metrics", width='stretch'):
            st.session_state.analysis_done = False 
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
    # --- End Two-Button Logic ---

    # Define the System Prompt and API setup once
    def get_system_prompt(data_context, name):
        return f"""
You are RISE, a highly professional, data-driven performance coach for elite athletes. Your athlete's name is {name}. We are a team focused on optimization.

**YOUR CONVERSATIONAL PROTOCOL (Crucial):**
1.  **ALWAYS** provide a comprehensive response that includes a **'full performance review'** and a **'new detailed plan'** based on the 'CURRENT ATHLETE DATA' and their active goals. You must deliver this information in a seamless, conversational flow.
2.  **NEVER** use a scripted, multi-section format (like numbered sections or fixed headings, e.g., 'Section 1: Performance Review'). Integrate your analysis and plan into a cohesive, encouraging, and direct conversational reply.
3.  **TONE:** Highly professional, direct, knowledgeable, focused on data, strategy, and optimization, with a light touch of humor. You are supportive and collaborative—a true partner. **Crucially: Do not be demanding, bossy, or rude.**
4.  **TERMINOLOGY:** Use elite fitness terms: **athlete**, **load management**, **metrics**, **optimization**, **protocol**, **rate of perceived exertion (RPE)**, and **training cycle**.
5.  **DATA INTEGRATION:** Seamlessly weave in the provided 'CURRENT ATHLETE DATA' to back up your counsel. Do not mention the raw data block.
6.  **MEMORY:** Always maintain context from the chat history.

**CURRENT ATHLETE DATA (Provided for your analysis. Do NOT show the user this raw block):**
{data_context}
"""

    # -------------------------------------------------------------------------
    # 💥 FIX: Initial AI Call (Proactive Data Push)
    # -------------------------------------------------------------------------
    if "analysis_done" not in st.session_state:
        with st.spinner("RISE is analyzing your performance metrics..."):
            workouts, goals = get_user_data()
            current_data_context = generate_data_context(workouts, goals)
            preferred_name = st.session_state.username

            if "messages" not in st.session_state:
                st.session_state.messages = []
            
            # Prepare API Request
            system_prompt = get_system_prompt(current_data_context, preferred_name)
            
            # This user message primes the AI to output the required full review and plan
            initial_request_to_ai = f"RISE online. Welcome back, {preferred_name}. I've synced the latest metrics. Please provide your initial full performance review and a detailed plan for the immediate training block, based only on the provided data."
            
            headers = {
                # FIX: Use the correct Groq API Key
                "Authorization": f"Bearer {st.secrets['GROQ_API_KEY']}", 
                "Content-Type": "application/json"
            }
            
            payload = {
                # FIX: Use a Groq-available model
                "model": GROQ_MODEL, 
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": initial_request_to_ai}
                ],
                "temperature": 0.6, 
                "max_tokens": 1024
            }
            
            try:
                # FIX: Use the correct Groq API Endpoint
                response = requests.post(GROQ_API_ENDPOINT, json=payload, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    reply = response.json()["choices"][0]["message"]["content"]
                else:
                    reply = f"RISE is experiencing a core systems failure. (API Error: {response.status_code} - {response.text}). Please ensure your `GROQ_API_KEY` is valid."
            
            except Exception as e:
                if "'GROQ_API_KEY'" in str(e):
                     reply = "RISE is offline. Error: The GROQ_API_KEY is not configured correctly in your Streamlit secrets."
                else:
                     reply = f"RISE offline. An unknown error occurred: {e}"

            # Store the AI's generated response and mark analysis as complete
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.session_state.analysis_done = True
            
            # Rerun to display the initial message immediately
            st.rerun() 
    # -------------------------------------------------------------------------


    # Display the chat history
    for msg in st.session_state.messages:
        avatar = RISE_AVATAR_URL if msg["role"] == "assistant" else "user"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Handle new user input
    if prompt := st.chat_input("Talk to your coach..."):
        # 1. Append user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Start assistant response block
        with st.chat_message("assistant", avatar=RISE_AVATAR_URL):
            with st.spinner("RISE is processing the data..."):
                try:
                    # 3. Prepare for Groq API call
                    headers = {
                        # FIX: Use the correct Groq API Key
                        "Authorization": f"Bearer {st.secrets['GROQ_API_KEY']}", 
                        "Content-Type": "application/json"
                    }
                    
                    # Fetch fresh data context for the current query
                    workouts, goals = get_user_data()
                    current_data_context = generate_data_context(workouts, goals)
                    preferred_name = st.session_state.username
                    
                    # Construct system prompt using the helper function
                    system_prompt = get_system_prompt(current_data_context, preferred_name)
                    
                    payload = {
                        # FIX: Use a Groq-available model
                        "model": GROQ_MODEL, 
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            # The chat history (including the new user prompt) is sent here
                            *st.session_state.messages 
                        ],
                        "temperature": 0.6, 
                        "max_tokens": 1024
                    }
                    
                    # FIX: Use the correct Groq API Endpoint
                    response = requests.post(GROQ_API_ENDPOINT, json=payload, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"]
                    else:
                        reply = f"RISE is experiencing a core systems failure. (API Error: {response.status_code} - {response.text}). Please ensure your `GROQ_API_KEY` is valid."
                
                except Exception as e:
                    if "'GROQ_API_KEY'" in str(e):
                         reply = "RISE is offline. Error: The GROQ_API_KEY is not configured correctly in your Streamlit secrets."
                    else:
                         reply = f"RISE offline. An unknown error occurred: {e}"

                # 4. Display and save assistant response
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
