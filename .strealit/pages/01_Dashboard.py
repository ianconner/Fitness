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

# ——— SIDEBAR NAV ———
st.sidebar.success(f"**{st.session_state.username}**")
st.sidebar.page_link("app.py", label="Home")
st.sidebar.page_link("pages/01_Dashboard.py", label="Dashboard")
st.sidebar.page_link("pages/02_AI_Coach.py", label="SOPHIA Coach")
if st.sidebar.button("Logout", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ——— GOAL SETTINGS (SIDEBAR) ———
st.sidebar.markdown("## Goal Settings")
goal_run_min = st.sidebar.number_input("2-Mile Target (min)", value=st.session_state.get("goal_run_min", 18.0), step=0.1)
goal_date = st.sidebar.date_input("Target Date", value=st.session_state.get("goal_date", datetime(2026, 6, 1).date()))
goal_push = st.sidebar.number_input("Push-ups", value=st.session_state.get("goal_push", 45), step=1)
goal_crunch = st.sidebar.number_input("Crunches", value=st.session_state.get("goal_crunch", 45), step=1)

if st.sidebar.button("Save Goals"):
    st.session_state.goal_run_min = goal_run_min
    st.session_state.goal_date = goal_date
    st.session_state.goal_push = goal_push
    st.session_state.goal_crunch = goal_crunch
    st.success("Goals saved!")

# Use saved goals
GOAL_RUN_MIN = st.session_state.get("goal_run_min", 18.0)
GOAL_DATE = st.session_state.get("goal_date", datetime(2026, 6, 1).date())
GOAL_PUSH = st.session_state.get("goal_push", 45)
GOAL_CRUNCH = st.session_state.get("goal_crunch", 45)

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

# Cumulative push-ups and crunches
df['cum_pushups'] = df['pushups'].cumsum()
df['cum_crunches'] = df['crunches'].cumsum()

# Helper: MM:SS format
def format_pace(minutes):
    if pd.isna(minutes):
        return "N/A"
    mins = int(minutes)
    secs = int((minutes - mins) * 60)
    return f"{mins}:{secs:02d}"

valid_df['pace_display'] = valid_df['pace_min_per_mi'].apply(format_pace)

# ——— PROJECTIONS ———
last_5 = valid_df.head(5)
avg_pace = last_5['pace_min_per_mi'].mean() if not last_5.empty else pd.NA
proj_2mi = avg_pace * 2 if pd.notna(avg_pace) else pd.NA
proj_str = format_pace(proj_2mi) if pd.notna(proj_2mi) else "N/A"

# ——— DASHBOARD TITLE + METRICS ———
st.markdown("## Progress Dashboard")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Projected 2-Mile", proj_str,
              f"Last {len(last_5)}: {avg_pace:.2f} min/mi" if pd.notna(avg_pace) else "N/A")
    if pd.notna(proj_2mi):
        color = "#4CAF50" if proj_2mi <= GOAL_RUN_MIN else "#FFC107" if proj_2mi <= 20 else "#F44336"
        st.markdown(f"<div style='background:{color};height:8px;border-radius:2px;'></div>", unsafe_allow_html=True)

with col2:
    latest_p = df['pushups'].iloc[-1]
    total_p = df['cum_pushups'].iloc[-1]
    delta_p = latest_p - GOAL_PUSH
    st.metric("Push-ups", latest_p,
              f"{delta_p:+} vs goal | Cum: {int(total_p)}")
    st.markdown("<div style='background:#4CAF50;height:8px;border-radius:2px;'></div>"
                if latest_p >= GOAL_PUSH else
                "<div style='background:#F44336;height:8px;border-radius:2px;'></div>", unsafe_allow_html=True)

with col3:
    latest_c = df['crunches'].iloc[-1]
    total_c = df['cum_crunches'].iloc[-1]
    delta_c = latest_c - GOAL_CRUNCH
    st.metric("Crunches", latest_c,
              f"{delta_c:+} vs goal | Cum: {int(total_c)}")
    st.markdown("<div style='background:#4CAF50;height:8px;border-radius:2px;'></div>"
                if latest_c >= GOAL_CRUNCH else
                "<div style='background:#F44336;height:8px;border-radius:2px;'></div>", unsafe_allow_html=True)

# ——— SUMMARY METRICS ———
st.markdown("---")
st.subheader("Lifetime Totals")
colA, colB, colC = st.columns(3)
with colA:
    st.metric("Total Miles", f"{valid_df['cum_miles'].iloc[-1]:.1f}")
