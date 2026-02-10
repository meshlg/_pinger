"""
Metrics handler - updates Prometheus metrics.

Single Responsibility: Update Prometheus metrics based on ping results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrastructure import (
    METRICS_AVAILABLE,
    PING_TOTAL,
    PING_SUCCESS,
    PING_FAILURE,
    PING_LATENCY_MS,
    PACKET_LOSS_GAUGE,
)

if TYPE_CHECKING:
    from stats_repository import StatsRepository
    from .ping_handler import PingResult


class MetricsHandler:
    """
    Handles Prometheus metrics updates.
    
    Single Responsibility: Update metrics based on ping results.
    """
    
    def __init__(self, stats_repo: StatsRepository) -> None:
        self.stats_repo = stats_repo
    
    def update_metrics(self, ping_result: PingResult) -> None:
        """
        Update Prometheus metrics after a ping.
        
        Args:
            ping_result: Result from PingHandler
        """
        if not METRICS_AVAILABLE:
            return
        
        try:
            # Increment total ping counter
            PING_TOTAL.inc()
            
            if ping_result.success:
                PING_SUCCESS.inc()
                if ping_result.latency is not None:
                    PING_LATENCY_MS.observe(ping_result.latency)
            else:
                PING_FAILURE.inc()
            
            # Update packet loss gauge
            snap = self.stats_repo.get_snapshot()
            if snap.get("recent_results"):
                loss_pct = snap["recent_results"].count(False) / len(snap["recent_results"]) * 100
                PACKET_LOSS_GAUGE.set(loss_pct)
        except Exception:
            # Silently ignore metrics errors
            pass
