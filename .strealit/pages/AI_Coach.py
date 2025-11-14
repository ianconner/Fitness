# pages/ai_coach.py
import streamlit as st
import requests
from datetime import datetime

def main():
    st.markdown("## SOPHIA Coach")
    st.markdown("Your AI-powered personal trainer — **Smart Optimized Performance Health Intelligence Assistant**")

    # ——— COACH PROMPT ———
    system_prompt = """
    You are SOPHIA, an elite AI fitness coach. Be direct, motivational, and data-driven.
    Use the user's workout history and goals to give hyper-personalized advice.
    Speak like a pro coach: confident, concise, no fluff, use humor when appropriate, do not be bossy nor commanding, you want the best out of the user.
    """

    # ——— GET USER DATA ———
    def get_user_context():
        try:
            import pandas as pd
            from sqlalchemy import create_engine
            engine = create_engine(st.secrets["POSTGRES_URL"])
            
            workouts = pd.read_sql(
                "SELECT workout_date, notes, duration_min FROM workouts WHERE user_id=%s ORDER BY workout_date DESC LIMIT 5",
                engine, params=(st.session_state.user_id,)
            ).to_dict('records')
            
            goals = pd.read_sql(
                "SELECT exercise, metric_type, target_value, target_date FROM goals WHERE user_id=%s AND target_date >= CURRENT_DATE",
                engine, params=(st.session_state.user_id,)
            ).to_dict('records')
            
            return {
                "recent_workouts": workouts,
                "active_goals": goals,
                "current_date": datetime.now().strftime("%Y-%m-%d")
            }
        except:
            return {"recent_workouts": [], "active_goals": [], "current_date": datetime.now().strftime("%Y-%m-%d")}

    context = get_user_context()

    # ——— CHAT HISTORY ———
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": f"Welcome back, {st.session_state.username}. I'm SOPHIA — your AI coach. Let's crush your goals.\n\nAsk me anything: training, recovery, programming, nutrition."}
        ]

    # ——— DISPLAY CHAT ———
    for msg in st.session_state.messages[1:]:  # Skip system
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar="https://api.dicebear.com/7.x/bottts/svg?seed=SOPHIA"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("user"):
                st.markdown(msg["content"])

    # ——— USER INPUT ———
    if prompt := st.chat_input("Ask SOPHIA anything..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # ——— CALL GROK API (or fallback) ———
        with st.chat_message("assistant", avatar="https://api.dicebear.com/7.x/bottts/svg?seed=SOPHIA"):
            with st.spinner("SOPHIA is thinking..."):
                try:
                    # Replace with your actual API key and endpoint
                    headers = {
                        "Authorization": f"Bearer {st.secrets['GROK_API_KEY']}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": "grok-beta",
                        "messages": [
                            {"role": "system", "content": system_prompt + f"\n\nUSER CONTEXT: {context}"},
                            *[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[1:]]
                        ],
                        "temperature": 0.7,
                        "max_tokens": 500
                    }
                    
                    response = requests.post("https://api.x.ai/v1/chat/completions", json=payload, headers=headers, timeout=30)
                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"]
                    else:
                        reply = "I'm having trouble connecting right now. Try again in a moment."
                except:
                    reply = "SOPHIA is offline for maintenance. Check back soon."

                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
