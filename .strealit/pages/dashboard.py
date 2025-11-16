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

def extract_pace_goal(goal_text):
    """Extract distance and time from goal text like 'Run 2 miles in 18 min'"""
    text = goal_text.lower()
    dist_match = re.search(r'(\d*\.?\d+)\s*(mile|mi)', text)
    time_match = re.search(r'(\d+)\s*(min|minute|mins)', text)
    distance = float(dist_match.group(1)) if dist_match else None
    total_time = float(time_match.group(1)) if time_match else None
    if distance and total_time and distance > 0:
        return distance, total_time
    return None, None

def calculate_pace_min_mi(distance_mi, total_time_min):
    return total_time_min / distance_mi if distance_mi and distance_mi > 0 else None

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

        # Goals
        cur.execute("""
            SELECT exercise, metric_type, target_value, target_date
            FROM goals
            WHERE user_id = %s AND target_date >= %s
            ORDER BY target_date
        """, (st.session_state.user_id, date.today()))
        goals_rows = cur.fetchall()
        df_goals = pd.DataFrame(goals_rows, columns=['exercise', 'metric_type', 'target_value', 'target_date'])

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
        cardio_keywords = ['run', 'running', 'walk', 'walking', 'elliptical', 'rowing', 'swim', 'cycling', 'bike']
        def classify(ex): return 'Cardio' if pd.notna(ex) and any(k in ex.lower() for k in cardio_keywords) else 'Weight'
        df_workouts['type'] = df_workouts['exercise'].apply(classify)

        for col in ['weight_lbs', 'time_min', 'distance_mi', 'sets', 'reps', 'rest_min']:
            df_workouts[col] = pd.to_numeric(df_workouts[col], errors='coerce')
        df_workouts['distance_mi'] = df_workouts['distance_mi'].replace(0, np.nan)

        # PACE: ((time + rest) * reps) / distance
        df_workouts['total_effort'] = (df_workouts['time_min'] + df_workouts['rest_min']) * df_workouts['reps']
        df_workouts['pace_min_mi'] = df_workouts['total_effort'] / df_workouts['distance_mi']

        # Format
        for col in ['weight_lbs', 'time_min', 'distance_mi', 'pace_min_mi']:
            df_workouts[col] = df_workouts[col].round(2).astype(str).replace(['0.0', '0', 'nan', 'inf', '<NA>'], '-')
        for col in ['sets', 'reps', 'rest_min']:
            df_workouts[col] = df_workouts[col].astype(str).replace(['0.0', '0', 'nan', '<NA>'], '-')

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
            with st.container(border=True):
                st.markdown(f"#### {sess['workout_date'].strftime('%b %d, %Y')}")
                st.caption(f"**Duration:** {sess['duration_min']} min | **Notes:** {sess['notes']}")
                ex = df_workouts[df_workouts['workout_id'] == sess['workout_id']]
                cardio = ex[ex['type'] == 'Cardio']
                weight = ex[ex['type'] == 'Weight']
                
                if not cardio.empty:
                    st.markdown("##### Cardio")
                    st.dataframe(cardio[['exercise', 'time_min', 'distance_mi', 'pace_min_mi']].rename(
                        columns={'time_min':'Time','distance_mi':'Dist','pace_min_mi':'Pace'}), width='stretch')
                if not weight.empty:
                    st.markdown("##### Weight")
                    st.dataframe(weight[['exercise','weight_lbs','sets','reps','rest_min']].rename(
                        columns={'weight_lbs':'Wt','sets':'S','reps':'R','rest_min':'Rest'}), width='stretch')
                
                e1, e2 = st.columns(2)
                with e1:
                    if st.button("✏️ Edit", key=f"edit_{sess['workout_id']}"):
                        st.session_state.editing_workout_id = sess['workout_id']
                        st.rerun()
                with e2:
                    # Two-step delete: first click shows confirmation, second click deletes
                    if st.session_state.confirm_delete_id == sess['workout_id']:
                        if st.button("⚠️ Confirm Delete", key=f"confirm_{sess['workout_id']}", type="primary"):
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
                        if st.button("🗑️ Delete", key=f"del_{sess['workout_id']}", type="secondary"):
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
                edit_dur = st.number_input("Duration (min)", min_value=1, value=int(sess['duration_min']))

                conn_e = get_conn()
                cur_e = conn_e.cursor()
                cur_e.execute("SELECT id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi, notes FROM workout_exercises WHERE workout_id=%s", (wid,))
                rows = cur_e.fetchall()
                ex_list = []
                for r in rows:
                    eid, name, sets, reps, wt, tm, rst, dist, nts = r
                    cat, sub, base = parse_exercise_name(name)
                    ex_list.append({ 
                        "id": eid, "category": cat, "sub_category": sub, "base_name": base,
                        "sets": int(sets or 1), "reps": int(reps or 1), "weight_lbs": float(wt or 0),
                        "time_min": float(tm or 0), "rest_min": float(rst or 0), "distance_mi": float(dist or 0),
                        "notes": nts or "", "prev_cat": cat 
                    })
                if not ex_list:
                    ex_list = [{
                        "id": None, "category": None, "sub_category": None, "base_name": "", 
                        "sets": 1, "reps": 1, "weight_lbs": 0.0, "time_min": 0.0, 
                        "rest_min": 1.5, "distance_mi": 0.0, "notes": "", "prev_cat": None
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
                        elif ex["category"] == "Weights":
                            ex["sets"] = st.number_input("Sets", min_value=1, value=ex["sets"], key=f"esets_{i}")
                            ex["reps"] = st.number_input("Reps", min_value=1, value=ex["reps"], key=f"ereps_{i}")
                            ex["weight_lbs"] = st.number_input("Weight", min_value=0.0, value=ex["weight_lbs"], step=5.0, key=f"ewt_{i}")
                            ex["rest_min"] = st.number_input("Rest", min_value=0.0, value=ex["rest_min"], step=0.5, key=f"erest_{i}")
                            ex["time_min"] = ex["distance_mi"] = 0.0
                        elif ex["category"] == "Free-Text":
                            ex["base_name"] = st.text_area("Description", value=ex["base_name"], key=f"efree_{i}")
                            ex["time_min"] = st.number_input("Time", min_value=0.0, value=ex["time_min"], step=0.5, key=f"efreet_{i}")
                            ex["sets"]=ex["reps"]=1
                            ex["weight_lbs"]=ex["distance_mi"]=ex["rest_min"]=0.0

                        with st.expander("Details", expanded=True):
                            sel_name = st.selectbox("Name", options=[""] + past_exercises,
                                index=0 if not ex.get("base_name") else (past_exercises.index(ex["base_name"])+1 if ex["base_name"] in past_exercises else 0),
                                key=f"ename_{i}")
                            final_name = st.text_input("or type", value=sel_name or ex["base_name"], key=f"ename_txt_{i}")
                            full_ex = f"{ex['category']} - {ex['sub_category']}: {final_name}".strip(": ") if ex['category'] and ex['sub_category'] else final_name
                            ex["base_name"] = final_name
                            ex["exercise"] = full_ex
                            ex["notes"] = st.text_area("Notes", value=ex["notes"], key=f"enotes_{i}")

                        st.divider()

                a1, a2 = st.columns(2)
                with a1:
                    if st.button("Add Exercise", key=f"add_e_{i}"):
                        ex_list.append({
                            "id": None, "category": None, "sub_category": None, "base_name": "", 
                            "sets": 1, "reps": 1, "weight_lbs": 0.0, "time_min": 0.0, 
                            "rest_min": 1.5, "distance_mi": 0.0, "notes": "", "prev_cat": None
                        })
                        st.rerun()
                with a2:
                    if len(ex_list) > 1 and st.button("Remove Last", key=f"rem_e_{i}"):
                        ex_list.pop()
                        st.rerun()

                s1, s2 = st.columns(2)
                with s1:
                    if st.button("💾 Save Changes", type="primary", width='stretch'):
                        try:
                            cu = conn_e.cursor()
                            cu.execute("UPDATE workouts SET workout_date=%s, notes=%s, duration_min=%s WHERE id=%s AND user_id=%s",
                                (edit_date, edit_notes, edit_dur, wid, st.session_state.user_id))
                            cu.execute("DELETE FROM workout_exercises WHERE workout_id=%s", (wid,))
                            for ex in ex_list:
                                if ex["exercise"].strip() and ex["category"]:
                                    cu.execute("INSERT INTO workout_exercises (workout_id, exercise, sets, reps, weight_lbs, time_min, rest_min, distance_mi, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                        (wid, ex["exercise"], ex["sets"], ex["reps"], ex["weight_lbs"], ex["time_min"], ex["rest_min"], ex["distance_mi"], ex["notes"]))
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
                    if st.button("❌ Cancel", width='stretch'):
                        st.session_state.editing_workout_id = None
                        st.rerun()

            st.markdown("---")

        # PACE CHART
        if not df_workouts[df_workouts['type'] == 'Cardio'].empty:
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

    # GOALS SECTION
    st.subheader("Active Goals")
    if not df_goals.empty:
        progress = {}

        for _, row in df_goals.iterrows():
            exercise = row['exercise']
            target = float(row['target_value'])
            
            # Try to auto-detect pace goal
            dist, total_time = extract_pace_goal(exercise)
            if dist and total_time:
                goal_pace = calculate_pace_min_mi(dist, total_time)
                matches = df_workouts[
                    df_workouts['exercise'].str.contains(re.escape(exercise.split(" in ")[0]), case=False, na=False) &
                    (df_workouts['type'] == 'Cardio')
                ]
                if not matches.empty:
                    paces = pd.to_numeric(matches['pace_min_mi'], errors='coerce')
                    current_pace = paces.min()
                else:
                    current_pace = None

                if current_pace and current_pace > 0:
                    pct = min((goal_pace / current_pace) * 100, 100)  # Cap at 100%
                    status = "Exceeding!" if pct >= 100 else "On Track"
                else:
                    pct = 0
                    status = "No data"

                progress[exercise] = {
                    'type': 'pace',
                    'goal_pace': goal_pace,
                    'current_pace': current_pace,
                    'pct': pct,
                    'status': status
                }
            else:
                # Non-pace goal
                metric = row['metric_type']
                matches = df_workouts[df_workouts['exercise'].str.contains(exercise, case=False, na=False)]
                current = 0
                if not matches.empty and metric in matches.columns:
                    current = pd.to_numeric(matches[metric], errors='coerce').max()
                pct = min((current / target) * 100, 100) if target > 0 else 0  # Cap at 100%
                progress[exercise] = {
                    'type': 'value',
                    'current': current,
                    'target': target,
                    'pct': pct
                }

        # Display
        for _, row in df_goals.iterrows():
            exercise = row['exercise']
            data = progress.get(exercise, {'type': 'value', 'pct': 0})
            days_left = (pd.to_datetime(row['target_date']) - pd.Timestamp.today()).days

            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{exercise}**")
                    if data['type'] == 'pace':
                        st.caption(f"Goal: {data['goal_pace']:.2f} min/mi | Best: {data['current_pace']:.2f} min/mi" if data['current_pace'] else f"Goal: {data['goal_pace']:.2f} min/mi | No data")
                    else:
                        st.caption(f"Goal: {data['target']} {row['metric_type'].replace('_', ' ')} | Current: {data['current']}")
                    st.progress(data['pct'] / 100)
                with c2:
                    st.markdown(f"**{data['pct']:.1f}%**")
                    if data['type'] == 'pace':
                        st.caption(data['status'])
                    st.caption(f"{days_left} days left")
    else:
        st.info("No active goals.")
