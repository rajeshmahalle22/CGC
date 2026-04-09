"""Flash drum result panel builder."""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from cgc_dashboard.engine.constants import COMPONENTS
from cgc_dashboard.engine.flash_drum import FlashResult


def build_flash_content(flash: FlashResult, stage_idx: int):
    """Build the flash drum results panel content."""
    if flash is None:
        return html.P("No flash drum for this stage.",
                       style={"color": "#666", "textAlign": "center"})

    if flash.error:
        return html.Div([
            html.P(f"Flash calculation error: {flash.error}",
                   style={"color": "#ff6b6b"}),
            html.P("DTL may not be available. CGC results are still valid.",
                   style={"color": "#888"}),
        ])

    approx_badge = ""
    if flash.is_approximate:
        approx_badge = dbc.Badge("APPROXIMATE (Raoult's Law)",
                                  color="warning", className="mb-2")

    # Conditions card
    conditions = dbc.Card([
        dbc.CardBody([
            html.H6("Flash Conditions", style={"color": "#4ecdc4"}),
            html.Div([
                html.Span(f"T = {flash.T_flash:.2f} C", style={"marginRight": "20px"}),
                html.Span(f"P = {flash.P_flash_kgcm2:.3f} kg/cm\u00b2"),
            ], style={"color": "#ccc", "fontFamily": "monospace"}),
        ])
    ], style={"backgroundColor": "#16213e", "border": "1px solid #0f3460",
              "marginBottom": "8px"})

    # Phase split
    phase_split = dbc.Card([
        dbc.CardBody([
            html.H6("Phase Split", style={"color": "#4ecdc4"}),
            dbc.Row([
                dbc.Col([
                    html.P("Vapor Fraction", style={"color": "#888", "fontSize": "0.75rem", "marginBottom": "0"}),
                    html.H4(f"{flash.vapor_fraction:.6f}",
                             style={"color": "#ffa500", "fontFamily": "monospace"}),
                    html.Small(f"{flash.vapor_flow_kmolh:.1f} kmol/h | {flash.vapor_flow_kgh:.0f} kg/h",
                               style={"color": "#aaa"}),
                ], md=6),
                dbc.Col([
                    html.P("Liquid Fraction", style={"color": "#888", "fontSize": "0.75rem", "marginBottom": "0"}),
                    html.H4(f"{flash.liquid_fraction:.6f}",
                             style={"color": "#4ecdc4", "fontFamily": "monospace"}),
                    html.Small(f"{flash.liquid_flow_kmolh:.1f} kmol/h | {flash.liquid_flow_kgh:.0f} kg/h",
                               style={"color": "#aaa"}),
                ], md=6),
            ])
        ])
    ], style={"backgroundColor": "#16213e", "border": "1px solid #0f3460",
              "marginBottom": "8px"})

    # Composition table
    all_comps = COMPONENTS + ["Water"]
    comp_rows = []
    for c in all_comps:
        yi = flash.y.get(c, 0.0)
        xi = flash.x.get(c, 0.0)
        ki = flash.K_values.get(c, 0.0)
        v_flow = yi * flash.vapor_flow_kmolh
        l_flow = xi * flash.liquid_flow_kmolh
        comp_rows.append(html.Tr([
            html.Td(c, style={"color": "#ccc"}),
            html.Td(f"{yi:.6f}", style={"color": "#ffa500", "fontFamily": "monospace"}),
            html.Td(f"{xi:.6f}", style={"color": "#4ecdc4", "fontFamily": "monospace"}),
            html.Td(f"{ki:.4f}" if ki < 1e6 else "INF",
                     style={"color": "#fff", "fontFamily": "monospace"}),
            html.Td(f"{v_flow:.2f}", style={"fontFamily": "monospace", "color": "#ccc"}),
            html.Td(f"{l_flow:.2f}", style={"fontFamily": "monospace", "color": "#ccc"}),
        ]))

    comp_table = dbc.Table([
        html.Thead(html.Tr([
            html.Th("Component"), html.Th("y (vapor)"), html.Th("x (liquid)"),
            html.Th("K = y/x"), html.Th("V [kmol/h]"), html.Th("L [kmol/h]"),
        ], style={"color": "#ffa500"})),
        html.Tbody(comp_rows),
    ], bordered=True, color="dark", hover=True, size="sm",
       style={"fontSize": "0.75rem"})

    # K-value bar chart
    k_comps = [c for c in all_comps if flash.K_values.get(c, 0.0) > 0
               and flash.K_values.get(c, 0.0) < 1e6]
    k_vals = [flash.K_values[c] for c in k_comps]
    colors = ["#ffa500" if k > 1 else "#4ecdc4" for k in k_vals]

    fig = go.Figure(go.Bar(
        x=k_vals, y=k_comps, orientation="h",
        marker_color=colors,
        text=[f"{k:.3f}" for k in k_vals],
        textposition="outside",
    ))
    fig.add_vline(x=1.0, line_dash="dash", line_color="#fff", opacity=0.5)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0a0a23",
        plot_bgcolor="#0a0a23",
        height=max(250, len(k_comps) * 25),
        margin=dict(l=80, r=60, t=30, b=30),
        xaxis_title="K-value",
        font=dict(size=11),
    )

    return html.Div([
        approx_badge if approx_badge else html.Div(),
        conditions,
        phase_split,
        html.H6("Composition Table", style={"color": "#4ecdc4", "marginTop": "10px"}),
        comp_table,
        html.H6("K-value Chart", style={"color": "#4ecdc4", "marginTop": "10px"}),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
    ])
