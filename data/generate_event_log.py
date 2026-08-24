#!/usr/bin/env python3
"""Generates the synthetic Cortonis Pharma deviation/CAPA event log.

Basically a state machine that walks each case through the SOP-QA-012 flow, picking
random durations from log-normal distributions and injecting the process deviations
described in the project spec (rework loops, escalations, skipped steps, reopened
cases, and a queue-time issue at Barcelona).

Important: Lyon only gets a higher REWORK rate, not slower steps. Its steps use the
exact same duration distributions as everyone else. The whole point of the demo is that
this doesn't show up if you only look at average step time.
"""

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

SEED = 42
N_CASES = 3000

SITES = ["Lyon", "Frankfurt", "Milan", "Barcelona", "Dublin"]
SITE_WEIGHTS = [0.22, 0.20, 0.26, 0.16, 0.16]

DEVIATION_TYPES = ["Production", "Laboratory", "Packaging", "Distribution", "Documentation"]
DEVIATION_TYPE_WEIGHTS = [0.34, 0.24, 0.18, 0.14, 0.10]

SEVERITIES = ["Critical", "Major", "Minor"]
SEVERITY_WEIGHTS = [0.12, 0.28, 0.60]
REGULATORY_DEADLINE_DAYS = {"Critical": 30, "Major": 60, "Minor": 90}

# who does what (see the SOP doc for the actual responsibilities)
ROLE_BY_ACTIVITY = {
    "Deviation Opened": "Production Supervisor",
    "Initial Assessment": "QA Investigator",
    "Investigation Assigned": "Site Quality Manager",
    "Root Cause Analysis": "QA Investigator",
    "CAPA Proposed": "CAPA Owner",
    "Quality Council Review": "Quality Council",
    "CAPA Implemented": "CAPA Owner",
    "Effectiveness Check": "QA Investigator",
    "Closed": "Site Quality Manager",
    "Deviation Reopened": "Site Quality Manager",
}
# CAPA Approved is handled separately below because it depends on severity

# how long each activity takes (start -> complete), log-normal (mu, sigma) in hours
DURATION_PARAMS_HOURS = {
    "Initial Assessment": (np.log(4), 0.5),
    "Investigation Assigned": (np.log(2), 0.5),
    "Root Cause Analysis": (np.log(96), 0.6),
    "CAPA Proposed": (np.log(40), 0.55),
    "Quality Council Review": (np.log(20), 0.45),
    "CAPA Approved": (np.log(30), 0.5),
    "CAPA Implemented": (np.log(140), 0.6),
    "Effectiveness Check": (np.log(220), 0.5),
}

# how long a case waits before someone starts the next activity
WAIT_PARAMS_HOURS = {
    "Initial Assessment": (np.log(6), 0.6),
    "Investigation Assigned": (np.log(18), 0.7),
    "Root Cause Analysis": (np.log(10), 0.6),
    "CAPA Proposed": (np.log(8), 0.6),
    "Quality Council Review": (np.log(12), 0.5),
    "CAPA Approved": (np.log(8), 0.6),
    "CAPA Implemented": (np.log(14), 0.6),
    "Effectiveness Check": (np.log(16), 0.6),
}
CLOSING_GAP_HOURS = (np.log(3), 0.4)
REOPEN_GAP_DAYS = (np.log(20), 0.7)

REWORK_RATE_NETWORK = 0.18
REWORK_RATE_LYON = 0.45          # ~2.5x network, this is the whole point of the project
MAX_REWORK_CYCLES = 5            # basically uncapped, 0.45**5 is already under 2%

# Extra delay when a CAPA gets rejected and has to go through Root Cause Analysis again
# (someone has to reconvene the investigation etc). Tuned by hand so Lyon's cycle time
# ends up ~40% longer than the rest of the network, matching what a real "why is this
# site slower" investigation would find.
REWORK_OVERHEAD_DAYS = (np.log(16), 0.5)

SKIP_EFFECTIVENESS_CHECK_RATE_MINOR = 0.08   # only happens on Minor cases
REOPEN_RATE = 0.04

BARCELONA_WAIT_MULTIPLIER = 4.5  # Barcelona has its own, unrelated queueing problem

# case open dates: starts at the SOP's effective date, and stops early enough that even
# a long case (rework + reopening) has closed before "today"
CASE_START_RANGE = (pd.Timestamp("2025-01-15"), pd.Timestamp("2026-03-15"))

OUT_CSV = "data/deviation_capa_log.csv"
OUT_SOP_JSON = "data/sop_reference.json"

SOP_FLOW = [
    "Deviation Opened", "Initial Assessment", "Investigation Assigned",
    "Root Cause Analysis", "CAPA Proposed", "CAPA Approved", "CAPA Implemented",
    "Effectiveness Check", "Closed",
]


@dataclass
class CaseParams:
    case_id: str
    site: str
    deviation_type: str
    severity: str
    rework_rate: float
    wait_multiplier: dict


def sample_lognormal(rng, mu, sigma):
    return float(rng.lognormal(mean=mu, sigma=sigma))


def capa_approver(severity):
    # Major/Critical go to the Quality Council, Minor stays with the Site Quality Manager
    return "Quality Council" if severity in ("Major", "Critical") else "Site Quality Manager"


