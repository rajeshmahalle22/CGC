"""Dash application factory."""

import dash
import dash_bootstrap_components as dbc


def create_app() -> dash.Dash:
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.DARKLY],
        suppress_callback_exceptions=True,
        title="CGC Train Performance Monitor",
        update_title=None,
    )
    return app
