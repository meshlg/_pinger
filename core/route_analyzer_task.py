"""Route analysis background task."""

from __future__ import annotations

import logging

from config import (
    ENABLE_ROUTE_ANALYSIS,
    ROUTE_ANALYSIS_INTERVAL,
    ROUTE_CHANGE_CONSECUTIVE,
    ROUTE_CHANGE_HOP_DIFF,
    ROUTE_IGNORE_FIRST_HOPS,
    ROUTE_SAVE_ON_CHANGE_CONSECUTIVE,
    TARGET_IP,
    t,
)
from alerts import add_visual_alert
from core.background_task import BackgroundTask
from infrastructure import METRICS_AVAILABLE, ROUTE_CHANGES_TOTAL, ROUTE_CHANGED_GAUGE
from route_analyzer import RouteAnalyzer
from services import TracerouteService


class RouteAnalyzerTask(BackgroundTask):
    """Periodically analyze network route and detect changes."""

    def __init__(
        self,
        *,
        route_analyzer: RouteAnalyzer,
        traceroute_service: TracerouteService,
        **kw,
    ) -> None:
        super().__init__(
            name="RouteAnalyzer",
            interval=ROUTE_ANALYSIS_INTERVAL,
            enabled=ENABLE_ROUTE_ANALYSIS,
            **kw,
        )
        self.route_analyzer = route_analyzer
        self.traceroute_service = traceroute_service

    async def execute(self) -> None:
        traceroute_output = await self.run_blocking(
            self.traceroute_service.run_traceroute,
            TARGET_IP,
        )

        hops = self.route_analyzer.parse_traceroute_output(traceroute_output)
        analysis = self.route_analyzer.analyze_route(hops)

        # Determine significant diffs
        diff_indices = analysis.get("diff_indices", [])
        significant_diffs = [i for i in diff_indices if i >= ROUTE_IGNORE_FIRST_HOPS]
        sig_count = len(significant_diffs)

        # Update hysteresis counters via repository
        is_significant = sig_count >= ROUTE_CHANGE_HOP_DIFF
        cons_changes, cons_ok = self.stats_repo.update_route_hysteresis(is_significant)

        # Update route status
        if cons_changes >= ROUTE_CHANGE_CONSECUTIVE:
            if not self.stats_repo.is_route_changed():
                self.stats_repo.set_route_changed(True)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[i] {t('route_changed')}",
                    "info",
                )
                if METRICS_AVAILABLE:
                    try:
                        ROUTE_CHANGES_TOTAL.inc()
                        ROUTE_CHANGED_GAUGE.set(1)
                    except Exception:
                        pass

                # Auto-trigger traceroute on route change
                if cons_changes >= ROUTE_SAVE_ON_CHANGE_CONSECUTIVE:
                    self.traceroute_service.trigger_traceroute(TARGET_IP)

        elif cons_ok >= ROUTE_CHANGE_CONSECUTIVE:
            if self.stats_repo.is_route_changed():
                self.stats_repo.set_route_changed(False)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[i] {t('route_stable')}",
                    "info",
                )
                if METRICS_AVAILABLE:
                    try:
                        ROUTE_CHANGED_GAUGE.set(0)
                    except Exception:
                        pass

        # Update route info
        self.stats_repo.update_route(
            hops,
            analysis["problematic_hop"],
            self.stats_repo.is_route_changed(),
            sig_count,
        )

        # Alert on problematic hop
        if analysis["problematic_hop"]:
            add_visual_alert(
                self.stats_repo.lock,
                self.stats_repo.get_stats(),
                f"[!] {t('problematic_hop')}: {analysis['problematic_hop']}",
                "warning",
            )
