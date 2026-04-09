"""Full page layout for the CGC dashboard.

IMPORTANT: Always renders MAX_STAGES stage panels (some hidden) so that
all callback Output IDs exist in the DOM regardless of current stage count.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc

from cgc_dashboard.dashboard.components.stage_panel import stage_accordion_item
from cgc_dashboard.dashboard.components.train_overview import train_overview_strip

MAX_STAGES = 6


def build_layout(num_stages: int = 4):
    # Build ALL stage accordion items — hide extras via display:none wrapper
    all_stage_items = []
    for i in range(MAX_STAGES):
        visible = i < num_stages
        item = html.Div(
            stage_accordion_item(i, MAX_STAGES),
            id=f"stage-wrapper-{i}",
            style={"display": "block"} if visible else {"display": "none"},
        )
        all_stage_items.append(item)

    return dbc.Container([
        # Hidden stores
        dcc.Store(id="calc-results-store", data=None),
        dcc.Store(id="current-num-stages", data=num_stages),

        # ── TOP BAR ─────────────────────────────────────────────
        dbc.Navbar(
            dbc.Container([
                dbc.Row([
                    dbc.Col(
                        html.H4("CGC TRAIN PERFORMANCE MONITOR",
                                style={"color": "#ffa500", "fontFamily": "monospace",
                                       "margin": "0", "letterSpacing": "2px"}),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Row([
                            dbc.Col([
                                html.Label("Stages:", style={"color": "#aaa",
                                           "fontSize": "0.75rem", "marginRight": "4px"}),
                                dbc.Select(
                                    id="num-stages-select",
                                    options=[{"label": str(i), "value": i}
                                             for i in range(2, MAX_STAGES + 1)],
                                    value=num_stages,
                                    style={"width": "70px", "display": "inline-block",
                                           "backgroundColor": "#1a1a2e", "color": "#e0e0e0",
                                           "border": "1px solid #333", "fontSize": "0.85rem"},
                                ),
                            ], width="auto", className="d-flex align-items-center me-3"),
                            dbc.Col([
                                html.Label("DTL Path:", style={"color": "#aaa",
                                           "fontSize": "0.75rem", "marginRight": "4px"}),
                                dbc.Input(
                                    id="dtl-path-input",
                                    placeholder="C:\\DWSIM\\",
                                    size="sm",
                                    style={"width": "200px", "backgroundColor": "#1a1a2e",
                                           "color": "#e0e0e0", "border": "1px solid #333"},
                                ),
                                html.Span(id="dtl-status", children="\u26ab",
                                          style={"marginLeft": "6px", "fontSize": "1rem"}),
                            ], width="auto", className="d-flex align-items-center me-3"),
                            dbc.Col(
                                dbc.Button("CALCULATE ALL STAGES",
                                           id="calc-btn", color="warning",
                                           size="sm", className="me-2",
                                           style={"fontWeight": "bold"}),
                                width="auto",
                            ),
                            dbc.Col(
                                dbc.Button("EXPORT EXCEL", id="export-btn",
                                           color="info", size="sm", outline=True),
                                width="auto",
                            ),
                            dbc.Col(
                                dbc.Button("LOAD DEFAULTS", id="load-defaults-btn",
                                           color="secondary", size="sm", outline=True),
                                width="auto", className="ms-2",
                            ),
                        ], className="g-0 align-items-center"),
                        width=True,
                    ),
                    dbc.Col(
                        html.Div(id="calc-timestamp",
                                 style={"color": "#666", "fontSize": "0.7rem",
                                        "textAlign": "right"}),
                        width="auto",
                    ),
                ], className="w-100 align-items-center"),
            ], fluid=True),
            color="#0a0a23",
            dark=True,
            style={"borderBottom": "2px solid #0f3460", "padding": "8px 0"},
        ),

        # Error banner
        html.Div(id="error-banner", style={"display": "none"}),

        # ── TRAIN OVERVIEW STRIP ────────────────────────────────
        html.Div(id="train-overview-container",
                 children=train_overview_strip(num_stages),
                 style={"marginTop": "10px"}),

        # ── PER-STAGE PANELS (all MAX_STAGES rendered, extras hidden) ──
        html.Div(
            id="stages-accordion-container",
            children=all_stage_items,
            style={"marginTop": "10px"},
        ),

        # ── TRAIN CHARTS ────────────────────────────────────────
        html.Div(id="train-charts-container", children=[
            html.H5("TRAIN ANALYTICS",
                     style={"color": "#ffa500", "marginTop": "20px",
                            "fontFamily": "monospace"}),
            dbc.Row([
                dbc.Col(dcc.Graph(id="chart-efficiency",
                                   config={"displayModeBar": False}), md=6),
                dbc.Col(dcc.Graph(id="chart-pt-profile",
                                   config={"displayModeBar": False}), md=6),
            ]),
            dbc.Row([
                dbc.Col(dcc.Graph(id="chart-condensate",
                                   config={"displayModeBar": False}), md=6),
                dbc.Col(dcc.Graph(id="chart-fouling",
                                   config={"displayModeBar": False}), md=6),
            ]),
        ]),

        # ── MATERIAL BALANCE TABLE ──────────────────────────────
        html.Div(id="material-balance-container", children=[
            html.H5("MATERIAL BALANCE",
                     style={"color": "#ffa500", "marginTop": "20px",
                            "fontFamily": "monospace"}),
            html.Div(id="material-balance-table"),
        ], style={"marginBottom": "40px"}),

        # Download component
        dcc.Download(id="download-excel"),

    ], fluid=True, style={
        "backgroundColor": "#0a0a23", "minHeight": "100vh",
        "color": "#e0e0e0", "fontFamily": "'Segoe UI', sans-serif",
    })
