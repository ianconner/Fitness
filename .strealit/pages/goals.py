# pages/goals.py
import streamlit as st
from datetime import date, timedelta
import psycopg2
import pandas as pd

def get_conn():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def main():
    st.markdown("## Goals")
    st.markdown("Set **compound goals** like *Run 2 miles in 18 minutes*")

    # Initialize session state for form submission
    if 'goal_submitted' not in st.session_state:
        st.session_state.goal_submitted = False

    # ——— ADD GOAL FORM ———
    st.subheader("Add New Goal")
    
    exercise = st.text_input("Exercise", placeholder="Run, Squat, Push-up", key="goal_exercise")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        metric_type = st.selectbox("Metric", ["time_min", "reps", "weight_lbs", "distance_mi"], key="goal_metric")
    
    with col2:
        if metric_type == "time_min":
            distance = st.number_input("Distance (mi)", min_value=0.1, step=0.1, value=2.0, key="goal_distance")
        target_value = st.number_input("Target Value", min_value=0.1, step=0.1, value=10.0, key="goal_value")
    
    with col3:
        target_date = st.date_input("Target Date", value=date.today() + timedelta(days=30), key="goal_date")
    
    # Show calculated pace for time_min
    if metric_type == "time_min" and 'goal_distance' in st.session_state:
        pace = target_value / st.session_state.goal_distance
        st.caption(f"**Pace: {pace:.2f} min/mi**")

    # Button with callback
    def handle_submit():
        st.session_state.goal_submitted = True
    
    st.button("Add Goal", type="primary", use_container_width=True, on_click=handle_submit, key="add_goal_btn")

    # Process submission
    if st.session_state.goal_submitted:
        st.write("🔍 DEBUG: Button was clicked!")
        st.write(f"🔍 DEBUG: user_id = {st.session_state.user_id}")
        st.write(f"🔍 DEBUG: exercise = '{exercise}'")
        st.write(f"🔍 DEBUG: metric_type = {metric_type}")
        st.write(f"🔍 DEBUG: target_value = {target_value}")
        st.write(f"🔍 DEBUG: target_date = {target_date}")
        
        if not exercise.strip():
            st.error("Please enter an exercise name.")
            st.session_state.goal_submitted = False
        else:
            conn = get_conn()
            cur = conn.cursor()
            try:
                st.write("🔍 DEBUG: Attempting INSERT...")
                cur.execute(
                    "INSERT INTO goals (user_id, exercise, metric_type, target_value, target_date) VALUES (%s, %s, %s, %s, %s)",
                    (st.session_state.user_id, exercise, metric_type, target_value, target_date)
                )
                conn.commit()
                st.write("🔍 DEBUG: INSERT successful!")
                
                # Verify it's there
                cur.execute("SELECT COUNT(*) FROM goals WHERE user_id=%s", (st.session_state.user_id,))
                count = cur.fetchone()[0]
                st.write(f"🔍 DEBUG: Total goals for this user: {count}")
                
                st.success(f"✓ Goal added: {exercise}")
                st.session_state.goal_submitted = False
                st.balloons()
                
                st.warning("⚠️ DEBUG MODE: Auto-refresh disabled. Manually refresh to see updated goals.")
                
            except Exception as e:
                conn.rollback()
                st.error(f"❌ Database Error: {e}")
                import traceback
                st.code(traceback.format_exc())
                st.session_state.goal_submitted = False
            finally:
                cur.close()
                conn.close()

    st.divider()

    # ——— DISPLAY GOALS ———
    st.subheader("Active Goals")
    
    st.write(f"🔍 DEBUG: Fetching goals for user_id = {st.session_state.user_id}")
    
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, exercise, metric_type, target_value, target_date, created_at FROM goals WHERE user_id=%s ORDER BY target_date",
            (st.session_state.user_id,)
        )
        rows = cur.fetchall()
        
        st.write(f"🔍 DEBUG: Query returned {len(rows)} rows")
        
        if rows:
            st.write(f"🔍 DEBUG: Sample row: {rows[0]}")
            
            df = pd.DataFrame(rows, columns=['id', 'exercise', 'metric_type', 'target_value', 'target_date', 'created_at'])
            
            # Calculate days left
            df["target_date"] = pd.to_datetime(df["target_date"])
            df["Days Left"] = (df["target_date"] - pd.Timestamp(date.today())).dt.days
            df["Progress"] = df["Days Left"].apply(
                lambda x: "🟢 On Track" if x > 7 else "🟡 Urgent" if x >= 0 else "🔴 Overdue"
            )
            
            # Display
            for idx, row in df.iterrows():
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                    with col1:
                        st.markdown(f"**{row['exercise']}**")
                    with col2:
                        st.text(f"{row['metric_type']}: {row['target_value']}")
                    with col3:
                        st.text(f"Due: {row['target_date'].strftime('%Y-%m-%d')}")
                    with col4:
                        st.markdown(row['Progress'])
                    st.divider()
        else:
            st.info("No goals yet. Add one above!")
            
            # Check total goals in database
            cur.execute("SELECT COUNT(*) FROM goals")
            total = cur.fetchone()[0]
            st.write(f"🔍 DEBUG: Total goals in entire database: {total}")
            
    except Exception as e:
        st.error(f"❌ Error loading goals: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        cur.close()
        conn.close()
