"""MonitorUI core class: constructor, tier detection, layout generation."""

from __future__ import annotations

from rich.console import Console
from rich.layout import Layout

from ui.theme import HeightTier, LayoutTier
from ui.panels.analysis import render_analysis_panel
from ui.panels.dashboard import render_dashboard
from ui.panels.footer import render_footer
from ui.panels.header import render_header
from ui.panels.hops import render_hop_panel
from ui.panels.metrics import render_metrics_panel
from ui.panels.toast import render_toast

try:
    from config import UI_COMPACT_THRESHOLD, UI_WIDE_THRESHOLD
except ImportError:
    from ..config import UI_COMPACT_THRESHOLD, UI_WIDE_THRESHOLD  # type: ignore[no-redef]

from ui_protocols.protocols import StatsDataProvider


class MonitorUI:
    """Adaptive Rich-based UI for network monitoring."""

    def __init__(self, console: Console, data_provider: StatsDataProvider) -> None:
        self.console = console
        self._data_provider = data_provider
        self._cached_jitter: float = 0.0
        self._last_jitter_update: float = 0.0
        self._jitter_cache_interval: float = 5.0

    @property
    def data_provider(self) -> StatsDataProvider:
        return self._data_provider

    def _get_tier(self) -> LayoutTier:
        width = self.console.size.width
        if width < UI_COMPACT_THRESHOLD:
            return "compact"
        if width >= UI_WIDE_THRESHOLD:
            return "wide"
        return "standard"

    def _get_height_tier(self) -> HeightTier:
        height = self.console.size.height
        if height < 25:
            return "minimal"
        if height < 32:
            return "short"
        if height < 40:
            return "standard"
        return "full"

    def generate_layout(self) -> Layout:
        width = max(60, self.console.size.width)
        height = max(20, self.console.size.height)
        tier = self._get_tier()
        h_tier = self._get_height_tier()
        inner = width - 2

        snap = self._data_provider.get_stats_snapshot()
        layout = Layout(name="root")

        header_panel = render_header(snap, width, tier)
        toast_panel = render_toast(snap, width)
        dashboard_panel = render_dashboard(snap, width, tier)
        footer_panel = render_footer(snap, width, tier)

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

        header_h = 3 if tier == "compact" else 4
        dashboard_h = 3 if tier == "compact" else 4
        toast_h = 3 if toast_panel else 0
        footer_h = 3
        fixed_lines = header_h + dashboard_h + footer_h + toast_h
        remaining = height - fixed_lines

        hop_panel_h = hop_display_count + 5 if hops else 4
        hop_panel_h = min(hop_panel_h, max(4, remaining * 2 // 3))
        body_h = max(8, remaining - hop_panel_h)
        hop_panel = render_hop_panel(snap, width, tier, h_tier)

        splits = [Layout(header_panel, size=header_h, name="header")]
        if toast_panel:
            splits.append(Layout(toast_panel, size=toast_h, name="toast"))
        splits.append(Layout(dashboard_panel, size=dashboard_h, name="dashboard"))

        if tier == "compact":
            metrics_panel = render_metrics_panel(snap, width, tier, h_tier)
            analysis_panel = render_analysis_panel(snap, width, tier, h_tier)

            if h_tier == "minimal":
                splits.append(Layout(hop_panel, name="hops", ratio=1))
                splits.append(Layout(footer_panel, size=footer_h, name="footer"))
                layout.split_column(*splits)
            else:
                body = Layout(name="body_inner")
                body.split_column(
                    Layout(metrics_panel, name="metrics", ratio=1),
                    Layout(analysis_panel, name="analysis", ratio=1),
                )
                splits.append(Layout(name="body", size=body_h))
                splits.append(Layout(hop_panel, name="hops", size=hop_panel_h))
                splits.append(Layout(footer_panel, size=footer_h, name="footer"))
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
            splits.append(Layout(footer_panel, size=footer_h, name="footer"))
            layout.split_column(*splits)
            layout["body"].update(body)

        return layout


__all__ = ["MonitorUI"]
