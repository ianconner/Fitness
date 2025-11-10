import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go

# Assume session state is set from app.py
if 'user_id' not in st.session_state or st.session_state.user_id is None:
    st.error("Please login first.")
    st.stop()

user_id = st.session_state.user_id

# Fetch logs
conn = sqlite3.connect('running_logs.db')
df = pd.read_sql_query(f"SELECT * FROM logs WHERE user_id = {user_id} ORDER BY date", conn)
conn.close()

if df.empty:
    st.info("No runs logged yet. Go to 'Log a Run' to add some!")
else:
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')

    # Pace Over Time Chart
    st.subheader("Pace Over Time")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df['date'], y=df['pace'], mode='lines+markers', name='Your Trend Line (Green)', line=dict(color='green', width=2)))

    # Add dummy traces for legend
    fig1.add_trace(go.Scatter(x=[], y=[], mode='lines', line=dict(color='gold', dash='solid'), name='Average (Yellow Line)', showlegend=True))
    fig1.add_trace(go.Scatter(x=[], y=[], mode='lines', line=dict(color='red', dash='dash'), name='Goal (Red Dashed Line)', showlegend=True))

    # Add actual hlines
    avg_pace = df['pace'].mean()
    fig1.add_hline(y=avg_pace, line_dash="solid", line_color="gold")
    goal_pace = st.number_input("Set Goal Pace (min/km)", min_value=0.0, value=5.0, step=0.1)
    fig1.add_hline(y=goal_pace, line_dash="dash", line_color="red")

    fig1.update_layout(xaxis_title="Date", yaxis_title="Pace (min/km)", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig1)

    # Average Pace Per Distance Chart
    st.subheader("Average Pace Per Distance")
    distance_bins = [0, 5, 10, 21, 42, float('inf')]
    distance_labels = ['<5km', '5-10km', '10-21km', '21-42km', '>42km']
    df['distance_group'] = pd.cut(df['distance'], bins=distance_bins, labels=distance_labels)
    avg_pace_per_group = df.groupby('distance_group')['pace'].mean().reset_index()

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=avg_pace_per_group['distance_group'], y=avg_pace_per_group['pace'], name='Average Pace (Yellow Line)'))

    # Add dummy traces for legend (adjusted for bar chart context, but focusing on lines)
    fig2.add_trace(go.Scatter(x=[], y=[], mode='lines', line=dict(color='gold', dash='solid'), name='Average (Yellow Line)', showlegend=True))
    fig2.add_trace(go.Scatter(x=[], y=[], mode='lines', line=dict(color='red', dash='dash'), name='Goal (Red Dashed Line)', showlegend=True))

    # Add actual hlines (global avg and goal)
    fig2.add_hline(y=avg_pace, line_dash="solid", line_color="gold")
    fig2.add_hline(y=goal_pace, line_dash="dash", line_color="red")

    fig2.update_layout(xaxis_title="Distance Group", yaxis_title="Average Pace (min/km)", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig2)

# Sidebar (consistent across pages)
with st.sidebar:
    st.title("Navigation")
    st.page_link("app.py", label="Home")
    st.page_link("pages/01_Dashboard.py", label="Dashboard")
    st.page_link("pages/02_Log_Run.py", label="Log a Run")
    st.page_link("pages/04_Coach.py", label="Coach")
    if st.session_state.role == 'admin':
        st.page_link("pages/03_Admin.py", label="Admin")
    if st.button("Logout"):
        del st.session_state.user_id
        del st.session_state.role
        st.experimental_rerun()
