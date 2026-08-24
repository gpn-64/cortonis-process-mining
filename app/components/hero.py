"""The headline callout at the top of the app -- the "why does this project exist"
banner. Always computed on the full event log, not the filtered one, since it's meant
to be the fixed headline finding (Lyon), not something that should change or break
if someone filters Lyon out of the sidebar.
"""

import streamlit as st

from src import kpi


@st.cache_data
def _lyon_vs_network_stats(df):
    step = kpi.step_durations(df)
    lyon_step = step.loc[step["site"] == "Lyon", "duration_hours"].mean()
    rest_step = step.loc[step["site"] != "Lyon", "duration_hours"].mean()
    step_delta_pct = (lyon_step - rest_step) / rest_step * 100

    cycle = kpi.case_cycle_time(df)
    lyon_cycle = cycle.loc[cycle["site"] == "Lyon", "cycle_time_days"].mean()
    rest_cycle = cycle.loc[cycle["site"] != "Lyon", "cycle_time_days"].mean()
    cycle_delta_pct = (lyon_cycle - rest_cycle) / rest_cycle * 100

    rework = kpi.rework_time(df)
    has_rework = rework["rework_time_days"] > 0
    lyon_rework_rate = has_rework[rework["site"] == "Lyon"].mean()
    rest_rework_rate = has_rework[rework["site"] != "Lyon"].mean()
    rework_ratio = lyon_rework_rate / rest_rework_rate

    return step_delta_pct, cycle_delta_pct, rework_ratio


def render(df):
    step_delta_pct, cycle_delta_pct, rework_ratio = _lyon_vs_network_stats(df)

    with st.container(border=True):
        col_text, col1, col2, col3 = st.columns([3, 1, 1, 1])
        with col_text:
            st.caption("THE FINDING")
            st.markdown(
                f"Lyon's average step duration is **in line with the network** "
                f"({step_delta_pct:+.0f}%). Its CAPA cycle time is "
                f"**{cycle_delta_pct:+.0f}% longer**. Standard reporting can't explain "
                "the gap -- process mining can."
            )
        col1.metric("step duration delta", f"{step_delta_pct:+.0f}%")
        col2.metric("cycle time vs. network", f"{cycle_delta_pct:+.0f}%")
        col3.metric("rework rate vs. network", f"{rework_ratio:.1f}×")
