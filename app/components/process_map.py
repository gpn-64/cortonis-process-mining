"""Turns the raw DFG dicts from src/discovery.py into a graphviz.Digraph for
st.graphviz_chart. This is where PM4Py's rendering is used (see the README / spec:
Plotly for KPIs and charts, Graphviz only for the process map itself).
"""

import graphviz

SOP_ACTIVITIES = {
    "Deviation Opened", "Initial Assessment", "Investigation Assigned",
    "Root Cause Analysis", "CAPA Proposed", "CAPA Approved", "CAPA Implemented",
    "Effectiveness Check", "Closed",
}

GREEN = "#0B5D3B"
GREEN_FILL = "#E8F2EC"
AMBER = "#B4750D"
AMBER_FILL = "#FCEFD8"
RED = "#8B1E1E"
RED_FILL = "#FBE3E3"


def _node_style(activity):
    if activity in SOP_ACTIVITIES:
        return GREEN_FILL, GREEN
    if activity == "Quality Council Review":
        return AMBER_FILL, AMBER
    return RED_FILL, RED  # Deviation Reopened


def _format_seconds(seconds):
    hours = seconds / 3600
    if hours < 48:
        return f"{hours:.0f}h"
    return f"{hours / 24:.1f}d"


def build_process_map(dfg, start_activities, end_activities, mode="frequency"):
    """mode: "frequency" (edge label = count) or "performance" (edge label = avg duration)."""
    graph = graphviz.Digraph()
    # extra rank/node spacing so edge labels have room to sit clear of boxes and
    # of each other once there are a few curved back-edges (rework, reopening)
    graph.attr(rankdir="LR", bgcolor="white", ranksep="0.9", nodesep="0.55")
    graph.attr("node", shape="box", style="rounded,filled", fontname="Helvetica", fontsize="11")
    graph.attr("edge", fontname="Helvetica", fontsize="10", color="#555555")

    graph.node("__start__", "", shape="circle", style="filled", fillcolor=GREEN, width="0.25")
    graph.node("__end__", "", shape="doublecircle", style="filled", fillcolor=RED, width="0.25")

    nodes = {a for edge in dfg for a in edge} | set(start_activities) | set(end_activities)
    for activity in nodes:
        fill, color = _node_style(activity)
        graph.node(activity, activity, fillcolor=fill, color=color)

    # these edges are short (start/end circle sits right next to its node), so a
    # regular label fits better than xlabel -- xlabel needs room to offset into
    for activity, count in start_activities.items():
        graph.edge("__start__", activity, label=str(count), color=GREEN, fontcolor=GREEN)
    for activity, count in end_activities.items():
        graph.edge(activity, "__end__", label=str(count), color=RED, fontcolor=RED)

    # xlabel (rather than label) lets Graphviz place each count clear of the edge
    # line and of neighbouring nodes/labels instead of dead-centering it on the
    # edge, which is what was causing labels to sit on top of arrowheads/boxes
    max_value = max(dfg.values()) if dfg else 1
    for (source, target), value in dfg.items():
        label = str(value) if mode == "frequency" else _format_seconds(value)
        penwidth = 0.8 + 3.2 * (value / max_value)
        graph.edge(source, target, xlabel=label, penwidth=f"{penwidth:.2f}")

    return graph
