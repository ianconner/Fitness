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
    /* Hide Streamlit's default page navigation menu */
    [data-testid="stSidebarNav"] {display: none !important;}
    
    /* Reduce top padding */
    .block-container {padding-top: 2rem !important;}
</style>
""", unsafe_allow_html=True)

# ——— CHECK LOGIN ———
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.error("Please log in from the home page.")
    st.stop()

# ——— SIDEBAR NAVIGATION ———
st.sidebar.success(f"**{st.session_state.username}**")

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

# Helper function to format pace as MM:SS
def format_pace(minutes):
    """Convert decimal minutes to MM:SS format"""
    if pd.isna(minutes):
        return "N/A"
    mins = int(minutes)
    secs = int((minutes - mins) * 60)
    return f"{mins}:{secs:02d}"

# Helper function to convert MM:SS to decimal for plotting
def pace_to_decimal(minutes):
    """Keep decimal format for calculations"""
    return minutes

df['date'] = pd.to_datetime(df['date'])
df['run_time_min'] = df['run_minutes'] + df['run_seconds']/60
df['pace_min_per_mi'] = df['run_time_min'] / df['distance'].replace(0, pd.NA)
valid_df = df[df['distance'] > 0].copy()
valid_df['cum_miles'] = valid_df['distance'].cumsum()
valid_df['pace_display'] = valid_df['pace_min_per_mi'].apply(format_pace)

# ---------- GOAL SETTINGS ----------
st.sidebar.markdown("## Goal Settings")
goal_run_min = st.sidebar.number_input("2-Mile Target (min)", value=18.0, step=0.1)
goal_date   = st.sidebar.date_input("Target Date", value=datetime(2026, 6, 1).date())
goal_push   = st.sidebar.number_input("Push-ups", value=45, step=1)
goal_crunch = st.sidebar.number_input("Crunches", value=45, step=1)

if st.sidebar.button("Save Goals"):
    st.session_state.goal_run_min = goal_run_min
    st.session_state.goal_date   = goal_date
    st.session_state.goal_push    = goal_push
    st.session_state.goal_crunch  = goal_crunch
    st.success("Goals saved!")

GOAL_RUN_MIN = st.session_state.get("goal_run_min", 18.0)
GOAL_DATE    = st.session_state.get("goal_date",   datetime(2026, 6, 1).date())
GOAL_PUSH    = st.session_state.get("goal_push",   45)
GOAL_CRUNCH  = st.session_state.get("goal_crunch", 45)

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
              f"Last {len(last_5)}: {avg_pace:.2f} min/mi")
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
    days_to_goal = (GOAL_DATE - datetime.today().date()).days
    st.metric("Days to Goal", f"{days_to_goal}")

tab1, tab2, tab3 = st.tabs(["Pace", "Push-ups", "Crunches"])

with tab1:
    # Create pace trend chart
    fig = px.scatter(valid_df, x='date', y='pace_min_per_mi', title="Pace Trend (per mile)")
    
    # Add green line connecting the dots
    fig.add_scatter(x=valid_df['date'], y=valid_df['pace_min_per_mi'], 
                    mode='lines', line=dict(color='green', width=2),
                    name='Your Pace', showlegend=True)
    
    # Add yellow average line
    avg_pace_all = valid_df['pace_min_per_mi'].mean()
    fig.add_hline(y=avg_pace_all, line_dash="solid", line_color="gold", 
                  line_width=2, annotation_text=f"Average: {format_pace(avg_pace_all)}")
    fig.add_scatter(x=[None], y=[None], mode='lines', 
                    line=dict(color='gold', width=2), name='Average', showlegend=True)
    
    # Add red dashed goal line
    goal_pace_per_mile = GOAL_RUN_MIN / 2
    fig.add_hline(y=goal_pace_per_mile, line_dash="dash", line_color="red", 
                  line_width=2, annotation_text=f"Goal: {format_pace(goal_pace_per_mile)}")
    fig.add_scatter(x=[None], y=[None], mode='lines', 
                    line=dict(color='red', width=2, dash='dash'), name='Goal', showlegend=True)
    
    # Create custom tick values and labels in MM:SS format
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
    
    # Format y-axis to show MM:SS
    fig.update_yaxes(
        tickmode='array',
        tickvals=tick_vals,
        ticktext=tick_labels,
        title="Pace (min:sec per mile)"
    )
    
    # Custom hover to show MM:SS format
    fig.update_traces(
        hovertemplate='<b>Date:</b> %{x|%b %d}<br><b>Pace:</b> ' + 
                      valid_df['pace_display'] + '<extra></extra>',
        selector=dict(mode='markers')
    )
    
    fig.update_xaxes(tickformat="%b %d")
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

with tab2:
    # Create push-ups chart
    fig = px.scatter(df, x='date', y='pushups', title="Push-ups")
    
    # Add green line connecting the dots
    fig.add_scatter(x=df['date'], y=df['pushups'], 
                    mode='lines', line=dict(color='green', width=2),
                    name='Your Push-ups', showlegend=True)
    
    # Add yellow average line
    avg_pushups = df['pushups'].mean()
    fig.add_hline(y=avg_pushups, line_dash="solid", line_color="gold", 
                  line_width=2, annotation_text=f"Average: {avg_pushups:.0f}")
    fig.add_scatter(x=[None], y=[None], mode='lines', 
                    line=dict(color='gold', width=2), name='Average', showlegend=True)
    
    # Add red dashed goal line
    fig.add_hline(y=GOAL_PUSH, line_dash="dash", line_color="red", 
                  line_width=2, annotation_text=f"Goal: {GOAL_PUSH}")
    fig.add_scatter(x=[None], y=[None], mode='lines', 
                    line=dict(color='red', width=2, dash='dash'), name='Goal', showlegend=True)
    
    fig.update_xaxes(tickformat="%b %d")
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

with tab3:
    # Create crunches chart
    fig = px.scatter(df, x='date', y='crunches', title="Crunches")
    
    # Add green line connecting the dots
    fig.add_scatter(x=df['date'], y=df['crunches'], 
                    mode='lines', line=dict(color='green', width=2),
                    name='Your Crunches', showlegend=True)
    
    # Add yellow average line
    avg_crunches = df['crunches'].mean()
    fig.add_hline(y=avg_crunches, line_dash="solid", line_color="gold", 
                  line_width=2, annotation_text=f"Average: {avg_crunches:.0f}")
    fig.add_scatter(x=[None], y=[None], mode='lines', 
                    line=dict(color='gold', width=2), name='Average', showlegend=True)
    
    # Add red dashed goal line
    fig.add_hline(y=GOAL_CRUNCH, line_dash="dash", line_color="red", 
                  line_width=2, annotation_text=f"Goal: {GOAL_CRUNCH}")
    fig.add_scatter(x=[None], y=[None], mode='lines', 
                    line=dict(color='red', width=2, dash='dash'), name='Goal', showlegend=True)
    
    fig.update_xaxes(tickformat="%b %d")
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
