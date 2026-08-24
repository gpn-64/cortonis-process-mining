"""Sidebar filters and the function that applies them to the event log."""

import streamlit as st


def render_sidebar_filters(df):
    """Draws the sidebar widgets and returns the picked values as a dict."""
    st.sidebar.header("Filters")

    sites = st.sidebar.multiselect(
        "Site", options=sorted(df["site"].unique()), default=sorted(df["site"].unique())
    )
    deviation_types = st.sidebar.multiselect(
        "Deviation type", options=sorted(df["deviation_type"].unique()),
        default=sorted(df["deviation_type"].unique()),
    )
    severities = st.sidebar.multiselect(
        "Severity", options=["Critical", "Major", "Minor"], default=["Critical", "Major", "Minor"]
    )

    min_date = df["timestamp"].min().date()
    max_date = df["timestamp"].max().date()
    date_range = st.sidebar.date_input(
        "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )

    st.sidebar.divider()
    path_percentage = st.sidebar.slider(
        "Process map: % of paths shown", min_value=10, max_value=100, value=100, step=5,
        help="Lower this if the process map gets too busy to read -- keeps only the most "
             "frequent paths between activities.",
    )

    return {
        "sites": sites,
        "deviation_types": deviation_types,
        "severities": severities,
        "date_range": date_range,
        "path_percentage": path_percentage / 100,
    }


def apply_filters(df, filters):
    """Filters the event log down to the cases matching the sidebar selection.

    Everything is filtered at the case level -- if a case matches, every one of its
    events is kept. Filtering event-by-event would risk cutting a case's trace off
    partway through (e.g. keeping "Deviation Opened" but dropping "Closed" because it
    happened a few days later), which would make discovery/conformance look wrong for
    reasons that have nothing to do with the actual process.
    """
    case_attrs = df.drop_duplicates("case_id").set_index("case_id")

    keep = (
        case_attrs["site"].isin(filters["sites"])
        & case_attrs["deviation_type"].isin(filters["deviation_types"])
        & case_attrs["severity"].isin(filters["severities"])
    )

    date_range = filters["date_range"]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        opened_at = df[df["activity"] == "Deviation Opened"].set_index("case_id")["timestamp"]
        start, end = date_range
        in_range = opened_at.dt.date.between(start, end)
        keep = keep & keep.index.map(in_range).fillna(False)

    keep_cases = case_attrs.index[keep]
    return df[df["case_id"].isin(keep_cases)]
