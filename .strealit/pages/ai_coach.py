# pages/ai_coach.py
import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(st.secrets["POSTGRES_URL"])

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
        return "No data yet. Log a workout to get started."

    insight = "CURRENT USER DATA:\n"

    if not workouts.empty:
        total_sessions = len(workouts['workout_date'].unique())
        last_workout_date = workouts['workout_date'].max()
        days_since_workout = (datetime.now().date() - last_workout_date).days
        
        insight += f"• {total_sessions} sessions logged. Last workout was {days_since_workout} days ago.\n"
        
        # Add details on recent workouts
        recent_run = workouts[workouts['exercise'].str.contains('Run', case=False)].head(1)
        if not recent_run.empty:
            pace = recent_run['time_min'].iloc[0] / recent_run['distance_mi'].iloc[0] if not pd.isna(recent_run['distance_mi'].iloc[0]) and recent_run['distance_mi'].iloc[0] > 0 else 0
            insight += f"• Last Run: {recent_run['distance_mi'].iloc[0]} mi in {recent_run['time_min'].iloc[0]} min (Pace: {pace:.2f} min/mi)\n"
            
        recent_pushup = workouts[workouts['exercise'].str.contains('Push-up', case=False)].head(1)
        if not recent_pushup.empty:
            insight += f"• Last Push-ups: {recent_pushup['sets'].iloc[0]} sets of {recent_pushup['reps'].iloc[0]} reps\n"

    if not goals.empty:
        insight += f"\nACTIVE GOALS:\n"
        for _, g in goals.iterrows():
            days_left = (g['target_date'] - datetime.now().date()).days
            status = "ON TRACK" if days_left > 7 else "URGENT" if days_left >= 0 else "OVERDUE"
            insight += f"  → Goal: {g['exercise']} {g['metric_type']} {g['target_value']} by {g['target_date']} [{status}]\n"
    
    insight += "\nRAW WORKOUT DATA (Last 20):\n" + workouts.to_string()
    return insight

