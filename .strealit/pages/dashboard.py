# pages/dashboard.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import date
import numpy as np
import plotly.express as px
import re

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def parse_exercise_name(exercise_str):
    if not exercise_str or not isinstance(exercise_str, str):
        return None, None, exercise_str or ""
    parts = [p.strip() for p in exercise_str.split(":")]
    name = parts[-1]
    if " - " in exercise_str:
        cat_sub = exercise_str.split(" - ", 1)[0]
        if " - " in cat_sub:
            cat, sub = cat_sub.split(" - ", 1)
            return cat, sub, name
        else:
            return cat_sub, None, name
    return None, None, name

def format_time_mmss(decimal_minutes):
    """Convert decimal minutes to MM:SS format"""
    if pd.isna(decimal_minutes) or decimal_minutes <= 0:
        return "0:00"
    minutes = int(decimal_minutes)
    seconds = int((decimal_minutes - minutes) * 60)
    return f"{minutes}:{seconds:02d}"

def format_pace_mmss(pace_decimal):
    """Convert decimal pace to MM:SS per mile format"""
    if pd.isna(pace_decimal) or pace_decimal <= 0:
        return "-"
    minutes = int(pace_decimal)
    seconds = int((pace_decimal - minutes) * 60)
    return f"{minutes}:{seconds:02d}"

def extract_pace_goal(goal_text):
    """Extract distance and time from goal text"""
    text = goal_text.lower()
    dist_match = re.search(r'(\d*\.?\d+)\s*(mile|mi)', text)
    time_match = re.search(r'(\d+):(\d+)', text)
    if not time_match:
        time_match = re.search(r'(\d+)\s*(min|minute|mins)', text)
    
    distance = float(dist_match.group(1)) if dist_match else None
    
    if time_match:
        if ':' in time_match.group(0):
            minutes = int(time_match.group(1))
            seconds = int(time_match.group(2))
            total_time = minutes + (seconds / 60)
        else:
            total_time = float(time_match.group(1))
    else:
        total_time = None
    
    if distance and total_time and distance > 0:
        return distance, total_time
    return None, None

