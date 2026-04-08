"""CGC Train Performance Monitor — Entry Point."""

from cgc_dashboard.dashboard.app import create_app
from cgc_dashboard.dashboard.layout import build_layout
from cgc_dashboard.dashboard.callbacks import register_callbacks

app = create_app()
app.layout = build_layout(num_stages=4)
register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
