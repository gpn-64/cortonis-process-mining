"""Tab 3 - Bottlenecks & SLA: cycle time by step, duration distributions, deadline
breach rate by segment. Plotly only, no PM4Py here (see spec section 5).
"""

import plotly.express as px
import streamlit as st

from src import kpi

GREEN = "#0B5D3B"


def render(filtered_df):
    if filtered_df.empty:
        st.info("No cases match the current filters.")
        return

    cycle = kpi.case_cycle_time(filtered_df)
    breach = kpi.deadline_breach(filtered_df)

    col1, col2 = st.columns(2)
    col1.metric("Average cycle time", f"{cycle['cycle_time_days'].mean():.1f} days")
    col2.metric("Deadline breach rate", f"{breach['breached'].mean() * 100:.1f}%")

    st.subheader("Step duration distributions")
    steps = kpi.step_durations(filtered_df)
    order = steps.groupby("activity")["duration_hours"].median().sort_values(ascending=False).index
    fig = px.box(steps, x="duration_hours", y="activity", category_orders={"activity": list(order)},
                 color_discrete_sequence=[GREEN])
    fig.update_layout(yaxis_title="", xaxis_title="duration (hours)", height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Regulatory deadline breach rate")
    segment = st.radio("Break down by", ["site", "severity", "deviation_type"], horizontal=True)
    breach_rate = kpi.breach_rate_by(filtered_df, segment).sort_values(ascending=False) * 100
    fig2 = px.bar(
        x=breach_rate.index, y=breach_rate.values, color_discrete_sequence=[GREEN],
        labels={"x": segment, "y": "% of cases breaching regulatory_deadline_days"},
    )
    fig2.update_layout(height=350)
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Cycle time by site")
    fig3 = px.box(cycle, x="site", y="cycle_time_days", color_discrete_sequence=[GREEN])
    fig3.update_layout(height=350)
    st.plotly_chart(fig3, use_container_width=True)
