"""Train overview strip — horizontal pipeline with live KPIs."""

from dash import html
import dash_bootstrap_components as dbc


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
    return html.Div(
        html.Span("\u2794", style={"color": "#555", "fontSize": "1.2rem"}),
        style={"display": "flex", "alignItems": "center", "padding": "0 6px"},
    )


def train_overview_strip(num_stages: int):
    items = []
    for i in range(num_stages):
        items.append(_stage_box(i))
        if i < num_stages - 1:
            items.append(_arrow())
            items.append(_flash_box(i))
            items.append(_arrow())

    return html.Div(
        items,
        style={
            "display": "flex", "alignItems": "center",
            "overflowX": "auto", "padding": "12px",
            "backgroundColor": "#0a0a23", "borderRadius": "8px",
            "border": "1px solid #1a1a2e", "marginBottom": "12px",
        },
    )