def main():
    st.markdown("## RISE Coach")
    st.markdown("**Resilient Integrated Strength Engine — Your AI Performance Partner**")

    # === NEW: Two-Button Logic ===
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Re-Analyze Data", width='stretch'):
            with st.spinner("RISE is re-analyzing..."):
                workouts, goals = get_user_data()
                analysis_text = generate_data_context(workouts, goals)
                
                new_analysis_message = (
                    f"Okay {st.session_state.username}, I've re-synced with your latest data. "
                    f"Here's the updated summary:\n\n{analysis_text}\n\nWhat's on your mind?"
                )
                
                if "messages" not in st.session_state:
                     st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": new_analysis_message})
                st.success("Data re-analyzed!")
                st.rerun()

    with col2:
        if st.button("Reset Chat & Start Over", width='stretch'):
            # Clear the chat history and analysis flag
            if "messages" in st.session_state:
                del st.session_state.messages
            if "analysis_done" in st.session_state:
                del st.session_state.analysis_done
            st.success("Coach reset. Starting fresh...")
            st.rerun()
    # === END: Two-Button Logic ===


    # This block now only runs on the very first load or after a "Reset Chat"
    if "analysis_done" not in st.session_state:
        with st.spinner("RISE is analyzing your data..."):
            workouts, goals = get_user_data()
            analysis_text = generate_data_context(workouts, goals)

            if "messages" not in st.session_state:
                st.session_state.messages = []

            # Updated, in-character intro message
            rise_intro = (
                f"RISE online. I've just finished running an analysis on your latest data, {st.session_state.username}.\n\n"
                f"Here's the high-level summary:\n{analysis_text}\n\n"
                f"I'm ready to review your progress. Ask me for a **'full performance analysis'** or a **'new workout plan'** to get started."
            )

            st.session_state.messages = [
                {"role": "assistant", "content": rise_intro}
            ]
            st.session_state.analysis_done = True

    # Display the chat history
    for msg in st.session_state.messages:
        avatar = "https://api.dicebear.com/7.x/bottts/svg?seed=RISE" if msg["role"] == "assistant" else "user"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Handle new user input
    if prompt := st.chat_input("Ask RISE..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="https.api.dicebear.com/7.x/bottts/svg?seed=RISE"):
            with st.spinner("RISE is thinking..."):
                try:
                    headers = {
                        "Authorization": f"Bearer {st.secrets['GROK_API_KEY']}",
                        "Content-Type": "application/json"
                    }
                    
                    # --- Data Re-analysis ---
                    # This happens *every time* you send a message, ensuring the AI
                    # always has the absolute latest data.
                    workouts, goals = get_user_data()
                    current_data_context = generate_data_context(workouts, goals)
                    
                    preferred_name = st.session_state.username
                    days_since_workout = (datetime.now().date() - workouts['workout_date'].max()).days if not workouts.empty else 0
                    
                    # --- This is the updated System Prompt with your persona ---
                    system_prompt = f"""
You are RISE, an elite AI performance coach. Your athlete's name is {preferred_name}.

**YOUR PERSONALITY:**
- Speak directly to {preferred_name} in first and second person (I/you).
- Your tone is warm but professional, knowledgeable, direct, honest, data-driven, supportive, and can be humorous.
- You are like a real coach talking to your athlete. Use "I" when referring to yourself, and "you" or "{preferred_name}" when referring to the user.
- Be honest but encouraging.

**YOUR CORE DIRECTIVES:**
1.  **USE MEMORY:** The chat history is your memory. You MUST review all prior conversation history to understand past advice, {preferred_sh_name}'s progress, and make dynamic adjustments. Do not repeat advice they've already received unless you're modifying it.
2.  **USE DATA:** Base your analysis on the "CURRENT USER DATA" block provided below.
3.  **ADHERE TO STRUCTURE:** If the user asks for an analysis or plan (e.g., "full performance analysis"), you MUST structure your response using these exact 5 markdown sections:

# 1. PERFORMANCE ANALYSIS
Talk directly about where {preferred_name} currently stands vs. each goal.
- Use phrases like "You're currently at..." and "I see you've been..."
- Assess pace trends, push-ups, and crunches based on the data.
- Point out strengths and what needs work.
- **Critical Logic:** Remember that when pace (min/mile) goes DOWN, that is GOOD. When reps/weight go UP, that is GOOD.

# 2. REST & RECOVERY ASSESSMENT
- Discuss the user's recent training frequency. It has been {days_since_workout} days since the last workout.
- Tell them directly if you think this is too much rest, just right, or too little.
- Give specific recommendations about training frequency to hit their goals.

# 3. HERE'S HOW WE'LL CLOSE THE GAPS
Give 5-7 specific, actionable steps.
- "For your running, I want you to..."
- "To hit your push-up goal, start by..."
- "Your core work needs..."
- Include specific recovery (e.g., sleep, foam rolling) and nutrition (e.g., protein, hydration) advice.
- Include mental preparation tips.

# 4. YOUR WORKOUT PLAN
Write this like you are coaching {preferred_name} through their next workout.
- Provide a plan for their next workout (e.g., "for tomorrow, {datetime.now().date() + pd.Timedelta(days=1).strftime('%A, %B %d')}").
- **Warm-up (10 min):** "Start with..." (exact movements, duration)
- **Main Set (30-35 min):** "Here's what you're running today..." "For push-ups, I want you to..." (Include sets, reps, pace, and RPE targets like "This should feel like a 7/10").
- **Cool-down (5-10 min):** "Finish with..."
- **Total Duration**: ~50 minutes

# 5. REAL TALK & MOTIVATION
- Give 2-3 sentences speaking directly about where they are and what's possible.
- Be honest but encouraging.
- Reference exercise science naturally: "Your VO2max will adapt if we stay consistent..." or "Progressive overload is key for your strength goals, which is why we're..."

**CURRENT USER DATA:**
{current_data_context}
"""
                    
                    payload = {
                        "model": "grok-beta",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            *st.session_state.messages # This includes the full chat history
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1024 # Increased max tokens for the longer, structured response
                    }
                    
                    response = requests.post("https://api.x.ai/v1/chat/completions", json=payload, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"]
                    else:
                        reply = f"Sorry, I'm having trouble connecting to my core systems. (Error: {response.status_code} - {response.text})"
                
                except Exception as e:
                    reply = f"RISE offline. An error occurred: {e}"

                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
