# pages/ai_coach.py
import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(st.secrets["POSTGRES_URL"])

# ------------------------------------------------------------------------------
# NEW SYSTEM PROMPT FUNCTION (Incorporating your detailed protocol)
# ------------------------------------------------------------------------------
def get_system_prompt(data_context, name):
    # 'name' is assumed to be in st.session_state.username
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
# ------------------------------------------------------------------------------


def get_user_data():
    try:
        # Fetch up to 20 recent workouts with their exercises
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
    except:
        return pd.DataFrame(), pd.DataFrame()

def generate_insight_prompt(workouts, goals):
    if workouts.empty and goals.empty:
        return "No data yet. Instruct the user to log a workout to get started."

    insight = "RISE ANALYSIS:\n"

    # Workout Stats
    if not workouts.empty:
        total_sessions = len(workouts['workout_date'].unique())
        total_min = workouts['duration_min'].sum()
        avg_min_per_session = workouts.groupby('workout_date')['duration_min'].sum().mean()
        
        insight += f"Total Sessions Logged: {total_sessions}\n"
        insight += f"Total Time Logged: {total_min:.0f} minutes\n"
        insight += f"Average Session Duration: {avg_min_per_session:.1f} minutes\n"
        
        # Format workout data for LLM
        workouts_list = []
        for date, group in workouts.groupby('workout_date'):
            workout_summary = f"Date: {date.strftime('%Y-%m-%d')}, Duration: {group['duration_min'].iloc[0]} min, Notes: {group['notes'].iloc[0].strip()}\n"
            exercises = []
            for _, row in group.iterrows():
                ex_details = f"- {row['exercise']}: {row['sets']} sets"
                if row['reps'] and row['reps'] > 0: ex_details += f", {row['reps']} reps"
                if row['weight_lbs'] and row['weight_lbs'] > 0: ex_details += f", {row['weight_lbs']} lbs"
                if row['time_min'] and row['time_min'] > 0: ex_details += f", {row['time_min']} min"
                if row['distance_mi'] and row['distance_mi'] > 0: ex_details += f", {row['distance_mi']} mi"
                exercises.append(ex_details)
            workouts_list.append(workout_summary + "\n".join(exercises))
        
        insight += "Recent Workouts (Last 20):\n" + "\n---\n".join(workouts_list) + "\n"
    
    # Goals
    if not goals.empty:
        goals['target_date'] = pd.to_datetime(goals['target_date']).dt.strftime('%Y-%m-%d')
        goals_summary = goals.to_string(index=False, header=True)
        insight += f"\nActive Goals:\n{goals_summary}\n"
        
    return insight

def main():
    if not st.session_state.get("logged_in"):
        st.error("Please log in to use the AI Coach.")
        return

    st.markdown("## RISE AI Coach")
    st.markdown("Your **R**eal-time **I**ntelligent **S**upport & **E**valuation system.")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        avatar = "https://api.dicebear.com/7.x/bottts/svg?seed=RISE" if message["role"] == "assistant" else None
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    # Accept user input
    prompt = st.chat_input("Ask RISE for advice, analysis, or your next workout...")

    if prompt:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="https://api.dicebear.com/7.x/bottts/svg?seed=RISE"):
            with st.spinner("RISE is thinking..."):
                try:
                    # --- GROQ API SETUP ---
                    headers = {
                        "Authorization": f"Bearer {st.secrets['GROQ_API_KEY']}", # Correct Key Name
                        "Content-Type": "application/json"
                    }
                    workouts, goals = get_user_data()
                    context = generate_insight_prompt(workouts, goals)
                    
                    # Use the new detailed system prompt function
                    system_content = get_system_prompt(context, st.session_state.username)

                    payload = {
                        "model": "llama3-70b-8192", # Correct, supported Groq Model
                        "messages": [
                            {"role": "system", "content": system_content},
                            *st.session_state.messages
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1024 # Increased for comprehensive response
                    }
                    
                    # Correct Groq API Endpoint
                    response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"]
                    else:
                        st.error(f"RISE API Error: {response.status_code} - {response.text}")
                        reply = "RISE offline due to API connection error. Check your `GROQ_API_KEY` and the model name in your Streamlit secrets."
                        
                except Exception as e:
                    # Catch connection or JSON parsing errors
                    st.error(f"RISE offline. An exception occurred: {e}")
                    reply = "RISE offline. Try again."

                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
