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

# ——— HIDE AUTO NAV ———
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none !important;}
    .block-container {padding-top: 2rem !important;}
</style>
""", unsafe_allow_html=True)

# ——— LOGIN CHECK ———
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.error("Please log in from the home page.")
    st.stop()

# ——— SIDEBAR ———
st.sidebar.success(f"**{st.session_state.username}**")
st.sidebar.page_link("app.py", label="Home")
st.sidebar.page_link("pages/01_Dashboard.py", label="Dashboard")
st.sidebar.page_link("pages/02_AI_Coach.py", label="SOPHIA Coach")
if st.sidebar.button("Logout", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ——— DB ———
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

# ——— DATA PROCESSING ———
df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)
valid_df = df[df['distance'] > 0].copy()
valid_df['cum_miles'] = valid_df['distance'].cumsum()

# Helper: MM:SS format
def format_pace(minutes):
    if pd.isna(minutes):
        return "N/A"
    mins = int(minutes)
    secs = int((minutes - mins) * 60)
    return f"{mins}:{secs:02d}"

valid_df['pace_display'] = valid_df['pace_min_per_mi'].apply(format_pace)

# ——— GOALS FROM SESSION STATE ———
GOAL_RUN_MIN = st.session_state.get("goal_run_min", 18.0)
GOAL_PUSH = st.session_state.get("goal_push", 45)
GOAL_CRUNCH = st.session_state.get("goal_crunch", 45)

# ——— DASHBOARD TITLE ———
st.markdown("## Progress Dashboard")

# ——— TABS ———
tab1, tab2, tab3 = st.tabs(["Pace", "Push-ups", "Crunches"])

# ——— TAB 1: PACE (FULLY RESTORED) ———
with tab1:
    fig = px.scatter(valid_df, x='date', y='pace_min_per_mi', title="Pace Trend")
    
    # Green trend line
    fig.add_scatter(x=valid_df['date'], y=valid_df['pace_min_per_mi'],
                    mode='lines', line=dict(color='green', width=2),
                    name='Your Pace', showlegend=True)
    
    # Yellow average
    avg_pace = valid_df['pace_min_per_mi'].mean()
    fig.add_hline(y=avg_pace, line_dash="solid", line_color="gold",
                  line_width=2, annotation_text=f"Avg: {format_pace(avg_pace)}",
                  annotation_position="right")
    
    # Red goal line
    goal_pace_per_mile = GOAL_RUN_MIN / 2
    fig.add_hline(y=goal_pace_per_mile, line_dash="dash", line_color="red",
                  line_width=2, annotation_text=f"Goal: {format_pace(goal_pace_per_mile)}",
                  annotation_position="right")
    
    # Custom Y-axis in MM:SS
    y_min = valid_df['pace_min_per_mi'].min()
    y_max = valid_df['pace_min_per_mi'].max()
    y_range_min = int(y_min) - 1
    y_range_max = int(y_max) + 2
    tick_vals = [i/2 for i in range(y_range_min*2, y_range_max*2 + 1)]
    tick_labels = [format_pace(v) for v in tick_vals]
    
    fig.update_yaxes(
        tickmode='array',
        tickvals=tick_vals,
        ticktext=tick_labels,
        title="Pace (min:sec per mile)"
    )
    
    # Custom hover
    fig.update_traces(
        hovertemplate='<b>Date:</b> %{x|%b %d}<br><b>Pace:</b> %{customdata[0]}<extra></extra>',
        customdata=valid_df[['pace_display']].values
    )
    
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

# ——— TAB 2: PUSH-UPS (FULLY RESTORED) ———
with tab2:
    fig = px.scatter(df, x='date', y='pushups', title="Push-ups")
    
    fig.add_scatter(x=df['date'], y=df['pushups'],
                    mode='lines', line=dict(color='green', width=2),
                    name='Your Push-ups', showlegend=True)
    
    avg_pushups = df['pushups'].mean()
    fig.add_hline(y=avg_pushups, line_dash="solid", line_color="gold",
                  line_width=2, annotation_text=f"Avg: {avg_pushups:.0f}",
                  annotation_position="right")
    
    fig.add_hline(y=GOAL_PUSH, line_dash="dash", line_color="red",
                  line_width=2, annotation_text=f"Goal: {GOAL_PUSH}",
                  annotation_position="right")
    
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

# ——— TAB 3: CRUNCHES (FULLY RESTORED) ———
with tab3:
    fig = px.scatter(df, x='date', y='crunches', title="Crunches")
    
    fig.add_scatter(x=df['date'], y=df['crunches'],
                    mode='lines', line=dict(color='green', width=2),
                    name='Your Crunches', showlegend=True)
    
    avg_crunches = df['crunches'].mean()
    fig.add_hline(y=avg_crunches, line_dash="solid", line_color="gold",
                  line_width=2, annotation_text=f"Avg: {avg_crunches:.0f}",
                  annotation_position="right")
    
    fig.add_hline(y=GOAL_CRUNCH, line_dash="dash", line_color="red",
                  line_width=2, annotation_text=f"Goal: {GOAL_CRUNCH}",
                  annotation_position="right")
    
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)
