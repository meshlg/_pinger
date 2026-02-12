"""
Alert handler - processes alerts based on ping results.

Single Responsibility: Determine if alerts should be triggered and trigger them.
Integrated with SmartAlertManager for intelligent alert processing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from config import (
    ALERT_ON_HIGH_LATENCY,
    ALERT_ON_PACKET_LOSS,
    HIGH_LATENCY_THRESHOLD,
    ENABLE_AUTO_TRACEROUTE,
    TRACEROUTE_TRIGGER_LOSSES,
    # Smart alert settings
    ENABLE_SMART_ALERTS,
    t,
)

if TYPE_CHECKING:
    from stats_repository import StatsRepository
    from services import TracerouteService
    from .ping_handler import PingResult
    from .smart_alert_manager import SmartAlertManager


class AlertHandler:
    """
    Handles alert logic based on ping results.
    
    Single Responsibility: Process alerts and trigger appropriate actions.
    Optionally integrates with SmartAlertManager for intelligent processing.
    """
    
    def __init__(
        self,
        stats_repo: StatsRepository,
        traceroute_service: TracerouteService | None = None,
        smart_alert_manager: Optional[SmartAlertManager] = None,
    ) -> None:
        self.stats_repo = stats_repo
        self.traceroute_service = traceroute_service
        self.smart_alert_manager = smart_alert_manager
    
    def process_alerts(
        self,
        ping_result,
        high_latency_triggered: bool,
        packet_loss_triggered: bool,
    ) -> None:
        """
        Process alerts based on ping result and stats update.
        
        Uses SmartAlertManager if enabled, otherwise falls back to legacy behavior.
        
        Args:
            ping_result: Result from PingHandler
            high_latency_triggered: Whether high latency alert was triggered
            packet_loss_triggered: Whether packet loss alert was triggered
        """
        # Use smart alert system if enabled
        if ENABLE_SMART_ALERTS and self.smart_alert_manager:
            self._process_smart_alerts(ping_result, high_latency_triggered, packet_loss_triggered)
        else:
            # Legacy behavior
            self._process_legacy_alerts(high_latency_triggered, packet_loss_triggered)
    
    def _process_legacy_alerts(
        self,
        high_latency_triggered: bool,
        packet_loss_triggered: bool,
    ) -> None:
        """Legacy alert processing without smart features."""
        # Handle high latency alert
        if high_latency_triggered:
            self.stats_repo.trigger_alert_sound("high_latency")
        
        # Handle packet loss alert
        if packet_loss_triggered:
            self.stats_repo.trigger_alert_sound("loss")
            self._check_auto_traceroute()
    
    def _process_smart_alerts(
        self,
        ping_result,
        high_latency_triggered: bool,
        packet_loss_triggered: bool,
    ) -> None:
        """Smart alert processing with deduplication, grouping, and prioritization."""
        from .alert_types import AlertType, AlertContext, AlertPriority
        from .smart_alert_manager import AlertAction
        from config import TARGET_IP
        
        # Process high latency alert
        if high_latency_triggered and ping_result.latency:
            context = AlertContext(
                service="ping",
                component="latency",
                problem_type="performance",
                target=TARGET_IP,
            )
            
            should_trigger, alert = self.smart_alert_manager.should_trigger_alert(
                metric="latency",
                value=ping_result.latency,
                alert_type=AlertType.HIGH_LATENCY,
                context=context,
                message=t('alert_high_latency').format(val=ping_result.latency),
            )
            
            if should_trigger and alert:
                action, group = self.smart_alert_manager.process_alert(alert)
                
                # Only trigger sound/visual for non-suppressed alerts
                if action == AlertAction.NOTIFY:
                    self.stats_repo.trigger_alert_sound("high_latency")
                    if group:
                        self.stats_repo.add_alert(f"[!] {group.get_summary()}", "warning")
                elif action == AlertAction.GROUP and group and group.count == 1:
                    # First alert in group - show it
                    self.stats_repo.add_alert(f"[!] {alert.message}", "warning")
        
        # Process packet loss alert
        if packet_loss_triggered:
            context = AlertContext(
                service="ping",
                component="connectivity",
                problem_type="availability",
                target=TARGET_IP,
            )
            
            # Get loss percentage from recent results
            with self.stats_repo.lock:
                recent = self.stats_repo._recent_results
                if recent:
                    loss_pct = (recent.count(False) / len(recent)) * 100
                else:
                    loss_pct = 0.0
            
            should_trigger, alert = self.smart_alert_manager.should_trigger_alert(
                metric="packet_loss",
                value=loss_pct,
                alert_type=AlertType.PACKET_LOSS,
                context=context,
                message=t('alert_packet_loss').format(val=loss_pct),
            )
            
            if should_trigger and alert:
                action, group = self.smart_alert_manager.process_alert(alert)
                
                if action == AlertAction.NOTIFY or (action == AlertAction.GROUP and group and group.priority.value >= AlertPriority.HIGH.value):
                    self.stats_repo.trigger_alert_sound("loss")
                    if group:
                        self.stats_repo.add_alert(f"[!] {group.get_summary()}", "warning")
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
