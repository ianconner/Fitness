# pages/02_Log_Workout.py
import streamlit as st
import psycopg2
import re
from datetime import date

# ——— DATABASE ———
def conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

# ——— AUTO-PARSER: FREE TEXT → STRUCTURED DATA ———
def parse_workout(text):
    exercises = []
    lines = [l.strip() for l in text.replace(';', '\n').split('\n') if l.strip()]
    
    for line in lines:
        line = line.strip('.')
        
        # 3 sets of 5 min run, 2 min rest
        interval = re.search(r'(\d+)\s*sets?\s+of\s+(\d+)\s*(min|minute)s?\s+(.+?)(?:,\s*(\d+)\s*(min|minute)s?\s+rest)?', line, re.I)
        if interval:
            sets, time_min, _, exercise, rest_min, _ = interval.groups()
            exercises.append({
                'exercise': exercise.strip().title(),
                'sets': int(sets),
                'time_min': int(time_min),
                'rest_min': int(rest_min) if rest_min else None
            })
            continue

        # Squat 200 lb x 10
        lift = re.search(r'(.+?)\s+(\d+)\s*(lb|lbs|pound|pounds)\s*[xX*]\s*(\d+)', line, re.I)
        if lift:
            exercise, weight, _, reps = lift.groups()
            exercises.append({
                'exercise': exercise.strip().title(),
                'weight_lbs': int(weight),
                'reps': int(reps)
            })
            continue

        # 20 push-ups
        reps_only = re.search(r'^(\d+)\s+(.+?)(?:s|es)?$', line, re.I)
        if reps_only and not any(k in line.lower() for k in ['min', 'lb', 'set', 'x']):
            reps, exercise = reps_only.groups()
            exercises.append({
                'exercise': exercise.strip().title(),
                'reps': int(reps)
            })
    return exercises

# ——— PAGE ———
st.set_page_config(page_title="Log Workout - SOPHIA", layout="wide")
st.title("Log Workout")

with st.form("log_form"):
    col1, col2 = st.columns(2)
    with col1:
        workout_date = st.date_input("Date", value=date.today())
    with col2:
        duration_min = st.number_input("Total Duration (min, optional)", min_value=0, step=1)
    
    notes = st.text_area(
        "Describe your workout (free text)",
        height=180,
        placeholder="Examples:\n• 3 sets of 5 min run, 2 min rest\n• Squat 200 lb x 10\n• 20 push-ups"
    )
    
    submitted = st.form_submit_button("Save & Parse", use_container_width=True)

    if submitted:
        if not notes.strip():
            st.error("Please describe your workout.")
        else:
            c = conn()
            cur = c.cursor()
            
            # Save raw workout
            cur.execute(
                """INSERT INTO workouts (user_id, workout_date, notes, duration_min)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (st.session_state.user_id, workout_date, notes, duration_min or None)
            )
            workout_id = cur.fetchone()[0]
            
            # Parse and save structured exercises
            parsed = parse_workout(notes)
            for ex in parsed:
                cur.execute(
                    """INSERT INTO workout_exercises
                       (workout_id, exercise, sets, reps, weight_lbs, time_min, rest_min)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (workout_id, ex['exercise'], ex.get('sets'), ex.get('reps'),
                     ex.get('weight_lbs'), ex.get('time_min'), ex.get('rest_min'))
                )
            
            c.commit()
            c.close()
            
            st.success("Workout logged & auto-parsed!")
            st.json(parsed, expanded=False)
            st.balloons()
