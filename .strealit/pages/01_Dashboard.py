# pages/01_Dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2
from datetime import datetime

# ——— PAGE CONFIG ———
st.set_page_config(
    page_title="Dashboard - SOPHIA",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ——— HIDE STREAMLIT'S AUTO NAV ———
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none !important;}
    .block-container {padding-top: 2rem !important;}
</style>
""", unsafe_allow_html=True)

# ——— CHECK LOGIN ———
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.error("Please log in from the home page.")
    st.stop()

# ——— SIDEBAR NAVIGATION ———
st.sidebar.success(f"**{st.session_state.get('preferred_name', st.session_state.username)}**")

st.sidebar.page_link("app.py", label="🏠 Home")
st.sidebar.page_link("pages/01_Dashboard.py", label="📊 Dashboard")
st.sidebar.page_link("pages/02_AI_Coach.py", label="🤖 SOPHIA Coach")

if st.sidebar.button("Logout", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.switch_page("app.py")

# ---------- DB ----------
def get_db_connection():
    return psycopg2.connect(st.secrets["POSTGRES_URL"])

def get_logs():
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT * FROM logs WHERE user_id = %s ORDER BY date",
        conn, params=(st.session_state.user_id,)
    )
    conn.close()
    return df

df = get_logs()
if df.empty:
    st.warning("No logs yet.")
    st.stop()

# Helper functions
def format_pace(minutes):
    """Convert decimal minutes to MM:SS format"""
    if pd.isna(minutes):
        return "N/A"
    mins = int(minutes)
    secs = int((minutes - mins) * 60)
    return f"{mins}:{secs:02d}"

df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)
valid_df = df[df['distance'] > 0].copy()
valid_df['cum_miles'] = valid_df['distance'].cumsum()
valid_df['pace_display'] = valid_df['pace_min_per_mi'].apply(format_pace)

# ---------- GOAL SETTINGS (Persistent) ----------
st.sidebar.markdown("## Goal Settings")

def load_user_goals():
    conn = psycopg2.connect(st.secrets["POSTGRES_URL"])
    cur = conn.cursor()
    cur.execute("""
        SELECT goal_run_min, goal_push, goal_crunch, goal_date
        FROM users WHERE id = %s
    """, (st.session_state.user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and any(row):
        return {
            "goal_run_min": row[0] or 18.0,
            "goal_push": row[1] or 45,
            "goal_crunch": row[2] or 45,
            "goal_date": row[3] or datetime.now().date()
        }
    return {"goal_run_min": 18.0, "goal_push": 45, "goal_crunch": 45, "goal_date": datetime.now().date()}

if "goal_run_min" not in st.session_state:
    saved = load_user_goals()
    st.session_state.goal_run_min = saved["goal_run_min"]
    st.session_state.goal_push = saved["goal_push"]
    st.session_state.goal_crunch = saved["goal_crunch"]
    st.session_state.goal_date = saved["goal_date"]

goal_run_min = st.sidebar.number_input("2-Mile Target (min)", value=st.session_state.goal_run_min, step=0.1)
goal_date    = st.sidebar.date_input("Target Date", value=st.session_state.goal_date)
goal_push    = st.sidebar.number_input("Push-ups", value=st.session_state.goal_push, step=1)
goal_crunch  = st.sidebar.number_input("Crunches", value=st.session_state.goal_crunch, step=1)

if st.sidebar.button("Save Goals"):
    conn = psycopg2.connect(st.secrets["POSTGRES_URL"])
    cur = conn.cursor()
    cur.execute("""
        UPDATE users SET goal_run_min = %s, goal_push = %s, goal_crunch = %s, goal_date = %s
        WHERE id = %s
    """, (goal_run_min, goal_push, goal_crunch, goal_date, st.session_state.user_id))
    conn.commit()
    cur.close()
    conn.close()

    st.session_state.goal_run_min = goal_run_min
    st.session_state.goal_push = goal_push
    st.session_state.goal_crunch = goal_crunch
    st.session_state.goal_date = goal_date
    st.success("Goals saved and synced to your account!")

GOAL_RUN_MIN = st.session_state.goal_run_min
GOAL_DATE    = st.session_state.goal_date
GOAL_PUSH    = st.session_state.goal_push
GOAL_CRUNCH  = st.session_state.goal_crunch

# ---------- PROJECTIONS ----------
last_5 = valid_df.head(5)
avg_pace = last_5['pace_min_per_mi'].mean() if not last_5.empty else pd.NA
proj_2mi = avg_pace * 2 if pd.notna(avg_pace) else pd.NA
proj_str = (f"{int(proj_2mi):02d}:{int((proj_2mi % 1)*60):02d}"
            if pd.notna(proj_2mi) else "N/A")

st.title("Progress Dashboard")

col1, col2, col3 = st.columns(3)

# ---- 2-Mile ----
with col1:
    st.metric("Projected 2-Mile", proj_str,
              f"Last {len(last_5)}: {avg_pace:.2f} min/mi" if pd.notna(avg_pace) else "")
    if pd.notna(proj_2mi) and proj_2mi <= GOAL_RUN_MIN:
        st.markdown("<div style='background:#4CAF50;height:8px;'></div>", unsafe_allow_html=True)
    elif pd.notna(proj_2mi) and proj_2mi <= 20:
        st.markdown("<div style='background:#FFC107;height:8px;'></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='background:#F44336;height:8px;'></div>", unsafe_allow_html=True)

# ---- Push-ups ----
with col2:
    latest_p = df['pushups'].iloc[-1]
    delta_p  = latest_p - GOAL_PUSH
    st.metric("Push-ups", latest_p,
              f"{delta_p:+} vs goal" if delta_p != 0 else "Goal met")
    st.markdown("<div style='background:#4CAF50;height:8px;'></div>"
                if latest_p >= GOAL_PUSH else
                "<div style='background:#F44336;height:8px;'></div>", unsafe_allow_html=True)

# ---- Crunches ----
with col3:
    latest_c = df['crunches'].iloc[-1]
    delta_c  = latest_c - GOAL_CRUNCH
    st.metric("Crunches", latest_c,
              f"{delta_c:+} vs goal" if delta_c != 0 else "Goal met")
    st.markdown("<div style='background:#4CAF50;height:8px;'></div>"
                if latest_c >= GOAL_CRUNCH else
                "<div style='background:#F44336;height:8px;'></div>", unsafe_allow_html=True)

# ---------- TRENDS ----------
st.markdown("---")
st.subheader("Trends")
colA, colB = st.columns(2)
with colA:
    st.metric("Total Miles", f"{valid_df['cum_miles'].iloc[-1]:.1f}")
with colB:
    days_to_goal = (GOAL_DATE - datetime.now().date()).days
    st.metric("Days to Goal", f"{days_to_goal}")

tab1, tab2, tab3 = st.tabs(["Pace", "Push-ups", "Crunches"])

# ---------- TAB 1: PACE TREND ----------
with tab1:
    fig = px.scatter(valid_df, x='date', y='pace_min_per_mi', title="Pace Trend (per mile)")
    fig.add_scatter(x=valid_df['date'], y=valid_df['pace_min_per_mi'], 
                    mode='lines', line=dict(color='green', width=2),
                    name='Your Pace', showlegend=True)
    
    avg_pace_all = valid_df['pace_min_per_mi'].mean()
    fig.add_hline(y=avg_pace_all, line_dash="solid", line_color="gold", 
                  line_width=2, annotation_text=f"Average: {format_pace(avg_pace_all)}")
    fig.add_scatter(x=[None], y=[None], mode='lines', 
                    line=dict(color='gold', width=2), name='Average', showlegend=True)
    
    goal_pace_per_mile = GOAL_RUN_MIN / 2
    fig.add_hline(y=goal_pace_per_mile, line_dash="dash", line_color="red", 
                  line_width=2, annotation_text=f"Goal: {format_pace(goal_pace_per_mile)}")
    fig.add_scatter(x=[None], y=[None], mode='lines', 
                    line=dict(color='red', width=2, dash='dash'), name='Goal', showlegend=True)
    
    # Custom Y-axis ticks
    y_min = valid_df['pace_min_per_mi'].min()
    y_max = valid_df['pace_min_per_mi'].max()
    y_range_min = int(y_min) - 1
    y_range_max = int(y_max) + 2
    
    tick_vals = []
    tick_labels = []
    for i in range(y_range_min * 2, y_range_max * 2 + 1):
        val = i / 2.0
        tick_vals.append(val)
        tick_labels.append(format_pace(val))
    
    fig.update_yaxes(
        tickmode='array',
        tickvals=tick_vals,
        ticktext=tick_labels,
        title="Pace (min:sec per mile)"
    )
    
    # Hover display
    fig.update_traces(
        hovertemplate='<b>Date:</b> %{x|%b %d}<br><b>Pace:</b> ' + 
                      valid_df['pace_display'] + '<extra></extra>',
        selector=dict(mode='markers')
    )
    
    fig.update_xaxes(
        tickformat="%b %d",
        tickmode='array',
        tickvals=valid_df['date'].unique(),
        ticktext=[d.strftime("%b %d") for d in valid_df['date'].unique()]
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            title=dict(text="Legend")
        )
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- TAB 2: PUSHUPS TREND ----------
with tab2:
    fig = px.scatter(df, x='date', y='pushups', title="Push-ups")
    fig.add_scatter(x=df['date'], y=df['pushups'], 
                    mode='lines', line=dict(color='green', width=2),
                    name='Your Push-ups', showlegend=True)
    avg_pushups = df['pushups'].mean()
    fig.add_hline(y=avg_pushups, line_dash="solid", line_color="gold", 
                  line_width=2, annotation_text=f"Average: {avg_pushups:.0f}")
    fig.add_hline(y=GOAL_PUSH, line_dash="dash", line_color="red", 
                  line_width=2, annotation_text=f"Goal: {GOAL_PUSH}")
    fig.update_xaxes(
        tickformat="%b %d",
        tickmode='array',
        tickvals=df['date'].unique(),
        ticktext=[d.strftime("%b %d") for d in df['date'].unique()]
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            title=dict(text="Legend")
        )
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- TAB 3: CRUNCHES TREND ----------
with tab3:
    fig = px.scatter(df, x='date', y='crunches', title="Crunches")
    fig.add_scatter(x=df['date'], y=df['crunches'], 
                    mode='lines', line=dict(color='green', width=2),
                    name='Your Crunches', showlegend=True)
    avg_crunches = df['crunches'].mean()
    fig.add_hline(y=avg_crunches, line_dash="solid", line_color="gold", 
                  line_width=2, annotation_text=f"Average: {avg_crunches:.0f}")
    fig.add_hline(y=GOAL_CRUNCH, line_dash="dash", line_color="red", 
                  line_width=2, annotation_text=f"Goal: {GOAL_CRUNCH}")
    fig.update_xaxes(
        tickformat="%b %d",
        tickmode='array',
        tickvals=df['date'].unique(),
        ticktext=[d.strftime("%b %d") for d in df['date'].unique()]
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            title=dict(text="Legend")
        )
    )
    st.plotly_chart(fig, use_container_width=True)
