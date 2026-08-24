"""Tab 2 - Conformance: conformance rate, most frequent deviations from the SOP, and
the most atypical cases with their trace.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from src import conformance

GREEN = "#0B5D3B"
AMBER = "#B4750D"


@st.cache_data
def _cached_conformance(filtered_df):
    net, im, fm, flow = conformance.build_reference_net()
    return conformance.check_conformance(filtered_df, net, im, fm, flow)


def render(filtered_df):
    if filtered_df.empty:
        st.info("No cases match the current filters.")
        return

    conf_df = _cached_conformance(filtered_df)
    summary = conformance.conformance_summary(conf_df)

    col1, col2 = st.columns(2)
    col1.metric("Conformance rate", f"{summary['conformance_rate'] * 100:.1f}%")
    col2.metric("Average fitness", f"{summary['average_fitness']:.3f}")

    st.subheader("Most frequent fitness problems")
    problems = summary["most_frequent_problem_activities"]
    if problems:
        problems_df = pd.DataFrame(problems, columns=["activity", "occurrences"])
        fig = px.bar(
            problems_df, x="occurrences", y="activity", orientation="h", color_discrete_sequence=[AMBER]
        )
        fig.update_layout(yaxis_title="", xaxis_title="occurrences (token mismatch)", height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("No fitness problems in the filtered cases.")

    out_of_model = summary["out_of_model_activity_rates"]
    if out_of_model:
        st.caption(
            "Activities not in the SOP-QA-012 reference flow (governed separately, "
            "see SOP section 9) -- shown here rather than counted against fitness:"
        )
        ooc_df = pd.DataFrame(
            [(k, f"{v * 100:.1f}%") for k, v in out_of_model.items()],
            columns=["activity", "% of cases"],
        )
        st.dataframe(ooc_df, hide_index=True, use_container_width=True)

    st.subheader("Most atypical cases")
    atypical = conformance.most_atypical_cases(conf_df, n=10).copy()
    atypical["trace"] = atypical["trace"].apply(lambda t: " -> ".join(t))
    atypical["problem_activities"] = atypical["problem_activities"].apply(", ".join)
    st.dataframe(atypical, hide_index=True, use_container_width=True)
