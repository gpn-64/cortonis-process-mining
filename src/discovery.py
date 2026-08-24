"""Process discovery: DFG (frequency + performance), inductive miner, case variants.

Functions here just take a DataFrame and return plain PM4Py objects (dict / PetriNet) --
no Streamlit or Graphviz stuff, that happens in app/components when we build the app.
"""

import pm4py

from src.loader import to_completion_events

_KEYS = dict(activity_key="activity", case_id_key="case_id", timestamp_key="timestamp")


def discover_dfg_frequency(df):
    """Frequency DFG: (dfg, start_activities, end_activities), dfg maps
    (source, target) -> number of times that transition happened."""
    log = to_completion_events(df)
    return pm4py.discover_dfg(log, **_KEYS)


def discover_dfg_performance(df, aggregation: str = "mean"):
    """Same as discover_dfg_frequency but the dfg values are durations (seconds)
    instead of counts. aggregation can be "mean", "median", "max", "min", "sum",
    "stdev" or "all"."""
    log = to_completion_events(df)
    return pm4py.discover_performance_dfg(log, perf_aggregation_key=aggregation, **_KEYS)


def filter_dfg_by_frequency(dfg, start_activities, end_activities,
                             activity_percentage: float = 1.0, path_percentage: float = 1.0):
    """Keeps only the most frequent activities/paths in a DFG. Useful once the graph
    gets too big to read -- this is what will back the frequency threshold slider in
    the Streamlit app later."""
    if activity_percentage < 1.0:
        dfg, start_activities, end_activities = pm4py.filter_dfg_activities_percentage(
            dfg, start_activities, end_activities, percentage=activity_percentage
        )
    if path_percentage < 1.0:
        dfg, start_activities, end_activities = pm4py.filter_dfg_paths_percentage(
            dfg, start_activities, end_activities, percentage=path_percentage
        )
    return dfg, start_activities, end_activities


def discover_process_model(df, noise_threshold: float = 0.0):
    """Runs the inductive miner and returns (petri_net, initial_marking, final_marking)."""
    log = to_completion_events(df)
    return pm4py.discover_petri_net_inductive(log, noise_threshold=noise_threshold, **_KEYS)


def get_case_variants(df):
    """Returns the distinct case variants (unique activity sequences), sorted by how
    often they occur, most common first."""
    log = to_completion_events(df)
    n_cases = log["case_id"].nunique()
    variant_counts = pm4py.get_variants_as_tuples(log, **_KEYS)
    rows = [
        {"variant": variant, "count": count, "frequency": count / n_cases}
        for variant, count in variant_counts.items()
    ]
    return sorted(rows, key=lambda r: r["count"], reverse=True)
