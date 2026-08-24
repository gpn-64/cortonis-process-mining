"""KPI computations: cycle time, isolated rework time, deadline breach, step duration.

Just pandas here, no PM4Py / Streamlit -- keeps this module easy to test on its own.
"""

import pandas as pd

CASE_ATTR_COLS = ["site", "severity", "deviation_type", "regulatory_deadline_days"]


def case_cycle_time(df: pd.DataFrame) -> pd.DataFrame:
    """Cycle time per case, in days, from the first "Deviation Opened" to the last
    "Closed" (so a reopened case counts its full time, including the reopened part)."""
    opened = df[df["activity"] == "Deviation Opened"].groupby("case_id")["timestamp"].min()
    closed = df[df["activity"] == "Closed"].groupby("case_id")["timestamp"].max()

    out = df.drop_duplicates("case_id").set_index("case_id")[CASE_ATTR_COLS].copy()
    out["opened_at"] = opened
    out["closed_at"] = closed
    out = out.dropna(subset=["opened_at", "closed_at"])
    out["cycle_time_days"] = (out["closed_at"] - out["opened_at"]).dt.total_seconds() / 86400
    return out.reset_index()


def rework_time(df: pd.DataFrame) -> pd.DataFrame:
    """Isolates how much of a case's cycle time was spent going through rejected
    CAPA -> Root Cause Analysis loops, instead of just measuring "total time" and
    guessing.

    How it works: group each case's "CAPA Approved" events by which "CAPA Implemented"
    event follows them. If a group has more than one "CAPA Approved" in it, every one
    except the last was effectively a rejection. rework_time_days is the time between
    the first and last "CAPA Approved" in that group, summed across groups (a case can
    have more than one group if it got reopened). Cases with no rejections get 0.
    """
    approved = df[(df["activity"] == "CAPA Approved") & (df["lifecycle_state"] == "complete")]
    implemented = df[(df["activity"] == "CAPA Implemented") & (df["lifecycle_state"] == "complete")]

    rows = []
    for case_id, group in df.drop_duplicates("case_id").set_index("case_id")[CASE_ATTR_COLS].iterrows():
        approved_ts = approved.loc[approved["case_id"] == case_id, "timestamp"].sort_values().tolist()
        impl_ts = implemented.loc[implemented["case_id"] == case_id, "timestamp"].sort_values().tolist()

        rework_days = 0.0
        idx = 0
        for impl in impl_ts:
            cluster = []
            while idx < len(approved_ts) and approved_ts[idx] < impl:
                cluster.append(approved_ts[idx])
                idx += 1
            if len(cluster) > 1:
                rework_days += (cluster[-1] - cluster[0]).total_seconds() / 86400

        rows.append({"case_id": case_id, **group.to_dict(), "rework_time_days": rework_days})

    return pd.DataFrame(rows)


def deadline_breach(df: pd.DataFrame) -> pd.DataFrame:
    """Same as case_cycle_time() but with a "breached" column: did the case take
    longer than its regulatory_deadline_days?"""
    cycle = case_cycle_time(df)
    cycle["breached"] = cycle["cycle_time_days"] > cycle["regulatory_deadline_days"]
    return cycle


def breach_rate_by(df: pd.DataFrame, by) -> pd.Series:
    """Breach rate (0-1) grouped by one or more columns, e.g. "site" or ["site", "severity"]."""
    return deadline_breach(df).groupby(by)["breached"].mean()


def step_durations(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (case, activity, occurrence) with how long that activity took
    (start -> complete), in hours. Activities that only ever get logged as "complete"
    (the case milestones) aren't included since there's nothing to measure."""
    paired = df[df["lifecycle_state"].isin(["start", "complete"])].copy()
    paired["occurrence"] = paired.groupby(["case_id", "activity"]).cumcount() // 2
    pivot = paired.pivot_table(
        index=["case_id", "activity", "occurrence"],
        columns="lifecycle_state", values="timestamp", aggfunc="first",
    ).dropna(subset=["start", "complete"])
    pivot["duration_hours"] = (pivot["complete"] - pivot["start"]).dt.total_seconds() / 3600
    pivot = pivot.reset_index()

    attrs = df.drop_duplicates("case_id").set_index("case_id")[["site", "severity", "deviation_type"]]
    return pivot.join(attrs, on="case_id")
