"""Train overview strip — horizontal pipeline with live KPIs.

Always renders MAX_STAGES boxes so callback IDs exist. Hidden stages
are controlled via the wrapper divs.
"""

from dash import html
import dash_bootstrap_components as dbc

MAX_STAGES = 6


def _stage_box(idx: int):
    return html.Div([
        html.Div(f"STAGE {idx+1}", style={
            "color": "#ffa500", "fontWeight": "bold",
            "fontSize": "0.75rem", "marginBottom": "4px",
        }),
        html.Div(id=f"overview-eff-{idx}", children="Eff: —",
                 style={"fontSize": "0.7rem", "color": "#ccc"}),
        html.Div(id=f"overview-power-{idx}", children="Pwr: —",
                 style={"fontSize": "0.7rem", "color": "#ccc"}),
        html.Div(id=f"overview-pratio-{idx}", children="PR: —",
                 style={"fontSize": "0.7rem", "color": "#ccc"}),
    ], style={
        "backgroundColor": "#16213e", "border": "2px solid #0f3460",
        "borderRadius": "8px", "padding": "8px 14px",
        "minWidth": "120px", "textAlign": "center",
    }, id=f"overview-box-{idx}")


def _flash_box(idx: int):
    return html.Div([
        html.Div(f"FLASH {idx+1}", style={
            "color": "#4ecdc4", "fontWeight": "bold",
            "fontSize": "0.7rem", "marginBottom": "2px",
        }),
        html.Div(id=f"overview-vf-{idx}", children="V: —",
                 style={"fontSize": "0.65rem", "color": "#aaa"}),
        html.Div(id=f"overview-liq-{idx}", children="L: —",
                 style={"fontSize": "0.65rem", "color": "#aaa"}),
    ], style={
        "backgroundColor": "#1a1a2e", "border": "1px solid #4ecdc4",
        "borderRadius": "6px", "padding": "6px 10px",
        "minWidth": "90px", "textAlign": "center",
    })


def _arrow():
    return html.Span("\u2794", style={"color": "#555", "fontSize": "1.2rem",
                                       "padding": "0 6px"})


def train_overview_strip(num_stages: int):
    """Build the overview strip. Always includes all MAX_STAGES elements
    with extras hidden."""
    items = []
    for i in range(MAX_STAGES):
        visible = i < num_stages
        # Stage box
        items.append(html.Div(
            _stage_box(i),
            id=f"overview-stage-wrap-{i}",
            style={"display": "inline-flex", "alignItems": "center"}
            if visible else {"display": "none"},
        ))
        # Flash + arrows between stages
        if i < MAX_STAGES - 1:
            flash_visible = i < num_stages - 1
            items.append(html.Div(
                [_arrow(), _flash_box(i), _arrow()],
                id=f"overview-flash-wrap-{i}",
                style={"display": "inline-flex", "alignItems": "center"}
                if flash_visible else {"display": "none"},
            ))

    return html.Div(
        items,
        style={
            "display": "flex", "alignItems": "center",
            "overflowX": "auto", "padding": "12px",
            "backgroundColor": "#0a0a23", "borderRadius": "8px",
            "border": "1px solid #1a1a2e", "marginBottom": "12px",
        },
    )
