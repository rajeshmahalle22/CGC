"""Per-stage accordion panel — inputs tab, KPI tab, flash tab."""

from __future__ import annotations
from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
from cgc_dashboard.engine.constants import COMPONENTS


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

LABEL_STYLE = {"color": "#aaa", "fontSize": "0.75rem", "marginBottom": "2px"}
INPUT_STYLE = {
    "backgroundColor": "#1a1a2e", "color": "#e0e0e0",
    "border": "1px solid #333", "borderRadius": "3px",
    "fontSize": "0.85rem",
}
CARD_STYLE = {
    "backgroundColor": "#16213e", "border": "1px solid #0f3460",
    "borderRadius": "6px", "padding": "10px", "marginBottom": "8px",
}
SECTION_STYLE = {"marginBottom": "12px"}


def _input_field(label, id_str, value=0.0, step="any"):
    return dbc.Col([
        html.Label(label, style=LABEL_STYLE),
        dbc.Input(id=id_str, type="number", value=value, step=step,
                  size="sm", style=INPUT_STYLE, debounce=True),
    ], md=3, sm=6, className="mb-2")


def _toggle(label, id_str, value=False):
    return dbc.Col([
        dbc.Checklist(
            id=id_str,
            options=[{"label": f"  {label}", "value": 1}],
            value=[1] if value else [],
            switch=True,
            style={"color": "#e0e0e0", "fontSize": "0.8rem"},
        ),
    ], md=3, sm=6, className="mb-1")


# ---------------------------------------------------------------------------
# QO Composition sub-table
# ---------------------------------------------------------------------------

def _qo_comp_row(stage_idx):
    rows = []
    for c in COMPONENTS:
        rows.append(
            dbc.Col([
                html.Label(c, style={**LABEL_STYLE, "fontSize": "0.7rem"}),
                dbc.Input(
                    id={"type": "qo-mf", "stage": stage_idx, "comp": c},
                    type="number", value=0.0, step="any", size="sm",
                    style={**INPUT_STYLE, "fontSize": "0.75rem"},
                    debounce=True,
                ),
            ], md=2, sm=3, xs=4, className="mb-1")
        )
    return dbc.Row(rows)


# ---------------------------------------------------------------------------
# Inputs Tab
# ---------------------------------------------------------------------------

def inputs_tab(stage_idx: int, num_stages: int):
    is_last = stage_idx == num_stages - 1

    sections = []

    # Stream control toggles
    sections.append(html.Div([
        html.H6("Stream Control", style={"color": "#ffa500", "marginBottom": "6px"}),
        dbc.Row([
            _toggle("Recycle Gas", f"rcy-active-{stage_idx}"),
            _toggle("AS1", f"as1-active-{stage_idx}"),
            _toggle("AS2", f"as2-active-{stage_idx}"),
            _toggle("AS3", f"as3-active-{stage_idx}"),
            _toggle("BFW Injection", f"bfw-active-{stage_idx}", True),
            _toggle("Wash Oil", f"wo-active-{stage_idx}"),
        ]),
    ], style=CARD_STYLE))

    # Stage conditions
    sections.append(html.Div([
        html.H6("Stage Conditions", style={"color": "#ffa500", "marginBottom": "6px"}),
        dbc.Row([
            _input_field("T_suc [C]", f"T-suc-{stage_idx}"),
            _input_field("P_suc [kg/cm2]", f"P-suc-{stage_idx}"),
            _input_field("T_dis [C]", f"T-dis-{stage_idx}"),
            _input_field("P_dis [kg/cm2]", f"P-dis-{stage_idx}"),
        ]),
        dbc.Row([
            _input_field("T_AC_out [C]", f"T-ac-{stage_idx}"),
            _input_field("Water MF", f"water-mf-{stage_idx}", step="0.0001"),
            _input_field("BFW Flow [kg/h]", f"bfw-flow-{stage_idx}"),
            _input_field("WO Flow [kg/h]", f"wo-flow-{stage_idx}"),
        ]),
        dbc.Row([
            _input_field("WO Molar [kmol/h]", f"wo-molar-{stage_idx}"),
        ]),
    ], style=CARD_STYLE))

    # Flow linkage
    sections.append(html.Div([
        html.H6("Flow Linkage", style={"color": "#ffa500", "marginBottom": "6px"}),
        dbc.Row([
            _input_field("Prev Dry Flow [kg/h]", f"prev-dry-{stage_idx}"),
            _input_field("Prev Water MF", f"prev-wmf-{stage_idx}", step="0.0001"),
            _input_field("Prev BFW [kg/h]", f"prev-bfw-{stage_idx}"),
            _input_field("Prev WO [kg/h]", f"prev-wo-{stage_idx}"),
        ]),
        dbc.Row([
            _input_field("Next Dry Flow [kg/h]", f"next-dry-{stage_idx}"),
            _input_field("Next Suc P [kg/cm2]", f"next-suc-p-{stage_idx}"),
            _input_field("Next Suc T [C]", f"next-suc-t-{stage_idx}"),
        ]),
    ], style=CARD_STYLE))

    # QO Composition
    sections.append(html.Div([
        html.H6("QO Component Mass Fractions", style={"color": "#ffa500", "marginBottom": "6px"}),
        dbc.Checklist(
            id=f"auto-fill-flash-{stage_idx}",
            options=[{"label": "  Auto-fill from Flash", "value": 1}],
            value=[1] if stage_idx > 0 else [],
            switch=True,
            style={"color": "#e0e0e0", "fontSize": "0.8rem", "marginBottom": "6px"},
        ),
        _qo_comp_row(stage_idx),
    ], style=CARD_STYLE))

    # AS1 inputs
    sections.append(html.Div(id=f"as1-panel-{stage_idx}", children=[
        html.H6("Additional Stream 1 (AS1)", style={"color": "#ffa500", "marginBottom": "6px"}),
        dbc.Row([
            _toggle("C3-Analyser Mode", f"as1-analyser-{stage_idx}", True),
        ]),
        dbc.Row([
            _input_field("Feed Flow [t/h]", f"as1-feed-{stage_idx}"),
            _input_field("Bottom Flow [t/h]", f"as1-bottom-{stage_idx}"),
            _input_field("C3 Analyser [%]", f"as1-c3-{stage_idx}"),
            _input_field("Direct Flow [kg/h]", f"as1-direct-{stage_idx}"),
        ]),
    ], style={**CARD_STYLE, "display": "none"}))

    # Flash drum (hidden for last stage)
    if not is_last:
        sections.append(html.Div([
            html.H6("Flash Drum", style={"color": "#ffa500", "marginBottom": "6px"}),
            dbc.Row([
                _input_field("Drum dP [kg/cm2]", f"flash-dp-{stage_idx}", value=0.3),
            ]),
        ], style=CARD_STYLE))

    return dbc.Tab(
        html.Div(sections, style={"padding": "10px"}),
        label="Inputs",
        tab_style={"backgroundColor": "#0f3460"},
        active_label_style={"backgroundColor": "#ffa500", "color": "#000"},
    )


