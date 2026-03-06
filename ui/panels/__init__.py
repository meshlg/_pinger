"""Panel rendering functions for the monitoring UI."""

from ui.panels.header import render_header
from ui.panels.toast import render_toast
from ui.panels.dashboard import render_dashboard
from ui.panels.metrics import render_metrics_panel
from ui.panels.analysis import render_analysis_panel
from ui.panels.hops import render_hop_panel
from ui.panels.footer import render_footer

__all__ = [
    "render_header",
    "render_toast",
    "render_dashboard",
    "render_metrics_panel",
    "render_analysis_panel",
    "render_hop_panel",
    "render_footer",
]
