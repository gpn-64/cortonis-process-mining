"""Entry point for the Cortonis Pharma process mining app.

Run with: streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src.loader import load_event_log
from src import discovery
from app.components import filters, process_map, conformance_view, bottlenecks_view, organizational_view

st.set_page_config(page_title="Cortonis Pharma - Deviation & CAPA Process Mining", layout="wide")


@st.cache_data
def get_event_log():
    return load_event_log()


@st.cache_data
def get_dfg(filtered_df, mode, path_percentage):
    if mode == "frequency":
        dfg, sa, ea = discovery.discover_dfg_frequency(filtered_df)
    else:
        dfg, sa, ea = discovery.discover_dfg_performance(filtered_df)
    if path_percentage < 1.0:
        dfg, sa, ea = discovery.filter_dfg_by_frequency(dfg, sa, ea, path_percentage=path_percentage)
    return dfg, sa, ea


def main():
    st.title("Cortonis Pharma — Deviation & CAPA Process Mining")
    st.caption(
        "Synthetic data. See the README for the full write-up, or "
        "`notebooks/01_exploration.ipynb` for the narrated analysis."
    )

    df = get_event_log()
    selected_filters = filters.render_sidebar_filters(df)
    filtered_df = filters.apply_filters(df, selected_filters)

    st.sidebar.divider()
    st.sidebar.caption(f"{filtered_df['case_id'].nunique()} cases in the current filter")

    tab1, tab2, tab3, tab4 = st.tabs(["Process Map", "Conformance", "Bottlenecks & SLA", "Organizational"])

    with tab1:
        if filtered_df.empty:
            st.info("No cases match the current filters.")
        else:
            mode = st.radio("View", ["frequency", "performance"], horizontal=True)
            dfg, sa, ea = get_dfg(filtered_df, mode, selected_filters["path_percentage"])
            graph = process_map.build_process_map(dfg, sa, ea, mode=mode)
            st.graphviz_chart(graph)

    with tab2:
        conformance_view.render(filtered_df)

    with tab3:
        bottlenecks_view.render(filtered_df)

    with tab4:
        organizational_view.render(filtered_df)


if __name__ == "__main__":
    main()