def build_case_events(rng, params, case_open_ts):
    """Walks one case through the process and returns its list of events."""
    events = []
    t = case_open_ts

    def emit(activity, ts, lifecycle, resource):
        events.append({
            "case_id": params.case_id,
            "activity": activity,
            "timestamp": ts,
            "lifecycle_state": lifecycle,
            "resource": resource,
            "site": params.site,
            "deviation_type": params.deviation_type,
            "severity": params.severity,
            "regulatory_deadline_days": REGULATORY_DEADLINE_DAYS[params.severity],
        })

    def run_paired(activity, cursor, resource=None):
        # emits a start event, then a complete event some time later
        wait_mu, wait_sigma = WAIT_PARAMS_HOURS[activity]
        wait_h = sample_lognormal(rng, wait_mu, wait_sigma) * params.wait_multiplier.get(activity, 1.0)
        start_ts = cursor + pd.Timedelta(hours=wait_h)
        dur_mu, dur_sigma = DURATION_PARAMS_HOURS[activity]
        dur_h = sample_lognormal(rng, dur_mu, dur_sigma)
        complete_ts = start_ts + pd.Timedelta(hours=dur_h)
        role = resource or ROLE_BY_ACTIVITY[activity]
        emit(activity, start_ts, "start", role)
        emit(activity, complete_ts, "complete", role)
        return complete_ts

    emit("Deviation Opened", t, "complete", ROLE_BY_ACTIVITY["Deviation Opened"])
    t = run_paired("Initial Assessment", t)
    t = run_paired("Investigation Assigned", t)

    def capa_cycle(cursor):
        # one full pass: investigate, propose a CAPA, maybe escalate, get it approved
        cursor = run_paired("Root Cause Analysis", cursor)
        cursor = run_paired("CAPA Proposed", cursor)
        if params.severity == "Critical":
            cursor = run_paired("Quality Council Review", cursor)
        cursor = run_paired("CAPA Approved", cursor, resource=capa_approver(params.severity))
        return cursor

    t = capa_cycle(t)

    # if the CAPA gets rejected, go through the cycle again (up to MAX_REWORK_CYCLES times)
    cycles = 0
    while cycles < MAX_REWORK_CYCLES and rng.random() < params.rework_rate:
        overhead_days = sample_lognormal(rng, *REWORK_OVERHEAD_DAYS)
        t = t + pd.Timedelta(days=overhead_days)
        t = capa_cycle(t)
        cycles += 1

    t = run_paired("CAPA Implemented", t)

    skip_check = params.severity == "Minor" and rng.random() < SKIP_EFFECTIVENESS_CHECK_RATE_MINOR
    if not skip_check:
        t = run_paired("Effectiveness Check", t)

    close_gap_h = sample_lognormal(rng, *CLOSING_GAP_HOURS)
    t = t + pd.Timedelta(hours=close_gap_h)
    emit("Closed", t, "complete", ROLE_BY_ACTIVITY["Closed"])

    # small chance the case gets reopened later and goes through (a simplified) cycle again
    if rng.random() < REOPEN_RATE:
        reopen_gap_d = sample_lognormal(rng, *REOPEN_GAP_DAYS)
        t = t + pd.Timedelta(days=reopen_gap_d)
        emit("Deviation Reopened", t, "complete", ROLE_BY_ACTIVITY["Deviation Reopened"])
        t = capa_cycle(t)
        t = run_paired("CAPA Implemented", t)
        skip_check_2 = params.severity == "Minor" and rng.random() < SKIP_EFFECTIVENESS_CHECK_RATE_MINOR
        if not skip_check_2:
            t = run_paired("Effectiveness Check", t)
        close_gap_h = sample_lognormal(rng, *CLOSING_GAP_HOURS)
        t = t + pd.Timedelta(hours=close_gap_h)
        emit("Closed", t, "complete", ROLE_BY_ACTIVITY["Closed"])

    return events


def generate():
    rng = np.random.default_rng(SEED)

    all_events = []
    for i in range(1, N_CASES + 1):
        site = rng.choice(SITES, p=SITE_WEIGHTS)
        deviation_type = rng.choice(DEVIATION_TYPES, p=DEVIATION_TYPE_WEIGHTS)
        severity = rng.choice(SEVERITIES, p=SEVERITY_WEIGHTS)

        rework_rate = REWORK_RATE_LYON if site == "Lyon" else REWORK_RATE_NETWORK
        wait_multiplier = {}
        if site == "Barcelona":
            wait_multiplier["Investigation Assigned"] = BARCELONA_WAIT_MULTIPLIER

        case_open_ts = CASE_START_RANGE[0] + pd.Timedelta(
            seconds=rng.uniform(0, (CASE_START_RANGE[1] - CASE_START_RANGE[0]).total_seconds())
        )
        year = case_open_ts.year
        params = CaseParams(
            case_id=f"DEV-{year}-{i:05d}",
            site=site,
            deviation_type=deviation_type,
            severity=severity,
            rework_rate=rework_rate,
            wait_multiplier=wait_multiplier,
        )
        all_events.extend(build_case_events(rng, params, case_open_ts))

    df = pd.DataFrame(all_events)
    df = df.sort_values(["case_id", "timestamp"]).reset_index(drop=True)
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df.to_csv(OUT_CSV, index=False)
    print(f"Wrote {len(df)} events for {df['case_id'].nunique()} cases to {OUT_CSV}")

    # also dump the reference flow so conformance checking has something to compare against
    sop_reference = {
        "process_name": "Cortonis Pharma Deviation and CAPA Process",
        "sop_reference": "SOP-QA-012, Version 3.0",
        "flow": SOP_FLOW,
        "transitions": [
            {"from": SOP_FLOW[i], "to": SOP_FLOW[i + 1]} for i in range(len(SOP_FLOW) - 1)
        ],
    }
    with open(OUT_SOP_JSON, "w") as f:
        json.dump(sop_reference, f, indent=2)
    print(f"Wrote SOP reference model to {OUT_SOP_JSON}")

    return df


if __name__ == "__main__":
    generate()
