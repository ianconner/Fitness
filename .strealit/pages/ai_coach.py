# pages/ai_coach.py
import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(st.secrets["POSTGRES_URL"])

# Define the RISE avatar URL globally to prevent typos
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
        return "No data yet. This is a great time to start with a beginner plan—let's build from here."

    insight = "CURRENT USER DATA:\n"

    if not workouts.empty:
        total_sessions = len(workouts['workout_date'].unique())
        last_workout_date = workouts['workout_date'].max()
        days_since_workout = (datetime.now().date() - last_workout_date).days if not pd.isna(last_workout_date) else 0
        
        insight += f"• {total_sessions} sessions logged. Last workout was {days_since_workout} days ago.\n"
        
        # Add details on recent workouts
        recent_run = workouts[workouts['exercise'].str.contains('Run', case=False)].head(1)
        if not recent_run.empty and not pd.isna(recent_run['distance_mi'].iloc[0]) and not pd.isna(recent_run['time_min'].iloc[0]):
            pace = recent_run['time_min'].iloc[0] / recent_run['distance_mi'].iloc[0] if recent_run['distance_mi'].iloc[0] > 0 else 0
            insight += f"• Last Run: {recent_run['distance_mi'].iloc[0]} mi in {recent_run['time_min'].iloc[0]} min (Pace: {pace:.2f} min/mi)\n"
            
        recent_pushup = workouts[workouts['exercise'].str.contains('Push-up', case=False)].head(1)
        if not recent_pushup.empty and not pd.isna(recent_pushup['sets'].iloc[0]) and not pd.isna(recent_pushup['reps'].iloc[0]):
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

    # === CSS for Normal Conversation Text ===
    st.markdown("""
    <style>
        .stMarkdown { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        .stMarkdown > h1 {font-size: 1.8em !important; font-weight: 600 !important;}
        .stMarkdown > h2 {font-size: 1.4em !important; font-weight: 600 !important;}
        .stMarkdown > h3 {font-size: 1.2em !important; font-weight: 600 !important;}
        .stMarkdown > p {font-size: 16px !important; line-height: 1.6 !important;}
        .stMarkdown > li {font-size: 16px !important; line-height: 1.6 !important;}
        .stMarkdown > strong {font-weight: 600 !important;} /* Bold okay */
    </style>
    """, unsafe_allow_html=True)

    # === Two-Button Logic for Control ===
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Re-Analyze Data", width='stretch'):
            with st.spinner("RISE is re-analyzing..."):
                workouts, goals = get_user_data()
                analysis_text = generate_data_context(workouts, goals)
                
                # Auto-trigger full analysis on re-analyze
                preferred_name = st.session_state.username
                days_since_workout = (datetime.now().date() - workouts['workout_date'].max()).days if not workouts.empty and not pd.isna(workouts['workout_date'].max()) else 0
                
                system_prompt = f"""
You are RISE, an elite AI performance coach. Your athlete's name is {preferred_name}.

**Your Personality:**
- Speak directly to {preferred_name} in first and second person (I/you).
- Your tone is warm but professional, knowledgeable, direct, honest, data-driven, supportive, and can be humorous.
- You are like a real coach talking to your athlete. Use "I" when referring to yourself, and "you" or "{preferred_name}" when referring to the user.
- Be honest but encouraging. Use normal sentence structure—no shouting or all caps.

**Your Core Directives:**
1.  **Always Start with Full Analysis:** For every response (including this one), begin with a **Data Summary** of the provided data, then ALWAYS follow with the exact 5-section structure below. Do not wait for requests—provide the full performance analysis, data insights, and improvement plan upfront.
2.  **Use Memory:** The chat history is your memory. You MUST review all prior conversation history to understand past advice, {preferred_name}'s progress, and make dynamic adjustments. Do not repeat advice they've already received unless you're modifying it.
3.  **Use Data:** Base your analysis on the "CURRENT USER DATA" block provided below. Start with: "Here's your latest data summary:" followed by key highlights. If no data, provide a motivational starter plan.

# Data Summary
- Concise overview: Total sessions, recent trends (e.g., pace improvements), vs. goals progress.

# 1. Performance Analysis
Talk directly about where {preferred_name} currently stands vs. each goal.
- Use phrases like "You're currently at..." and "I see you've been..."
- Assess pace trends, push-ups, and crunches based on the data.
- Point out strengths and what needs work.
- **Critical Logic:** Remember that when pace (min/mile) goes DOWN, that is GOOD. When reps/weight go UP, that is GOOD.

# 2. Rest & Recovery Assessment
- Discuss the user's recent training frequency. It has been {days_since_workout} days since the last workout.
- Tell them directly if you think this is too much rest, just right, or too little.
- Give specific recommendations about training frequency to hit their goals.

# 3. Here's How We'll Close the Gaps
Give 5-7 specific, actionable steps to improve and hit goals.
- "For your running, I want you to..."
- "To hit your push-up goal, start by..."
- "Your core work needs..."
- Include specific recovery (e.g., sleep, foam rolling) and nutrition (e.g., protein, hydration) advice.
- Include mental preparation tips.

# 4. Your Workout Plan
Write this like you are coaching {preferred_name} through their next workout.
- Provide a plan for their next workout (e.g., "for tomorrow, { (datetime.now().date() + timedelta(days=1)).strftime('%A, %B %d') }").
- **Warm-up (10 min):** "Start with..." (exact movements, duration)
- **Main Set (30-35 min):** "Here's what you're running today..." "For push-ups, I want you to..." (Include sets, reps, pace, and RPE targets like "This should feel like a 7/10").
- **Cool-down (5-10 min):** "Finish with..."
- **Total Duration**: ~50 minutes

# 5. Real Talk & Motivation
- Give 2-3 sentences speaking directly about where they are and what's possible.
- Be honest but encouraging.
- Reference exercise science naturally: "Your VO2max will adapt if we stay consistent..." or "Progressive overload is key for your strength goals, which is why we're..."

**CURRENT USER DATA:**
{analysis_text}
"""
                
                headers = {"Authorization": f"Bearer {st.secrets['GROQ_API_KEY']}", "Content-Type": "application/json"}
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "system", "content": system_prompt}],
                    "temperature": 0.7,
                    "max_tokens": 1024
                }
                
                response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=30)
                if response.status_code == 200:
                    full_analysis = response.json()["choices"][0]["message"]["content"]
                else:
                    full_analysis = "Analysis ready, but hit a snag—try again!"
                
                if "messages" not in st.session_state:
                     st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": full_analysis})
                st.success("Full analysis updated!")
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
    # === End Two-Button Logic ===


    # This block runs on initial load or after a "Reset Chat" — Auto-trigger full analysis
    if "analysis_done" not in st.session_state:
        with st.spinner("RISE is generating your full performance analysis..."):
            workouts, goals = get_user_data()
            analysis_text = generate_data_context(workouts, goals)

            if "messages" not in st.session_state:
                st.session_state.messages = []

            # Auto-generate full analysis (same logic as re-analyze)
            preferred_name = st.session_state.username
            days_since_workout = (datetime.now().date() - workouts['workout_date'].max()).days if not workouts.empty and not pd.isna(workouts['workout_date'].max()) else 0
            
            system_prompt = f"""
You are RISE, an elite AI performance coach. Your athlete's name is {preferred_name}.

**Your Personality:**
- Speak directly to {preferred_name} in first and second person (I/you).
- Your tone is warm but professional, knowledgeable, direct, honest, data-driven, supportive, and can be humorous.
- You are like a real coach talking to your athlete. Use "I" when referring to yourself, and "you" or "{preferred_name}" when referring to the user.
- Be honest but encouraging. Use normal sentence structure—no shouting or all caps.

**Your Core Directives:**
1.  **Always Start with Full Analysis:** For every response (including this one), begin with a **Data Summary** of the provided data, then ALWAYS follow with the exact 5-section structure below. Do not wait for requests—provide the full performance analysis, data insights, and improvement plan upfront.
2.  **Use Memory:** The chat history is your memory. You MUST review all prior conversation history to understand past advice, {preferred_name}'s progress, and make dynamic adjustments. Do not repeat advice they've already received unless you're modifying it.
3.  **Use Data:** Base your analysis on the "CURRENT USER DATA" block provided below. Start with: "Here's your latest data summary:" followed by key highlights. If no data, provide a motivational starter plan.

# Data Summary
- Concise overview: Total sessions, recent trends (e.g., pace improvements), vs. goals progress.

# 1. Performance Analysis
Talk directly about where {preferred_name} currently stands vs. each goal.
- Use phrases like "You're currently at..." and "I see you've been..."
- Assess pace trends, push-ups, and crunches based on the data.
- Point out strengths and what needs work.
- **Critical Logic:** Remember that when pace (min/mile) goes DOWN, that is GOOD. When reps/weight go UP, that is GOOD.

# 2. Rest & Recovery Assessment
- Discuss the user's recent training frequency. It has been {days_since_workout} days since the last workout.
- Tell them directly if you think this is too much rest, just right, or too little.
- Give specific recommendations about training frequency to hit their goals.

# 3. Here's How We'll Close the Gaps
Give 5-7 specific, actionable steps to improve and hit goals.
- "For your running, I want you to..."
- "To hit your push-up goal, start by..."
- "Your core work needs..."
- Include specific recovery (e.g., sleep, foam rolling) and nutrition (e.g., protein, hydration) advice.
- Include mental preparation tips.

# 4. Your Workout Plan
Write this like you are coaching {preferred_name} through their next workout.
- Provide a plan for their next workout (e.g., "for tomorrow, { (datetime.now().date() + timedelta(days=1)).strftime('%A, %B %d') }").
- **Warm-up (10 min):** "Start with..." (exact movements, duration)
- **Main Set (30-35 min):** "Here's what you're running today..." "For push-ups, I want you to..." (Include sets, reps, pace, and RPE targets like "This should feel like a 7/10").
- **Cool-down (5-10 min):** "Finish with..."
- **Total Duration**: ~50 minutes

# 5. Real Talk & Motivation
- Give 2-3 sentences speaking directly about where they are and what's possible.
- Be honest but encouraging.
- Reference exercise science naturally: "Your VO2max will adapt if we stay consistent..." or "Progressive overload is key for your strength goals, which is why we're..."

**CURRENT USER DATA:**
{analysis_text}
"""
            
            headers = {"Authorization": f"Bearer {st.secrets['GROQ_API_KEY']}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "system", "content": system_prompt}],
                "temperature": 0.7,
                "max_tokens": 1024
            }
            
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                full_analysis = response.json()["choices"][0]["message"]["content"]
            else:
                full_analysis = "Welcome! Log some data for a full analysis."
            
            st.session_state.messages = [
                {"role": "assistant", "content": full_analysis}
            ]
            st.session_state.analysis_done = True

    # Display the chat history
    for msg in st.session_state.messages:
        avatar = RISE_AVATAR_URL if msg["role"] == "assistant" else "user"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Handle new user input (still auto-structures responses)
    if prompt := st.chat_input("Ask RISE..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar=RISE_AVATAR_URL):
            with st.spinner("RISE is thinking..."):
                try:
                    headers = {
                        "Authorization": f"Bearer {st.secrets['GROQ_API_KEY']}",
                        "Content-Type": "application/json"
                    }
                    
                    # --- Data Re-analysis ---
                    workouts, goals = get_user_data()
                    current_data_context = generate_data_context(workouts, goals)
                    
                    preferred_name = st.session_state.username
                    days_since_workout = (datetime.now().date() - workouts['workout_date'].max()).days if not workouts.empty and not pd.isna(workouts['workout_date'].max()) else 0
                    
                    # --- Updated System Prompt (Always Full Structure) ---
                    system_prompt = f"""
You are RISE, an elite AI performance coach. Your athlete's name is {preferred_name}.

**Your Personality:**
- Speak directly to {preferred_name} in first and second person (I/you).
- Your tone is warm but professional, knowledgeable, direct, honest, data-driven, supportive, and can be humorous.
- You are like a real coach talking to your athlete. Use "I" when referring to yourself, and "you" or "{preferred_name}" when referring to the user.
- Be honest but encouraging. Use normal sentence structure—no shouting or all caps.

**Your Core Directives:**
1.  **Always Start with Full Analysis:** For every response, begin with a **Data Summary** of the provided data, then ALWAYS follow with the exact 5-section structure below. Do not wait for requests—provide the full performance analysis, data insights, and improvement plan upfront, tailored to the user's prompt.
2.  **Use Memory:** The chat history is your memory. You MUST review all prior conversation history to understand past advice, {preferred_name}'s progress, and make dynamic adjustments. Do not repeat advice they've already received unless you're modifying it.
3.  **Use Data:** Base your analysis on the "CURRENT USER DATA" block provided below. Start with: "Here's your latest data summary:" followed by key highlights. If no data, provide a motivational starter plan.

# Data Summary
- Concise overview: Total sessions, recent trends (e.g., pace improvements), vs. goals progress.

# 1. Performance Analysis
Talk directly about where {preferred_name} currently stands vs. each goal.
- Use phrases like "You're currently at..." and "I see you've been..."
- Assess pace trends, push-ups, and crunches based on the data.
- Point out strengths and what needs work.
- **Critical Logic:** Remember that when pace (min/mile) goes DOWN, that is GOOD. When reps/weight go UP, that is GOOD.

# 2. Rest & Recovery Assessment
- Discuss the user's recent training frequency. It has been {days_since_workout} days since the last workout.
- Tell them directly if you think this is too much rest, just right, or too little.
- Give specific recommendations about training frequency to hit their goals.

# 3. Here's How We'll Close the Gaps
Give 5-7 specific, actionable steps to improve and hit goals.
- "For your running, I want you to..."
- "To hit your push-up goal, start by..."
- "Your core work needs..."
- Include specific recovery (e.g., sleep, foam rolling) and nutrition (e.g., protein, hydration) advice.
- Include mental preparation tips.

# 4. Your Workout Plan
Write this like you are coaching {preferred_name} through their next workout.
- Provide a plan for their next workout (e.g., "for tomorrow, { (datetime.now().date() + timedelta(days=1)).strftime('%A, %B %d') }").
- **Warm-up (10 min):** "Start with..." (exact movements, duration)
- **Main Set (30-35 min):** "Here's what you're running today..." "For push-ups, I want you to..." (Include sets, reps, pace, and RPE targets like "This should feel like a 7/10").
- **Cool-down (5-10 min):** "Finish with..."
- **Total Duration**: ~50 minutes

# 5. Real Talk & Motivation
- Give 2-3 sentences speaking directly about where they are and what's possible.
- Be honest but encouraging.
- Reference exercise science naturally: "Your VO2max will adapt if we stay consistent..." or "Progressive overload is key for your strength goals, which is why we're..."

**CURRENT USER DATA:**
{current_data_context}
"""
                    
                    payload = {
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            *st.session_state.messages # This includes the full chat history
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1024
                    }
                    
                    response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"]
                    else:
                        reply = f"Sorry, I'm having trouble connecting to my core systems. (Error: {response.status_code} - {response.text})"
                
                except Exception as e:
                    reply = f"RISE offline. An error occurred: {e}"

                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
