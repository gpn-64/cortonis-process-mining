"""Tab 4 - Organizational: handoff heatmap between roles, workload per role, waiting
time before each role picks up work.
"""

import plotly.express as px
import streamlit as st

from src import organizational as org

GREEN = "#0B5D3B"


def render(filtered_df):
    if filtered_df.empty:
        st.info("No cases match the current filters.")
        return

    st.subheader("Handoffs between roles")
    matrix = org.handoff_matrix(filtered_df, include_self=False)
    fig = px.imshow(
        matrix, text_auto=True, color_continuous_scale="Greens",
        labels={"x": "to", "y": "from", "color": "handoffs"},
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Workload by role")
        workload = org.workload_by_role(filtered_df)
        fig2 = px.bar(
            workload, x="n_events", y="resource", orientation="h", color_discrete_sequence=[GREEN]
        )
        fig2.update_layout(yaxis_title="", xaxis_title="activity instances", height=350)
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.subheader("Waiting time by role")
        wait = org.waiting_time_by_role(filtered_df)
        median_wait = wait.groupby("resource")["waiting_hours"].median().sort_values(ascending=False)
        fig3 = px.bar(
            x=median_wait.values, y=median_wait.index, orientation="h", color_discrete_sequence=[GREEN]
        )
        fig3.update_layout(yaxis_title="", xaxis_title="median waiting time (hours)", height=350)
        st.plotly_chart(fig3, use_container_width=True)
