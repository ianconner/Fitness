# pages/ai_coach.py
import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine

# ——— DATABASE ENGINE ———
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

    insight = "SOPHIA ANALYSIS:\n"

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

    return insight

def main():
    st.markdown("## SOPHIA Coach")
    st.markdown("**Smart Optimized Performance Health Intelligence Assistant**")

    # ——— AUTO-ANALYSIS ON LOAD ———
    if "analysis_done" not in st.session_state:
        with st.spinner("SOPHIA is analyzing your data..."):
            workouts, goals = get_user_data()
            analysis = generate_insight_prompt(workouts, goals)

            if "messages" not in st.session_state:
                st.session_state.messages = []

            # Inject SOPHIA's first message
            sophia_intro = (
                "SOPHIA online. Analyzing your fitness DNA...\n\n"
                f"{analysis}\n\n"
                "I'm ready. Ask me anything — programming, recovery, PRs, form, nutrition."
            )

            st.session_state.messages = [
                {"role": "assistant", "content": sophia_intro}
            ]
            st.session_state.analysis_done = True

    # ——— CHAT DISPLAY ———
    for msg in st.session_state.messages:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar="https://api.dicebear.com/7.x/bottts/svg?seed=SOPHIA"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("user"):
                st.markdown(msg["content"])

    # ——— USER INPUT ———
    if prompt := st.chat_input("Ask SOPHIA..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="https://api.dicebear.com/7.x/bottts/svg?seed=SOPHIA"):
            with st.spinner("SOPHIA is thinking..."):
                try:
                    headers = {
                        "Authorization": f"Bearer {st.secrets['GROK_API_KEY']}",
                        "Content-Type": "application/json"
                    }
                    # Rebuild context
                    workouts, goals = get_user_data()
                    context = generate_insight_prompt(workouts, goals)

                    payload = {
                        "model": "grok-beta",
                        "messages": [
                            {"role": "system", "content": f"You are SOPHIA, elite AI coach. Use this data:\n{context}"},
                            *st.session_state.messages
                        ],
                        "temperature": 0.7,
                        "max_tokens": 500
                    }
                    response = requests.post("https://api.x.ai/v1/chat/completions", json=payload, headers=headers, timeout=30)
                    reply = response.json()["choices"][0]["message"]["content"] if response.status_code == 200 else "Connection error."
                except:
                    reply = "SOPHIA offline. Try again."

                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
