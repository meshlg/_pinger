"""
Alert handler - processes alerts based on ping results.

Single Responsibility: Determine if alerts should be triggered and trigger them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config import (
    ALERT_ON_HIGH_LATENCY,
    ALERT_ON_PACKET_LOSS,
    HIGH_LATENCY_THRESHOLD,
    ENABLE_AUTO_TRACEROUTE,
    TRACEROUTE_TRIGGER_LOSSES,
)

from alerts import trigger_alert

if TYPE_CHECKING:
    from stats_repository import StatsRepository
    from services import TracerouteService
    from .ping_handler import PingResult


class AlertHandler:
    """
    Handles alert logic based on ping results.
    
    Single Responsibility: Process alerts and trigger appropriate actions.
    """
    
    def __init__(
        self,
        stats_repo: StatsRepository,
        traceroute_service: TracerouteService | None = None,
    ) -> None:
        self.stats_repo = stats_repo
        self.traceroute_service = traceroute_service
    
    def process_alerts(
        self,
        ping_result,
        high_latency_triggered: bool,
        packet_loss_triggered: bool,
    ) -> None:
        """
        Process alerts based on ping result and stats update.
        
        Args:
            ping_result: Result from PingHandler
            high_latency_triggered: Whether high latency alert was triggered
            packet_loss_triggered: Whether packet loss alert was triggered
        """
        # Handle high latency alert
        if high_latency_triggered:
            trigger_alert(
                self.stats_repo.lock,
                self.stats_repo.get_stats(),
                "high_latency"
            )
        
        # Handle packet loss alert
        if packet_loss_triggered:
            trigger_alert(
                self.stats_repo.lock,
                self.stats_repo.get_stats(),
                "loss"
            )
            self._check_auto_traceroute()
    
    def _check_auto_traceroute(self) -> None:
        """Trigger traceroute if conditions met."""
        if not ENABLE_AUTO_TRACEROUTE or not self.traceroute_service:
            return
        
        with self.stats_repo.lock:
            cons_losses = self.stats_repo.get_stats()["consecutive_losses"]
        
        if cons_losses >= TRACEROUTE_TRIGGER_LOSSES:
            from config import TARGET_IP
            self.traceroute_service.trigger_traceroute(TARGET_IP)
