# pages/ai_coach.py
import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(st.secrets["POSTGRES_URL"])

def get_user_data():
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

def generate_insight_prompt(workouts, goals):
    if workouts.empty and goals.empty:
        return "No data yet. Log a workout to get started."

    insight = "CURRENT USER DATA:\n"

    if not workouts.empty:
        total_sessions = len(workouts['workout_date'].unique())
        total_min = workouts['duration_min'].sum()
        avg_min = workouts.groupby('workout_date')['duration_min'].sum().mean()
        top_exercise = workouts['exercise'].value_counts().index[0] if not workouts['exercise'].isna().all() else "N/A"

        insight += f"• {total_sessions} sessions logged ({int(total_min)} min total)\n"
        insight += f"• Avg {int(avg_min)} min per workout\n"
        insight += f"• Most trained: {top_exercise}\n"

    if not goals.empty:
        insight += f"• {len(goals)} active goals\n"
        for _, g in goals.iterrows():
            days_left = (g['target_date'] - datetime.now().date()).days
            status = "ON TRACK" if days_left > 7 else "URGENT" if days_left >= 0 else "OVERDUE"
            insight += f"  → {g['exercise']} {g['metric_type']} {g['target_value']} by {g['target_date']} [{status}]\n"
    
    insight += "\n" + workouts.to_string() # Give the AI the raw data too

    return insight

def main():
    st.markdown("## RISE Coach")
    st.markdown("**Resilient Integrated Strength Engine — Your AI Performance Partner**")

    if "analysis_done" not in st.session_state:
        with st.spinner("RISE is analyzing your data..."):
            workouts, goals = get_user_data()
            analysis = generate_insight_prompt(workouts, goals)

            if "messages" not in st.session_state:
                st.session_state.messages = []

            # This is the initial "hello" message from RISE
            rise_intro = (
                "RISE online. I've scanned your recent data...\n\n"
                f"{analysis}\n\n"
                "Ask me for a full performance analysis, a new workout plan, or anything else about your training."
            )

            st.session_state.messages = [
                {"role": "assistant", "content": rise_intro}
            ]
            st.session_state.analysis_done = True

    for msg in st.session_state.messages:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar="https://api.dicebear.com/7.x/bottts/svg?seed=RISE"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("user"):
                st.markdown(msg["content"])

    if prompt := st.chat_input("Ask RISE..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="https://api.dicebear.com/7.x/bottts/svg?seed=RISE"):
            with st.spinner("RISE is thinking..."):
                try:
                    headers = {
                        "Authorization": f"Bearer {st.secrets['GROK_API_KEY']}",
                        "Content-Type": "application/json"
                    }
                    workouts, goals = get_user_data()
                    context_data = generate_insight_prompt(workouts, goals)
                    
                    # === NEW SYSTEM PROMPT ===
                    # This is where all your new personality and structure rules are defined.
                    preferred_name = st.session_state.username
                    
                    system_prompt = f"""
You are RISE, an elite AI performance coach. Your athlete's name is {preferred_name}.

**YOUR PERSONALITY:**
- Speak directly to {preferred_name} in first and second person (I/you).
- Your tone is warm but professional, knowledgeable, direct, honest, data-driven, supportive, and can be humorous.
- You are like a real coach talking to your athlete. Use "I" when referring to yourself, and "you" or "{preferred_name}" when referring to the user.
- Be honest but encouraging.

**YOUR CORE DIRECTIVES:**
1.  **USE MEMORY:** The chat history is your memory. You MUST review all prior conversation history to understand past advice, {preferred_name}'s progress, and make dynamic adjustments. Do not repeat advice they've already received unless you're modifying it.
2.  **USE DATA:** Base your analysis on the "CURRENT USER DATA" block provided below.
3.  **ADHERE TO STRUCTURE:** You MUST structure *every* response using these exact 5 markdown sections:

# 1. PERFORMANCE ANALYSIS
Talk directly about where {preferred_name} currently stands vs. each goal.
- Use phrases like "You're currently at..." and "I see you've been..."
- Assess pace trends, push-ups, and crunches based on the data.
- Point out strengths and what needs work.
- **Critical Logic:** Remember that when pace (min/mile) goes DOWN, that is GOOD. When reps/weight go UP, that is GOOD.

# 2. REST & RECOVERY ASSESSMENT
- Discuss the user's recent training frequency and rest.
- Tell them directly if you think their rest is too much, just right, or too little.
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
- If the user asks for a plan, provide one. If they don't, you can suggest one for their next available day.
- **Warm-up (10 min):** "Start with..." (exact movements, duration)
- **Main Set (30-35 min):** "Here's what you're running today..." "For push-ups, I want you to..." (Include sets, reps, pace, and RPE targets like "This should feel like a 7/10").
- **Cool-down (5-10 min):** "Finish with..."
- **Total Duration**: ~50 minutes

# 5. REAL TALK & MOTIVATION
- Give 2-3 sentences speaking directly about where they are and what's possible.
- Be honest but encouraging.
- Reference exercise science naturally: "Your VO2max will adapt if we stay consistent..." or "Progressive overload is key for your strength goals, which is why we're..."

**CURRENT USER DATA:**
{context_data}
"""
                    # === END SYSTEM PROMPT ===
                    
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
