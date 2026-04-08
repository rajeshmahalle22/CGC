"""Train-level Plotly charts."""

from __future__ import annotations
from typing import List, Optional
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from cgc_dashboard.engine.cgc_stage import StageResult
from cgc_dashboard.engine.flash_drum import FlashResult

_BG = "#0a0a23"
_LAYOUT = dict(
    template="plotly_dark", paper_bgcolor=_BG, plot_bgcolor=_BG,
    font=dict(size=11), margin=dict(l=60, r=40, t=40, b=40),
    height=320,
)


def efficiency_chart(results: List[StageResult]) -> go.Figure:
    """Bar chart of polytropic efficiency across stages."""
    stages = [f"Stage {i+1}" for i in range(len(results))]
    effs = [r.efficiency for r in results]
    colors = ["#ff4444" if e < 72 else "#ffa500" if e < 78 else "#00ff88"
              for e in effs]

    fig = go.Figure(go.Bar(x=stages, y=effs, marker_color=colors,
                           text=[f"{e:.1f}%" for e in effs],
                           textposition="outside"))
    fig.add_hrect(y0=72, y1=78, fillcolor="#ffa500", opacity=0.08,
                  line_width=0)
    fig.add_hrect(y0=78, y1=100, fillcolor="#00ff88", opacity=0.05,
                  line_width=0)
    fig.update_layout(**_LAYOUT, title="Polytropic Efficiency",
                      yaxis_title="%", yaxis_range=[60, 100])
    return fig


def pressure_temperature_chart(results: List[StageResult],
                                inputs: list) -> go.Figure:
    """Dual-axis P & T profile across stages."""
    n = len(results)
    stages = [f"Stage {i+1}" for i in range(n)]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    p_suc = [inp.P_suc for inp in inputs]
    p_dis = [inp.P_dis for inp in inputs]
    t_suc = [inp.T_suc for inp in inputs]
    t_dis_bfw = [r.T_dis_BFW for r in results]
    t_ac = [inp.T_AC_out for inp in inputs]

    fig.add_trace(go.Scatter(x=stages, y=p_suc, name="P_suc",
                              line=dict(color="#4ecdc4", dash="dot"),
                              mode="lines+markers"), secondary_y=False)
    fig.add_trace(go.Scatter(x=stages, y=p_dis, name="P_dis",
                              line=dict(color="#4ecdc4"),
                              mode="lines+markers"), secondary_y=False)
    fig.add_trace(go.Scatter(x=stages, y=t_suc, name="T_suc",
                              line=dict(color="#ffa500", dash="dot"),
                              mode="lines+markers"), secondary_y=True)
    fig.add_trace(go.Scatter(x=stages, y=t_dis_bfw, name="T_dis(BFW)",
                              line=dict(color="#ff6b6b"),
                              mode="lines+markers"), secondary_y=True)
    fig.add_trace(go.Scatter(x=stages, y=t_ac, name="T_AC_out",
                              line=dict(color="#00ff88", dash="dash"),
                              mode="lines+markers"), secondary_y=True)

    fig.update_layout(**_LAYOUT, title="Pressure & Temperature Profile")
    fig.update_yaxes(title_text="Pressure [kg/cm\u00b2]", secondary_y=False)
    fig.update_yaxes(title_text="Temperature [\u00b0C]", secondary_y=True)
    return fig


def condensate_chart(flash_results: List[Optional[FlashResult]]) -> go.Figure:
    """Stacked bar: vapor vs liquid per flash drum."""
    drums = []
    v_flows = []
    l_flows = []
    for i, f in enumerate(flash_results):
        if f is not None:
            drums.append(f"Flash {i+1}")
            v_flows.append(f.vapor_flow_kmolh)
            l_flows.append(f.liquid_flow_kmolh)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=drums, y=v_flows, name="Vapor",
                          marker_color="#ffa500"))
    fig.add_trace(go.Bar(x=drums, y=l_flows, name="Liquid",
                          marker_color="#4ecdc4"))
    fig.update_layout(**_LAYOUT, barmode="stack",
                      title="Condensate Knock-out per Flash Drum",
                      yaxis_title="Flow [kmol/h]")
    return fig


def fouling_chart(results: List[StageResult]) -> go.Figure:
    """Fouling index trend across stages."""
    stages = [f"Stage {i+1}" for i in range(len(results))]
    fouling = [r.fouling_index for r in results]

    fig = go.Figure(go.Scatter(
        x=stages, y=fouling, mode="lines+markers",
        line=dict(color="#ff6b6b", width=2),
        marker=dict(size=8),
        text=[f"{f:.2f}" for f in fouling],
        textposition="top center",
    ))
    fig.update_layout(**_LAYOUT, title="Fouling Index Trend",
                      yaxis_title="Fouling Index (10000/UA)")
    return fig


def power_chart(results: List[StageResult]) -> go.Figure:
    """Power per stage bar chart."""
    stages = [f"Stage {i+1}" for i in range(len(results))]
    powers = [r.power for r in results]

    fig = go.Figure(go.Bar(
        x=stages, y=powers, marker_color="#ff6b6b",
        text=[f"{p:.0f}" for p in powers], textposition="outside",
    ))
    fig.update_layout(**_LAYOUT, title="Shaft Power per Stage",
                      yaxis_title="Power [kW]")
    return fig