def main():
    st.markdown("## Dashboard")
    st.markdown("Your fitness journey at a glance.")

    conn = get_conn()
    cur = conn.cursor()

    try:
        # Workouts
        cur.execute("""
            SELECT w.id, w.workout_date, w.duration_min, w.notes,
                   we.id as ex_id, we.exercise, we.sets, we.reps, we.weight_lbs,
                   we.time_min, we.distance_mi, we.rest_min, we.notes as ex_notes
            FROM workouts w
            LEFT JOIN workout_exercises we ON w.id = we.workout_id
            WHERE w.user_id = %s
            ORDER BY w.workout_date DESC
        """, (st.session_state.user_id,))
        rows = cur.fetchall()
        df_workouts = pd.DataFrame(rows, columns=[
            'workout_id', 'workout_date', 'duration_min', 'notes', 'ex_id',
            'exercise', 'sets', 'reps', 'weight_lbs', 'time_min',
            'distance_mi', 'rest_min', 'ex_notes'
        ])
        
        # Classify workouts immediately after loading
        if not df_workouts.empty:
            cardio_keywords = ['run', 'running', 'walk', 'walking', 'elliptical', 'rowing', 'swim', 'cycling', 'bike', 'cardio']
            def classify(ex): return 'Cardio' if pd.notna(ex) and any(k in ex.lower() for k in cardio_keywords) else 'Weight'
            df_workouts['type'] = df_workouts['exercise'].apply(classify)

        # Past exercises for autocomplete
        cur.execute("""
            SELECT DISTINCT we.exercise
            FROM workout_exercises we
            JOIN workouts w ON we.workout_id = w.id
            WHERE w.user_id = %s AND we.exercise IS NOT NULL
        """, (st.session_state.user_id,))
        past_exercises = [row[0] for row in cur.fetchall()]

    finally:
        conn.close()

    # DATA PREP
    if not df_workouts.empty:
        # Type column already created above, now do numeric conversions
        for col in ['weight_lbs', 'time_min', 'distance_mi', 'sets', 'reps', 'rest_min']:
            df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
        df_workouts['distance_mi_numeric'] = df_workouts['distance_mi'].replace(0, np.nan)

        # PACE: (time * reps) + (rest * (reps - 1)) / distance
        # We handle missing rest by filling with 0
        df_workouts['rest_min_filled'] = df_workouts['rest_min'].fillna(0)
        df_workouts['reps_filled'] = df_workouts['reps'].fillna(1)
        
        # FIX: Correct total effort formula to only include rest BETWEEN sets/reps
        df_workouts['total_effort'] = (df_workouts['time_min'] * df_workouts['reps_filled']) + \
                                      (df_workouts['rest_min_filled'] * (df_workouts['reps_filled'] - 1).clip(lower=0))
                                      
        df_workouts['pace_min_mi'] = df_workouts['total_effort'] / df_workouts['distance_mi_numeric']

        # Format for display - keep numeric for calculations, create formatted columns
        df_workouts['time_display'] = df_workouts['time_min'].apply(format_time_mmss)
        df_workouts['pace_display'] = df_workouts['pace_min_mi'].apply(format_pace_mmss)
        
        # Format other columns for display
        df_workouts['weight_lbs_display'] = df_workouts['weight_lbs'].round(2).astype(str).replace(['0.0', '0', 'nan', 'inf', '<NA>'], '-')
        df_workouts['distance_mi_display'] = df_workouts['distance_mi'].round(2).astype(str).replace(['0.0', '0', 'nan', 'inf', '<NA>'], '-')
        for col in ['sets', 'reps', 'rest_min']:
            df_workouts[f'{col}_display'] = df_workouts[col].astype(str).replace(['0.0', '0', 'nan', '<NA>'], '-')

        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1: 
            st.metric("Total Workouts", len(df_workouts.drop_duplicates('workout_id')))
        with col2: 
            total_duration = pd.to_numeric(df_workouts['duration_min'], errors='coerce').sum()
            st.metric("Total Time", f"{int(total_duration)} min")
        with col3:
            valid_durations = df_workouts.groupby('workout_date')['duration_min'].first()
            valid_durations = pd.to_numeric(valid_durations, errors='coerce').dropna()
            avg_duration = valid_durations.mean() if not valid_durations.empty else 0
            st.metric("Avg Duration", f"{int(avg_duration)} min")

        # Recent Workouts
        st.subheader("Recent Workouts")
        sessions = df_workouts[['workout_id', 'workout_date', 'duration_min', 'notes']].drop_duplicates().sort_values('workout_date', ascending=False).head(5)

        # Initialize delete confirmation state
        if 'confirm_delete_id' not in st.session_state:
            st.session_state.confirm_delete_id = None

        for idx, sess in sessions.iterrows():
            # Get exercises for this workout
            ex = df_workouts[df_workouts['workout_id'] == sess['workout_id']]
            cardio = ex[ex['type'] == 'Cardio']
            weight = ex[ex['type'] == 'Weight']
            
            # Build condensed summary
            summary_parts = []
            
            # Cardio summary
            if not cardio.empty:
                cardio_items = []
                for _, row in cardio.iterrows():
                    ex_name = row['exercise'].split(': ')[-1] if ': ' in row['exercise'] else row['exercise']
                    parts = []
                    if not pd.isna(row['distance_mi']) and row['distance_mi'] > 0:
                        parts.append(f"{row['distance_mi']:.1f}mi")
                    if not pd.isna(row['time_min']) and row['time_min'] > 0:
                        # FIX: Apply correct total time formula for display: (Time * Reps) + (Rest * (Reps-1))
                        reps_val = row['reps'] if row['reps'] > 0 else 1
                        rest_val = row['rest_min'] if not pd.isna(row['rest_min']) else 0
                        
                        total_time = (row['time_min'] * reps_val) + (rest_val * max(0, reps_val - 1))
                        parts.append(format_time_mmss(total_time))
                        
                        if reps_val > 1:
                            parts.append(f"({int(reps_val)} intervals)")
                    cardio_items.append(f"{ex_name} ({', '.join(parts)})" if parts else ex_name)
                if cardio_items:
                    summary_parts.append(f"🏃 {' • '.join(cardio_items)}")
            
            # Weights summary
            if not weight.empty:
                weight_items = []
                for _, row in weight.iterrows():
                    ex_name = row['exercise'].split(': ')[-1] if ': ' in row['exercise'] else row['exercise']
                    parts = []
                    if not pd.isna(row['sets']) and not pd.isna(row['reps']):
                        parts.append(f"{int(row['sets'])}×{int(row['reps'])}")
                    if not pd.isna(row['weight_lbs']) and row['weight_lbs'] > 0:
                        parts.append(f"{row['weight_lbs']:.0f}lbs")
                    weight_items.append(f"{ex_name} ({', '.join(parts)})" if parts else ex_name)
                if weight_items:
                    summary_parts.append(f"💪 {' • '.join(weight_items)}")
            
            with st.container(border=True):
                # Single line layout: Date | Summary | Duration | Actions
                col1, col2, col3, col4 = st.columns([2, 5, 1, 1])
                
                with col1:
                    st.markdown(f"**{sess['workout_date'].strftime('%b %d')}**")
                
                with col2:
                    if summary_parts:
                        st.markdown(f"*{' | '.join(summary_parts)}*")
                    else:
                        st.markdown("*No exercises logged*")
                
                with col3:
                    st.markdown(f"⏱️ {sess['duration_min']}m")
                
                with col4:
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("✏️", key=f"edit_{sess['workout_id']}", help="Edit", use_container_width=True):
                            st.session_state.editing_workout_id = sess['workout_id']
                            st.rerun()
                    with btn_col2:
                        if st.session_state.confirm_delete_id == sess['workout_id']:
                            if st.button("⚠️", key=f"confirm_{sess['workout_id']}", type="primary", help="Confirm", use_container_width=True):
                                cdel = get_conn()
                                curdel = cdel.cursor()
                                try:
                                    curdel.execute("DELETE FROM workout_exercises WHERE workout_id=%s",(sess['workout_id'],))
                                    curdel.execute("DELETE FROM workouts WHERE id=%s AND user_id=%s",(sess['workout_id'], st.session_state.user_id))
                                    cdel.commit()
                                    st.session_state.confirm_delete_id = None
                                    st.success("Deleted!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                                finally:
                                    curdel.close()
                                    cdel.close()
                        else:
                            if st.button("🗑️", key=f"del_{sess['workout_id']}", type="secondary", help="Delete", use_container_width=True):
                                st.session_state.confirm_delete_id = sess['workout_id']
                                st.rerun()

        # EDIT MODE - Place immediately after Recent Workouts
        if st.session_state.get("editing_workout_id"):
            wid = st.session_state.editing_workout_id
            sess = sessions[sessions['workout_id']==wid].iloc[0]
            
            st.markdown("---")
            st.subheader(f"✏️ Editing Workout: {sess['workout_date'].strftime('%b %d, %Y')}")
            
            with st.container(border=True):
                edit_date = st.date_input("Date", value=sess['workout_date'])
                edit_notes = st.text_area("Notes", value=sess['notes'])
                # FIX: Handle 0 duration by using max(1, value)
                edit_dur = st.number_input("Duration (min)", min_value=1, value=max(1, int(sess['duration_min'])))

                conn_e = get_conn()
                cur_e = conn_e.cursor()
                cur_e.execute("SELECT id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi, notes, goal_id FROM workout_exercises WHERE workout_id=%s", (wid,))
                rows = cur_e.fetchall()
                
                # Fetch active goals for linking
                cur_e.execute("""
                    SELECT id, exercise, metric_type, target_value, target_date 
                    FROM goals 
                    WHERE user_id = %s AND target_date >= %s
                    ORDER BY target_date
                """, (st.session_state.user_id, date.today()))
                active_goals = cur_e.fetchall()
                
                ex_list = []
                for r in rows:
                    eid, name, sets, reps, wt, tm, rst, dist, nts, gid = r
                    cat, sub, base = parse_exercise_name(name)
                    ex_list.append({ 
                        "id": eid, "category": cat, "sub_category": sub, "base_name": base,
                        "sets": int(sets or 1), "reps": int(reps or 1), "weight_lbs": float(wt or 0),
                        "time_min": float(tm or 0), "rest_min": float(rst or 0), "distance_mi": float(dist or 0),
                        "notes": nts or "", "prev_cat": cat, "goal_id": gid
                    })
                if not ex_list:
                    ex_list = [{
                        "id": None, "category": None, "sub_category": None, "base_name": "", 
                        "sets": 1, "reps": 1, "weight_lbs": 0.0, "time_min": 0.0, 
                        "rest_min": 1.5, "distance_mi": 0.0, "notes": "", "prev_cat": None, "goal_id": None
                    }]

                for i, ex in enumerate(ex_list):
                    with st.container(border=True):
                        st.markdown(f"**Exercise {i+1}**")
                        cat_opts = ["", "Cardio", "Weights", "Free-Text"]
                        cat_idx = cat_opts.index(ex["category"]) if ex["category"] in cat_opts else 0
                        sel_cat = st.selectbox("Category", cat_opts, index=cat_idx, key=f"ecat_{i}")
                        if ex.get("prev_cat") != sel_cat:
                            ex["sub_category"] = None
                            ex["prev_cat"] = sel_cat
                        ex["category"] = sel_cat

                        sub = ""
                        if ex["category"] == "Cardio":
                            opts = ["Running","Walking","Elliptical","Other"]
                            idx = opts.index(ex["sub_category"]) if ex["sub_category"] in opts else 0
                            sub = st.selectbox("Sub-Category", opts, index=idx, key=f"esub_{i}")
                        elif ex["category"] == "Weights":
                            opts = ["Free-Weights","Machine","Body-Weights"]
                            idx = opts.index(ex["sub_category"]) if ex["sub_category"] in opts else 0
                            sub = st.selectbox("Sub-Category", opts, index=idx, key=f"esub_{i}")
                        ex["sub_category"] = sub

                        if ex["category"] == "Cardio":
                            ex["reps"] = st.number_input("Reps", min_value=1, value=ex["reps"], key=f"ereps_{i}")
                            if ex["reps"] > 1:
                                ex["rest_min"] = st.number_input("Rest (min)", min_value=0.0, value=ex["rest_min"], step=0.5, key=f"erest_{i}")
                            c_t, c_d = st.columns(2)
                            with c_t: 
                                ex["time_min"] = st.number_input("Time", min_value=0.0, value=ex["time_min"], step=0.5, key=f"etime_{i}")
                            with c_d: 
                                ex["distance_mi"] = st.number_input("Distance", min_value=0.0, value=ex["distance_mi"], step=0.1, key=f"edist_{i}")
                            tot = (ex["time_min"] + ex["rest_min"]) * ex["reps"]
                            pace = tot / ex["distance_mi"] if ex["distance_mi"] > 0 else 0
                            st.caption(f"**Pace: {pace:.2f} min/mi**" if ex["distance_mi"] > 0 else "**Pace: -**")
                            ex["sets"] = 1
                            ex["weight_lbs"] = 0.0
                            
                            # Compact single-line for name and goal
                            col_name, col_goal = st.columns([2, 1])
                            with col_name:
                                sel_name = st.selectbox("Exercise", options=[""] + past_exercises,
                                    index=0 if not ex.get("base_name") else (past_exercises.index(ex["base_name"])+1 if ex["base_name"] in past_exercises else 0),
                                    key=f"ename_{i}")
                                final_name = sel_name if sel_name else ex["base_name"]
                            with col_goal:
                                # GOAL LINKING for Cardio
                                if active_goals:
                                    relevant_goals = [g for g in active_goals if 'cardio' in g[1].lower() or 'run' in g[1].lower() or 'walk' in g[1].lower()]
                                    if relevant_goals:
                                        goal_options = ["No Goal"] + [f"{g[1].split(':')[-1].strip()}" for g in relevant_goals]
                                        current_goal_idx = 0
                                        if ex.get("goal_id"):
                                            for idx, g in enumerate(relevant_goals):
                                                if g[0] == ex["goal_id"]:
                                                    current_goal_idx = idx + 1
                                                    break
                                        selected_goal_idx = st.selectbox("🎯 Goal", range(len(goal_options)),
                                            format_func=lambda idx: goal_options[idx], index=current_goal_idx, key=f"egoal_{i}")
                                        ex["goal_id"] = relevant_goals[selected_goal_idx - 1][0] if selected_goal_idx > 0 else None
                            
                            full_ex = f"{ex['category']} - {ex['sub_category']}: {final_name}".strip(": ") if ex['category'] and ex['sub_category'] else final_name
                            ex["base_name"] = final_name
                            ex["exercise"] = full_ex
                            ex["notes"] = st.text_input("Notes", value=ex.get("notes", ""), key=f"enotes_{i}")
                            
                        elif ex["category"] == "Weights":
                            ex["sets"] = st.number_input("Sets", min_value=1, value=ex["sets"], key=f"esets_{i}")
                            ex["reps"] = st.number_input("Reps", min_value=1, value=ex["reps"], key=f"ereps_{i}")
                            ex["weight_lbs"] = st.number_input("Weight", min_value=0.0, value=ex["weight_lbs"], step=5.0, key=f"ewt_{i}")
                            ex["rest_min"] = st.number_input("Rest", min_value=0.0, value=ex["rest_min"], step=0.5, key=f"erest_{i}")
                            ex["time_min"] = ex["distance_mi"] = 0.0
                            
                            # Compact single-line for name and goal
                            col_name, col_goal = st.columns([2, 1])
                            with col_name:
                                sel_name = st.selectbox("Exercise", options=[""] + past_exercises,
                                    index=0 if not ex.get("base_name") else (past_exercises.index(ex["base_name"])+1 if ex["base_name"] in past_exercises else 0),
                                    key=f"ename_{i}")
                                final_name = sel_name if sel_name else ex["base_name"]
                            with col_goal:
                                # GOAL LINKING for Weights
                                if active_goals:
                                    relevant_goals = [g for g in active_goals if 'weight' in g[1].lower() or final_name.lower() in g[1].lower()]
                                    if relevant_goals:
                                        goal_options = ["No Goal"] + [f"{g[1].split(':')[-1].strip()}" for g in relevant_goals]
                                        current_goal_idx = 0
                                        if ex.get("goal_id"):
                                            for idx, g in enumerate(relevant_goals):
                                                if g[0] == ex["goal_id"]:
                                                    current_goal_idx = idx + 1
                                                    break
                                        selected_goal_idx = st.selectbox("🎯 Goal", range(len(goal_options)),
                                            format_func=lambda idx: goal_options[idx], index=current_goal_idx, key=f"egoal_{i}")
                                        ex["goal_id"] = relevant_goals[selected_goal_idx - 1][0] if selected_goal_idx > 0 else None
                            
                            full_ex = f"{ex['category']} - {ex['sub_category']}: {final_name}".strip(": ") if ex['category'] and ex['sub_category'] else final_name
                            ex["base_name"] = final_name
                            ex["exercise"] = full_ex
                            ex["notes"] = st.text_input("Notes", value=ex.get("notes", ""), key=f"enotes_{i}")
                            
                        elif ex["category"] == "Free-Text":
                            ex["base_name"] = st.text_area("Description", value=ex["base_name"], key=f"efree_{i}")
                            ex["time_min"] = st.number_input("Time", min_value=0.0, value=ex["time_min"], step=0.5, key=f"efreet_{i}")
                            ex["sets"]=ex["reps"]=1
                            ex["weight_lbs"]=ex["distance_mi"]=ex["rest_min"]=0.0
                            ex["exercise"] = ex["base_name"]
                            ex["goal_id"] = None

                        st.divider()

                a1, a2 = st.columns(2)
                with a1:
                    if st.button("Add Exercise", key=f"add_e_{i}"):
                        ex_list.append({
                            "id": None, "category": None, "sub_category": None, "base_name": "", 
                            "sets": 1, "reps": 1, "weight_lbs": 0.0, "time_min": 0.0, 
                            "rest_min": 1.5, "distance_mi": 0.0, "notes": "", "prev_cat": None, "goal_id": None
                        })
                        st.rerun()
                with a2:
                    if len(ex_list) > 1 and st.button("Remove Last", key=f"rem_e_{i}"):
                        ex_list.pop()
                        st.rerun()

                s1, s2 = st.columns(2)
                with s1:
                    if st.button("💾 Save Changes", type="primary", use_container_width=True):
                        try:
                            cu = conn_e.cursor()
                            cu.execute("UPDATE workouts SET workout_date=%s, notes=%s, duration_min=%s WHERE id=%s AND user_id=%s",
                                (edit_date, edit_notes, edit_dur, wid, st.session_state.user_id))
                            cu.execute("DELETE FROM workout_exercises WHERE workout_id=%s", (wid,))
                            for ex in ex_list:
                                if ex["exercise"].strip() and ex["category"]:
                                    cu.execute("INSERT INTO workout_exercises (workout_id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi, notes, goal_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                        (wid, ex["exercise"], ex["sets"], ex["reps"], ex["weight_lbs"], ex["time_min"], ex["rest_min"], ex["distance_mi"], ex["notes"], ex.get("goal_id")))
                            conn_e.commit()
                            st.success("Updated!")
                            st.session_state.editing_workout_id = None
                            st.rerun()
                        except Exception as e:
                            conn_e.rollback()
                            st.error(f"Error: {e}")
                        finally:
                            cur_e.close()
                            conn_e.close()
                with s2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.editing_workout_id = None
                        st.rerun()

            st.markdown("---")

        # PACE CHART
        if 'type' in df_workouts.columns and not df_workouts[df_workouts['type'] == 'Cardio'].empty:
            st.subheader("Pace Trend")
            pace_df = df_workouts[df_workouts['type'] == 'Cardio'].copy()
            pace_df['pace'] = pd.to_numeric(pace_df['pace_min_mi'], errors='coerce')
            pace_df = pace_df.dropna(subset=['pace'])
            if not pace_df.empty:
                pace_df['date_only'] = pd.to_datetime(pace_df['workout_date']).dt.date
                fig = px.line(
                    pace_df,
                    x='date_only',
                    y='pace',
                    color='exercise',
                    markers=True,
                    title="Pace (min/mi) Over Time"
                )
                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Pace (min/mi)",
                    xaxis=dict(tickformat="%b %d")
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No cardio pace data yet.")

    else:
        st.info("No workouts yet.")

    # GOALS SECTION - THE HUB
    st.subheader("Active Goals")
    
    # Load goals with linked workout data
    try:
        goals_query = """
            SELECT g.id, g.exercise, g.metric_type, g.target_value, g.target_date,
                   COUNT(we.id) as linked_workouts,
                   MAX(CASE 
                       WHEN g.metric_type = 'reps' THEN we.reps
                       WHEN g.metric_type = 'sets' THEN we.sets
                       WHEN g.metric_type = 'weight_lbs' THEN we.weight_lbs
                       WHEN g.metric_type = 'time_min' THEN we.time_min
                       WHEN g.metric_type = 'distance_mi' THEN we.distance_mi
                   END) as best_value
            FROM goals g
            LEFT JOIN workout_exercises we ON g.id = we.goal_id
            WHERE g.user_id = %s AND g.target_date >= %s
            GROUP BY g.id, g.exercise, g.metric_type, g.target_value, g.target_date
            ORDER BY g.target_date
        """
        conn_goals = get_conn()
        df_goals_linked = pd.read_sql(goals_query, conn_goals, params=(st.session_state.user_id, date.today()))
        conn_goals.close()
        
        if not df_goals_linked.empty:
            df_goals_linked['target_date'] = pd.to_datetime(df_goals_linked['target_date']).dt.date
            df_goals_linked['target_value'] = pd.to_numeric(df_goals_linked['target_value'], errors='coerce')
            df_goals_linked['best_value'] = pd.to_numeric(df_goals_linked['best_value'], errors='coerce')
    except Exception as e:
        st.error(f"Error loading goals: {e}")
        df_goals_linked = pd.DataFrame()
    
    if not df_goals_linked.empty:
        progress = {}

        for _, row in df_goals_linked.iterrows():
            exercise = row['exercise']
            metric = row['metric_type']
            target = float(row['target_value'])
            best = row['best_value'] if not pd.isna(row['best_value']) else 0
            linked_count = int(row['linked_workouts'])
            
            # Calculate progress percentage
            if best > 0 and target > 0:
                progress_pct = min((best / target) * 100, 100)
            else:
                progress_pct = 0
            
            progress[exercise] = {
                'type': 'value',
                'current': best,
                'target': target,
                'metric': metric,
                'pct': progress_pct,
                'linked_count': linked_count
            }

        # Display - Detailed Hub View
        for _, row in df_goals_linked.iterrows():
            exercise = row['exercise']
            data = progress.get(exercise, {'type': 'value', 'pct': 0})
            days_left = (row['target_date'] - date.today()).days

            with st.container(border=True):
                st.markdown(f"### {exercise}")
                
                # Standard goal display
                metric_unit = row['metric_type'].replace('_', ' ').title()
                st.markdown(f"**Goal:** {row['target_value']:.1f} {metric_unit}")
                
                if data.get('current', 0) > 0:
                    st.markdown(f"**Best:** {data['current']:.1f} {metric_unit} | **Linked Workouts:** {data.get('linked_count', 0)}")
                else:
                    st.markdown("**Best:** No linked workouts yet")
                
                status = "🟢 On Track" if days_left > 7 else "🟡 Urgent" if days_left >= 0 else "🔴 Overdue"
                st.caption(f"**Due:** {row['target_date'].strftime('%b %d, %Y')} ({days_left} days) | **Status:** {status}")
                
                progress_label = f"Progress: {data['pct']:.0f}%"
                if data['pct'] >= 100:
                    progress_label += " ⭐ ACHIEVED!"
                elif data['pct'] >= 75:
                    progress_label += " 🔥"
                st.caption(progress_label)
                st.progress(data['pct'] / 100)
    else:
        st.info("No active goals. Visit the Goals page to set your first target!")
