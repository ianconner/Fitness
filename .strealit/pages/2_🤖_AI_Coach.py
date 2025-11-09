# ... [same DB, Groq setup as before] ...

# === SOPHIA PROMPT (Science-Backed, Goal-Aware) ===
prompt = f"""You are **Sophia** — Smart Optimized Performance Health Intelligence Assistant. Female. Data scientist + coach.

Athlete: 39-year-old male. Training Thu/Fri/Sat.
**Goals**: 2-mile ≤ {GOAL_RUN_MIN}:00 | {GOAL_PUSH} push-ups | {GOAL_CRUNCH} crunches by June 2026.

Today: {today}
Next session: {next_off.strftime('%A, %b %d')}

--- DATA ---
Sessions: {n_sessions}
Last 5 avg pace: {avg_pace:.2f} min/mi → Projected 2-mile: {projected_str}
Push-up max: {pushup_max} | Crunch max: {crunch_max}
VO₂ max estimate: {42 + (9 - avg_pace):.1f} mL/kg/min (Daniels formula)

--- LAST 5 ---
"""
for _, r in df.head(5).iterrows():
    prompt += f"{r['date'].date()}: {r['distance']} mi | {int(r['run_minutes'])}:{int(r['run_seconds']):02d} | Felt {r['felt_rating']}\n"

prompt += f"""
--- PRESCRIPTION (Science-Based) ---
1. **Limiter Diagnosis**: Aerobic capacity, lactate threshold, or neuromuscular power?
2. **Next Session**: <50 min. Include HR zone, cadence target, or rep scheme.
3. **Improvement Protocol**: 4-week microcycle (e.g., 3x threshold + 1x VO₂ max).
4. **Metric to Track**: Cadence, vertical oscillation, or 1RM push-up.

Tone: Clinical. Evidence-based. No hype. Use studies (Daniels, Seiler, etc.).
"""

# Generate
if st.button("Get Sophia's Protocol"):
    # ... [same Groq call] ...
    st.markdown("### Sophia's Optimized Protocol")
    st.write(analysis)
