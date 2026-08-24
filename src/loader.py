"""Loads the event log CSV into a validated DataFrame."""

import pandas as pd

REQUIRED_COLUMNS = [
    "case_id", "activity", "timestamp", "lifecycle_state",
    "resource", "site", "deviation_type", "severity", "regulatory_deadline_days",
]

VALID_LIFECYCLE_STATES = {"start", "complete"}


def load_event_log(csv_path: str = "data/deviation_capa_log.csv") -> pd.DataFrame:
    """Reads the CSV and does some basic sanity checks before handing it back."""
    df = pd.read_csv(csv_path)

    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Event log is missing required columns: {sorted(missing)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    if df[REQUIRED_COLUMNS].isnull().any().any():
        bad_cols = df[REQUIRED_COLUMNS].columns[df[REQUIRED_COLUMNS].isnull().any()].tolist()
        raise ValueError(f"Event log has null values in required column(s): {bad_cols}")

    bad_lifecycle = set(df["lifecycle_state"].unique()) - VALID_LIFECYCLE_STATES
    if bad_lifecycle:
        raise ValueError(f"Unexpected lifecycle_state value(s): {sorted(bad_lifecycle)}")

    return df.sort_values(["case_id", "timestamp"]).reset_index(drop=True)


def to_completion_events(df: pd.DataFrame) -> pd.DataFrame:
    """Keeps only the 'complete' events.

    Each paired activity (start + complete) would otherwise show up twice in a row in
    the DFG/Petri net, which just adds noise -- we only care about the order activities
    happened in for discovery/conformance, not the start/complete pairs (that's what
    kpi.step_durations() is for).
    """
    completion = df[df["lifecycle_state"] == "complete"].copy()
    return completion.sort_values(["case_id", "timestamp"]).reset_index(drop=True)
