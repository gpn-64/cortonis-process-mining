"""The headline callout at the top of the app -- the "why does this project exist"
banner. Always computed on the full event log, not the filtered one, since it's meant
to be the fixed headline finding (Lyon), not something that should change or break
if someone filters Lyon out of the sidebar.
"""

import streamlit as st

from src import kpi


@st.cache_data
def _lyon_vs_network_stats(df):
    step = kpi.step_durations(df)
    lyon_step = step.loc[step["site"] == "Lyon", "duration_hours"].mean()
    rest_step = step.loc[step["site"] != "Lyon", "duration_hours"].mean()
    step_delta_pct = (lyon_step - rest_step) / rest_step * 100

    cycle = kpi.case_cycle_time(df)
    lyon_cycle = cycle.loc[cycle["site"] == "Lyon", "cycle_time_days"].mean()
    rest_cycle = cycle.loc[cycle["site"] != "Lyon", "cycle_time_days"].mean()
    cycle_delta_pct = (lyon_cycle - rest_cycle) / rest_cycle * 100

    rework = kpi.rework_time(df)
    has_rework = rework["rework_time_days"] > 0
    lyon_rework_rate = has_rework[rework["site"] == "Lyon"].mean()
    rest_rework_rate = has_rework[rework["site"] != "Lyon"].mean()
    rework_ratio = lyon_rework_rate / rest_rework_rate

    return step_delta_pct, cycle_delta_pct, rework_ratio


def _stat_block(value, label):
    return f"""
        <div style="text-align:center;min-width:76px;">
            <div style="font-size:19px;font-weight:700;font-family:'Courier New',monospace;">{value}</div>
            <div style="font-size:10px;opacity:.78;margin-top:5px;line-height:1.3;">{label}</div>
        </div>
    """


def render(df):
    step_delta_pct, cycle_delta_pct, rework_ratio = _lyon_vs_network_stats(df)

    divider = '<div style="width:1px;align-self:stretch;background:rgba(255,255,255,.25);"></div>'
    stats = "".join([
        _stat_block(f"{step_delta_pct:+.0f}%", "step duration<br>delta"),
        divider,
        _stat_block(f"{cycle_delta_pct:+.0f}%", "cycle time<br>vs. network"),
        divider,
        _stat_block(f"{rework_ratio:.1f}×", "rework rate<br>vs. network"),
    ])

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(120deg, #0B5D3B 0%, #0F7A4C 100%);
            border-radius: 14px;
            padding: 24px 30px;
            color: #fff;
            margin-bottom: 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 36px;
        ">
            <div>
                <div style="font-size:10.5px;font-weight:700;letter-spacing:.1em;
                    text-transform:uppercase;opacity:.72;margin-bottom:9px;">The finding</div>
                <p style="font-size:16px;font-weight:500;line-height:1.5;margin:0;max-width:640px;color:#fff;">
                    Lyon's average step duration is <b>in line with the network</b>
                    ({step_delta_pct:+.0f}%). Its CAPA cycle time is
                    <b>{cycle_delta_pct:+.0f}% longer</b>. Standard reporting can't
                    explain the gap -- process mining can.
                </p>
            </div>
            <div style="display:flex;gap:26px;flex:none;">{stats}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