with colB:
    st.metric("Total Push-ups", f"{int(df['cum_pushups'].iloc[-1])}")
with colC:
    st.metric("Total Crunches", f"{int(df['cum_crunches'].iloc[-1])}")

st.markdown("---")
st.subheader("Trends")
colX, colY = st.columns(2)
with colX:
    st.metric("Days to Goal", f"{(GOAL_DATE - datetime.today().date()).days}")
with colY:
    st.write("")  # spacer

# ——— TABS ———
tab1, tab2, tab3 = st.tabs(["Pace", "Push-ups", "Crunches"])

# ——— TAB 1: PACE (WITH FULL LEGEND) ———
with tab1:
    fig = px.scatter(valid_df, x='date', y='pace_min_per_mi', title="Pace Trend (min/mi)")
    fig.add_scatter(x=valid_df['date'], y=valid_df['pace_min_per_mi'],
                    mode='lines', line=dict(color='green', width=2),
                    name='Your Pace Trend Line (Green)', showlegend=True)
    avg_pace_val = valid_df['pace_min_per_mi'].mean()
    fig.add_hline(y=avg_pace_val, line_dash="solid", line_color="gold",
                  line_width=2, annotation_text=f"Avg: {format_pace(avg_pace_val)}",
                  annotation_position="right")
    goal_pace = GOAL_RUN_MIN / 2
    fig.add_hline(y=goal_pace, line_dash="dash", line_color="red",
                  line_width=2, annotation_text=f"Goal: {format_pace(goal_pace)}",
                  annotation_position="right")

    # MM:SS Y-axis
    y_min = valid_df['pace_min_per_mi'].min()
    y_max = valid_df['pace_min_per_mi'].max()
    y_range_min = int(y_min) - 1
    y_range_max = int(y_max) + 2
    tick_vals = [i/2 for i in range(y_range_min*2, y_range_max*2 + 1)]
    tick_labels = [format_pace(v) for v in tick_vals]
    fig.update_yaxes(tickmode='array', tickvals=tick_vals, ticktext=tick_labels,
                     title="Pace (min:sec per mile)")

    # Custom hover
    fig.update_traces(
        hovertemplate='<b>Date:</b> %{x|%b %d}<br><b>Pace:</b> %{customdata[0]}<extra></extra>',
        customdata=valid_df[['pace_display']].values
    )
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

# ——— TAB 2: PUSH-UPS (WITH FULL LEGEND) ———
with tab2:
    fig = px.scatter(df, x='date', y='pushups', title="Push-ups")
    fig.add_scatter(x=df['date'], y=df['pushups'],
                    mode='lines', line=dict(color='green', width=2),
                    name='Session Trend Line (Green)', showlegend=True)
    fig.add_scatter(x=df['date'], y=df['cum_pushups'],
                    mode='lines', line=dict(color='purple', width=3),
                    name='Cumulative Total (Purple)', showlegend=True)
    avg_push = df['pushups'].mean()
    fig.add_hline(y=avg_push, line_dash="solid", line_color="gold",
                  line_width=2, annotation_text=f"Avg: {avg_push:.0f}",
                  annotation_position="right")
    fig.add_hline(y=GOAL_PUSH, line_dash="dash", line_color="red",
                  line_width=2, annotation_text=f"Goal: {GOAL_PUSH}",
                  annotation_position="right")
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

# ——— TAB 3: CRUNCHES (WITH FULL LEGEND) ———
with tab3:
    fig = px.scatter(df, x='date', y='crunches', title="Crunches")
    fig.add_scatter(x=df['date'], y=df['crunches'],
                    mode='lines', line=dict(color='green', width=2),
                    name='Session Trend Line (Green)', showlegend=True)
    fig.add_scatter(x=df['date'], y=df['cum_crunches'],
                    mode='lines', line=dict(color='purple', width=3),
                    name='Cumulative Total (Purple)', showlegend=True)
    avg_crunch = df['crunches'].mean()
    fig.add_hline(y=avg_crunch, line_dash="solid", line_color="gold",
                  line_width=2, annotation_text=f"Avg: {avg_crunch:.0f}",
                  annotation_position="right")
    fig.add_hline(y=GOAL_CRUNCH, line_dash="dash", line_color="red",
                  line_width=2, annotation_text=f"Goal: {GOAL_CRUNCH}",
                  annotation_position="right")
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)
