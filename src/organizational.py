"""Organizational mining: handoffs between roles, workload per role, waiting time
before a role picks up work.
"""

import pandas as pd

from src.loader import to_completion_events


def handoff_pairs(df: pd.DataFrame, include_self: bool = True) -> pd.DataFrame:
    """For every case, looks at which resource completed an activity and which
    resource completed the next one, and counts how often each (from, to) pair
    happens. include_self=False drops cases where the same person/role kept the work
    (i.e. not really a "handoff")."""
    completion = to_completion_events(df)
    completion = completion.sort_values(["case_id", "timestamp"])
    next_resource = completion.groupby("case_id")["resource"].shift(-1)

    pairs = pd.DataFrame({
        "from_resource": completion["resource"],
        "to_resource": next_resource,
    }).dropna(subset=["to_resource"])

    if not include_self:
        pairs = pairs[pairs["from_resource"] != pairs["to_resource"]]

    return (
        pairs.groupby(["from_resource", "to_resource"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .reset_index(drop=True)
    )


def handoff_matrix(df: pd.DataFrame, include_self: bool = True) -> pd.DataFrame:
    """Same as handoff_pairs() but pivoted into a from/to matrix, ready for a heatmap."""
    pairs = handoff_pairs(df, include_self=include_self)
    return pairs.pivot_table(
        index="from_resource", columns="to_resource", values="count", fill_value=0
    )


def workload_by_role(df: pd.DataFrame) -> pd.DataFrame:
    """How many activities (and how many distinct cases) each role handled."""
    completion = to_completion_events(df)
    return (
        completion.groupby("resource")
        .agg(n_events=("activity", "size"), n_cases=("case_id", "nunique"))
        .sort_values("n_events", ascending=False)
        .reset_index()
    )


def waiting_time_by_role(df: pd.DataFrame) -> pd.DataFrame:
    """For every paired activity, how long between the previous event in the case and
    this activity's start -- basically "how long did this role sit in the queue before
    picking this up". One row per activity occurrence; milestone activities with no
    start event aren't included since there's no wait to measure."""
    events = df.sort_values(["case_id", "timestamp"]).copy()
    events["prev_timestamp"] = events.groupby("case_id")["timestamp"].shift(1)

    starts = events[events["lifecycle_state"] == "start"].dropna(subset=["prev_timestamp"]).copy()
    starts["waiting_hours"] = (
        (starts["timestamp"] - starts["prev_timestamp"]).dt.total_seconds() / 3600
    )
    return starts[["case_id", "activity", "resource", "site", "waiting_hours"]].reset_index(drop=True)