# ---------------------------------------------------------------------------
# KPI Tab
# ---------------------------------------------------------------------------

def _kpi_card(title, id_str, unit="", color="#ffa500"):
    return dbc.Col(
        dbc.Card([
            dbc.CardBody([
                html.P(title, style={"color": "#999", "fontSize": "0.7rem",
                                     "marginBottom": "2px"}),
                html.H5(id=id_str, children="—",
                         style={"color": color, "fontFamily": "monospace",
                                "marginBottom": "0"}),
                html.Small(unit, style={"color": "#666"}),
            ], style={"padding": "8px"}),
        ], style={"backgroundColor": "#16213e", "border": "1px solid #0f3460"}),
        md=3, sm=6, className="mb-2",
    )


def kpi_tab(stage_idx: int):
    cards = dbc.Row([
        _kpi_card("Pressure Ratio", f"kpi-pratio-{stage_idx}", "—"),
        _kpi_card("Efficiency", f"kpi-eff-{stage_idx}", "%", "#00ff88"),
        _kpi_card("T_dis (BFW corr)", f"kpi-tdis-{stage_idx}", "C"),
        _kpi_card("Polytropic Head", f"kpi-head-{stage_idx}", "J/kg"),
        _kpi_card("Shaft Power", f"kpi-power-{stage_idx}", "kW", "#ff6b6b"),
        _kpi_card("Molecular Weight", f"kpi-mw-{stage_idx}", "kg/kmol"),
        _kpi_card("AC Duty", f"kpi-acduty-{stage_idx}", "kW", "#4ecdc4"),
        _kpi_card("Fouling Index", f"kpi-fouling-{stage_idx}", "—"),
        _kpi_card("Hot Approach", f"kpi-hotapp-{stage_idx}", "C"),
        _kpi_card("UA", f"kpi-ua-{stage_idx}", "kW/C"),
        _kpi_card("Vol Suc", f"kpi-volsuc-{stage_idx}", "m3/h"),
        _kpi_card("Vol Dis", f"kpi-voldis-{stage_idx}", "m3/h"),
        _kpi_card("AC dP", f"kpi-acdp-{stage_idx}", "kg/cm2"),
        _kpi_card("Norm AC dP", f"kpi-normdp-{stage_idx}", "—"),
        _kpi_card("Fouling dP %", f"kpi-fouldp-{stage_idx}", "%"),
        _kpi_card("MW (no BFW)", f"kpi-mwnobfw-{stage_idx}", "kg/kmol"),
    ])

    # Intermediate values table
    detail_table = html.Div([
        html.Hr(style={"borderColor": "#333"}),
        html.H6("Intermediate Calculations", style={"color": "#ffa500"}),
        html.Div(id=f"detail-table-{stage_idx}"),
    ])

    return dbc.Tab(
        html.Div([cards, detail_table], style={"padding": "10px"}),
        label="CGC KPIs",
        tab_style={"backgroundColor": "#0f3460"},
        active_label_style={"backgroundColor": "#ffa500", "color": "#000"},
    )


# ---------------------------------------------------------------------------
# Flash Results Tab
# ---------------------------------------------------------------------------

def flash_tab(stage_idx: int, num_stages: int):
    is_last = stage_idx == num_stages - 1
    if is_last:
        content = html.Div([
            html.P("No flash drum for the last stage.",
                   style={"color": "#666", "textAlign": "center", "padding": "40px"})
        ])
    else:
        content = html.Div(id=f"flash-content-{stage_idx}", children=[
            html.P("Run calculation to see flash drum results.",
                   style={"color": "#666", "textAlign": "center", "padding": "40px"})
        ])

    return dbc.Tab(
        html.Div(content, style={"padding": "10px"}),
        label="Flash Drum",
        tab_style={"backgroundColor": "#0f3460"},
        active_label_style={"backgroundColor": "#ffa500", "color": "#000"},
    )


# ---------------------------------------------------------------------------
# Full Stage Accordion Item
# ---------------------------------------------------------------------------

def stage_accordion_item(stage_idx: int, num_stages: int):
    return dbc.AccordionItem(
        dbc.Tabs([
            inputs_tab(stage_idx, num_stages),
            kpi_tab(stage_idx),
            flash_tab(stage_idx, num_stages),
        ], id=f"stage-tabs-{stage_idx}"),
        title=f"STAGE {stage_idx + 1}",
        style={"backgroundColor": "#0a0a23"},
    )
