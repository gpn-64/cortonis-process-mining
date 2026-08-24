"""Conformance checking: replays the event log against the SOP-QA-012 reference model
(data/sop_reference.json) using token-based replay.

Note on the reference model: it's just the straight nine-step flow from the SOP, no
branches for rework/escalation/reopening (the SOP itself says those are handled
separately, see section 9 of the doc). That means token-based replay will correctly
flag rework loops and skipped steps as fitness problems, but it will NOT flag
"Quality Council Review" or "Deviation Reopened" as problems, since those activities
don't even exist in the reference model -- PM4Py just skips events it can't match to a
transition. I report those separately as out_of_model_activity_rates instead of letting
them silently not count, since whether they should count as a "deviation" is really a
judgment call.
"""

import json
from collections import Counter

import pandas as pd
import pm4py
from pm4py.objects.petri_net.obj import Marking, PetriNet
from pm4py.objects.petri_net.utils import petri_utils

from src.loader import to_completion_events

_KEYS = dict(activity_key="activity", case_id_key="case_id", timestamp_key="timestamp")


def build_reference_net(sop_json_path: str = "data/sop_reference.json"):
    """Builds a simple, straight-line Petri net from the SOP flow (one transition per
    step, no branches). Returns (petri_net, initial_marking, final_marking, flow)."""
    with open(sop_json_path) as f:
        sop = json.load(f)
    flow = sop["flow"]

    net = PetriNet(sop.get("process_name", "SOP reference"))
    places = [PetriNet.Place(f"p{i}") for i in range(len(flow) + 1)]
    for place in places:
        net.places.add(place)
    for i, activity in enumerate(flow):
        transition = PetriNet.Transition(f"t{i}", activity)
        net.transitions.add(transition)
        petri_utils.add_arc_from_to(places[i], transition, net)
        petri_utils.add_arc_from_to(transition, places[i + 1], net)

    initial_marking = Marking({places[0]: 1})
    final_marking = Marking({places[-1]: 1})
    return net, initial_marking, final_marking, flow


def check_conformance(df: pd.DataFrame, net=None, im=None, fm=None, flow=None) -> pd.DataFrame:
    """Runs token-based replay for every case in df and returns one row per case:
    case_id, site, severity, deviation_type, trace, fit, fitness, missing_tokens,
    remaining_tokens, problem_activities, out_of_model_activities."""
    if net is None:
        net, im, fm, flow = build_reference_net()
    flow_set = set(flow)

    log = to_completion_events(df)
    diagnostics = pm4py.conformance_diagnostics_token_based_replay(log, net, im, fm, **_KEYS)

    case_order = log.drop_duplicates("case_id")["case_id"].tolist()
    traces = log.groupby("case_id")["activity"].apply(tuple).to_dict()
    case_attrs = log.drop_duplicates("case_id").set_index("case_id")[
        ["site", "severity", "deviation_type"]
    ].to_dict("index")

    rows = []
    for case_id, diag in zip(case_order, diagnostics):
        trace = traces[case_id]
        rows.append({
            "case_id": case_id,
            "site": case_attrs[case_id]["site"],
            "severity": case_attrs[case_id]["severity"],
            "deviation_type": case_attrs[case_id]["deviation_type"],
            "trace": trace,
            "fit": bool(diag["trace_is_fit"]),
            "fitness": float(diag["trace_fitness"]),
            "missing_tokens": int(diag["missing_tokens"]),
            "remaining_tokens": int(diag["remaining_tokens"]),
            "problem_activities": tuple(sorted({t.label for t in diag["transitions_with_problems"]})),
            "out_of_model_activities": tuple(sorted(set(trace) - flow_set)),
        })
    return pd.DataFrame(rows)


def conformance_summary(conformance_df: pd.DataFrame) -> dict:
    """Rolls check_conformance() up into a few headline numbers."""
    n = len(conformance_df)
    problem_counter = Counter(
        a for problems in conformance_df["problem_activities"] for a in problems
    )
    out_of_model_counter = Counter(
        a for acts in conformance_df["out_of_model_activities"] for a in acts
    )
    return {
        "n_cases": n,
        "conformance_rate": conformance_df["fit"].mean(),
        "average_fitness": conformance_df["fitness"].mean(),
        "most_frequent_problem_activities": problem_counter.most_common(),
        "out_of_model_activity_rates": {
            act: cnt / n for act, cnt in out_of_model_counter.most_common()
        },
    }


def most_atypical_cases(conformance_df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """The n cases with the worst fitness score, for spot-checking."""
    return conformance_df.sort_values("fitness").head(n)[
        ["case_id", "site", "severity", "fitness", "problem_activities", "trace"]
    ]
