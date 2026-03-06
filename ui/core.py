"""MonitorUI core class: constructor, tier detection, layout generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.layout import Layout

from ui.theme import HeightTier, LayoutTier
from ui.panels.header import render_header
from ui.panels.toast import render_toast
from ui.panels.dashboard import render_dashboard
from ui.panels.metrics import render_metrics_panel
from ui.panels.analysis import render_analysis_panel
from ui.panels.hops import render_hop_panel
from ui.panels.footer import render_footer

try:
    from config import UI_COMPACT_THRESHOLD, UI_WIDE_THRESHOLD
except ImportError:
    from ..config import UI_COMPACT_THRESHOLD, UI_WIDE_THRESHOLD  # type: ignore[no-redef]

# Import Protocol for DIP-compliant design
from ui_protocols.protocols import StatsDataProvider

if TYPE_CHECKING:
    from monitor import Monitor


class MonitorUI:
    """
    Adaptive Rich-based UI for network monitoring.

    Renders adaptively based on both terminal width AND height:
    Width tiers:
      - compact  (<100 cols): single column
      - standard (100–149):   two columns
      - wide     (≥150):      two columns + extended hop table
    Height tiers:
      - minimal  (<25 rows): status + essential data only
      - short    (25–39):    condensed panels
      - standard (40–54):    full panels
      - full     (≥55):      sparklines, progress bars, expanded details
    """

    def __init__(self, console: Console, data_provider: StatsDataProvider) -> None:
        self.console = console
        self._data_provider = data_provider
        self.monitor = data_provider
        self._cached_jitter: float = 0.0
        self._last_jitter_update: float = 0.0
        self._jitter_cache_interval: float = 5.0

    @property
    def data_provider(self) -> StatsDataProvider:
        return self._data_provider

    # ═══════════════════════════════════════════════════════════════════════════
    # Tier detection
    # ═══════════════════════════════════════════════════════════════════════════

    def _get_tier(self) -> LayoutTier:
        w = self.console.size.width
        if w < UI_COMPACT_THRESHOLD:
            return "compact"
        if w >= UI_WIDE_THRESHOLD:
            return "wide"
        return "standard"

    def _get_height_tier(self) -> HeightTier:
        h = self.console.size.height
        if h < 25:
            return "minimal"
        if h < 32:
            return "short"
        if h < 40:
            return "standard"
        return "full"

    # ═══════════════════════════════════════════════════════════════════════════
    # Layout generation — single snapshot, height-aware sizing
    # ═══════════════════════════════════════════════════════════════════════════

    def generate_layout(self) -> Layout:
        w = max(60, self.console.size.width)
        h = max(20, self.console.size.height)
        tier = self._get_tier()
        h_tier = self._get_height_tier()
        inner = w - 2

        # Single snapshot for entire render cycle
        snap = self.monitor.get_stats_snapshot()

        layout = Layout(name="root")

        header_panel = render_header(snap, w, tier)
        toast_panel = render_toast(snap, w)
        dashboard_panel = render_dashboard(snap, w, tier)
        footer_panel = render_footer(snap, w, tier)

        connection_lost = bool(snap.get("threshold_states", {}).get("connection_lost", False))
        hops = snap.get("hop_monitor_hops", [])
        if connection_lost:
            hops = []
        if h_tier == "minimal":
            hop_display_count = min(len(hops), 5)
        elif h_tier == "short":
            hop_display_count = min(len(hops), 8)
        else:
            hop_display_count = len(hops)

        toast_h = 3 if toast_panel else 0
        fixed_lines = 9 + toast_h
        remaining = h - fixed_lines

        hop_panel_h = hop_display_count + 5 if hops else 4
        hop_panel_h = min(hop_panel_h, max(4, remaining * 2 // 3))

        body_h = max(8, remaining - hop_panel_h)
        hop_panel = render_hop_panel(snap, w, tier, h_tier)

        splits = [Layout(header_panel, size=3, name="header")]
        if toast_panel:
            splits.append(Layout(toast_panel, size=3, name="toast"))
        splits.append(Layout(dashboard_panel, size=3, name="dashboard"))

        if tier == "compact":
            metrics_panel = render_metrics_panel(snap, w, tier, h_tier)
            analysis_panel = render_analysis_panel(snap, w, tier, h_tier)

            if h_tier == "minimal":
                splits.append(Layout(hop_panel, name="hops", ratio=1))
                splits.append(Layout(footer_panel, size=3, name="footer"))
                layout.split_column(*splits)
            else:
                body = Layout(name="body_inner")
                body.split_column(
                    Layout(metrics_panel, name="metrics", ratio=1),
                    Layout(analysis_panel, name="analysis", ratio=1),
                )
                splits.append(Layout(name="body", size=body_h))
                splits.append(Layout(hop_panel, name="hops", size=hop_panel_h))
                splits.append(Layout(footer_panel, size=3, name="footer"))
                layout.split_column(*splits)
                layout["body"].update(body)
        else:
            left_w = (inner // 2) - 1
            right_w = inner - left_w - 1

            metrics_panel = render_metrics_panel(snap, left_w, tier, h_tier)
            analysis_panel = render_analysis_panel(snap, right_w, tier, h_tier)

            body = Layout(name="body_inner")
            body.split_row(
                Layout(metrics_panel, name="metrics", ratio=1),
                Layout(analysis_panel, name="analysis", ratio=1),
            )

            splits.append(Layout(name="body", size=body_h))
            splits.append(Layout(hop_panel, name="hops", size=hop_panel_h))
            splits.append(Layout(footer_panel, size=3, name="footer"))
            layout.split_column(*splits)
            layout["body"].update(body)

        return layout


__all__ = ["MonitorUI"]
