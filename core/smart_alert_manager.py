"""
Smart Alert Manager - Central coordinator for intelligent alert system.

Integrates deduplication, grouping, prioritization, and adaptive thresholds
with rate limiting and noise reduction.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from config import ADAPTIVE_ANOMALY_SIGMA, ADAPTIVE_BASELINE_WINDOW_HOURS, ADAPTIVE_UPDATE_INTERVAL_MINUTES
from core.adaptive_thresholds import AdaptiveThresholds
from core.alert_deduplicator import AlertDeduplicator
from core.alert_grouper import AlertGrouper
from core.alert_prioritizer import AlertPrioritizer
from core.alert_types import AlertContext, AlertEntity, AlertGroup, AlertHistory, AlertPriority, AlertType

if TYPE_CHECKING:
    from stats_repository import StatsRepository


class AlertAction(Enum):
    """Action to take for an alert."""
    
    NOTIFY = "notify"           # Send notification
    SUPPRESS = "suppress"       # Suppress (deduplicated)
    GROUP = "group"            # Add to group
    RATE_LIMITED = "rate_limited"  # Rate limited
    

@dataclass
class AlertMetrics:
    """Metrics for alert system monitoring."""
    
    total_alerts: int = 0
    deduplicated_alerts: int = 0
    suppressed_alerts: int = 0
    rate_limited_alerts: int = 0
    active_groups: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "total_alerts": self.total_alerts,
            "deduplicated_alerts": self.deduplicated_alerts,
            "suppressed_alerts": self.suppressed_alerts,
            "rate_limited_alerts": self.rate_limited_alerts,
            "active_groups": self.active_groups,
        }


class SmartAlertManager:
    """
    Central manager for intelligent alert processing.
    
    Coordinates:
    - Alert deduplication
    - Context-based grouping
    - Dynamic prioritization
    - Adaptive thresholds
    - Rate limiting
    - Noise reduction
    """
    
    def __init__(
        self,
        stats_repo: StatsRepository,
        dedup_window_seconds: int = 300,
        group_window_seconds: int = 600,
        rate_limit_per_minute: int = 10,
        rate_limit_burst: int = 5,
        escalation_threshold_minutes: int = 30,
        enable_deduplication: bool = True,
        enable_grouping: bool = True,
        enable_dynamic_priority: bool = True,
        enable_adaptive_thresholds: bool = True,
    ):
        """
        Initialize smart alert manager.
        
        Args:
            stats_repo: Statistics repository for data access
            dedup_window_seconds: Deduplication time window
            group_window_seconds: Grouping time window
            rate_limit_per_minute: Max alerts per minute
            rate_limit_burst: Max alerts in burst
            escalation_threshold_minutes: Time before escalating
            enable_deduplication: Enable deduplication
            enable_grouping: Enable grouping
            enable_dynamic_priority: Enable dynamic prioritization
            enable_adaptive_thresholds: Enable adaptive thresholds
        """
        self.stats_repo = stats_repo
        self.enable_deduplication = enable_deduplication
        self.enable_grouping = enable_grouping
        self.enable_dynamic_priority = enable_dynamic_priority
        self.enable_adaptive_thresholds = enable_adaptive_thresholds
        
        # Core components
        self.deduplicator = AlertDeduplicator(
            window_seconds=dedup_window_seconds,
        )
        
        self.grouper = AlertGrouper(
            group_window_seconds=group_window_seconds,
        )
        
        self.prioritizer = AlertPrioritizer(
            escalation_threshold_seconds=escalation_threshold_minutes * 60,
        )
        
        self.adaptive_thresholds = AdaptiveThresholds(
            stats_repo=stats_repo,
            baseline_window_hours=ADAPTIVE_BASELINE_WINDOW_HOURS,
            update_interval_minutes=ADAPTIVE_UPDATE_INTERVAL_MINUTES,
            anomaly_sigma=ADAPTIVE_ANOMALY_SIGMA,
        )
        
        # Alert history
        self.history = AlertHistory()
        
        # Rate limiting
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_limit_burst = rate_limit_burst
        self._alert_timestamps: deque[float] = deque(maxlen=rate_limit_per_minute * 2)
        
        # Metrics
        self.metrics = AlertMetrics()
        
        # Logger
        self.logger = logging.getLogger(__name__)
    
    def process_alert(
        self,
        alert: AlertEntity,
        context: Optional[Dict] = None,
    ) -> Tuple[AlertAction, Optional[AlertGroup]]:
        """
        Process an alert through smart system.
        
        Steps:
        1. Check rate limiting
        2. Calculate priority (if enabled)
        3. Check deduplication (if enabled)
        4. Group with related alerts (if enabled)
        5. Enrich with context
        6. Determine action
        
        Args:
            alert: Alert to process
            context: Additional context
            
        Returns:
            Tuple of (AlertAction, optional AlertGroup)
        """
        self.metrics.total_alerts += 1
        
        # 1. Check rate limiting
        if self._is_rate_limited():
            self.metrics.rate_limited_alerts += 1
            self.logger.debug(f"Alert rate limited: {alert.message}")
            return (AlertAction.RATE_LIMITED, None)
        
        # 2. Calculate priority (if enabled)
        if self.enable_dynamic_priority:
            alert.priority = self.prioritizer.calculate_priority(alert, context)
        
        # 3. Check deduplication (if enabled)
        if self.enable_deduplication:
            if self.deduplicator.should_suppress(alert):
                self.metrics.deduplicated_alerts += 1
                self.logger.debug(f"Alert deduplicated: {alert.fingerprint}")
                return (AlertAction.SUPPRESS, None)
        
        # 4. Group with related alerts (if enabled)
        group = None
        if self.enable_grouping:
            group = self.grouper.add_to_group(alert)
            self.metrics.active_groups = len(self.grouper.get_active_groups())
        
        # 5. Add to history
        self.history.add(alert)
        
        # 6. Record timestamp for rate limiting
        self._alert_timestamps.append(time.time())
        
        # Determine action
        if alert.suppressed:
            self.metrics.suppressed_alerts += 1
            return (AlertAction.SUPPRESS, group)
        
        if group and group.count > 1:
            return (AlertAction.GROUP, group)
        
        return (AlertAction.NOTIFY, group)
    
    def should_trigger_alert(
        self,
        metric: str,
        value: float,
        alert_type: AlertType,
        context: AlertContext,
        message: str,
    ) -> Tuple[bool, Optional[AlertEntity]]:
        """
        Check if alert should be triggered using adaptive thresholds.
        
        Args:
            metric: Metric name (e.g., "latency")
            value: Current value
            alert_type: Type of alert
            context: Alert context
            message: Alert message
            
        Returns:
            Tuple of (should_trigger, AlertEntity if created)
        """
        # Check adaptive threshold
        if self.enable_adaptive_thresholds:
            threshold = self.adaptive_thresholds.get_threshold(metric)
            is_anomaly = value > threshold
            
            if not is_anomaly:
                return (False, None)
        
        # Create alert
        alert = AlertEntity(
            alert_type=alert_type,
            message=message,
            priority=AlertPriority.MEDIUM,  # Will be recalculated
            context=context,
            metadata={"metric": metric, "value": value},
        )
        
        return (True, alert)
    
    def _is_rate_limited(self) -> bool:
        """
        Check if we're currently rate limited.
        
        Checks both:
        - Burst limit (last 10 seconds)
        - Per-minute limit
        
        Returns:
            True if rate limited
        """
        now = time.time()
        
        # Check burst limit (last 10 seconds)
        burst_count = sum(
            1 for ts in self._alert_timestamps
            if now - ts <= 10
        )
        if burst_count >= self.rate_limit_burst:
            return True
        
        # Check per-minute limit
        minute_count = sum(
            1 for ts in self._alert_timestamps
            if now - ts <= 60
        )
        if minute_count >= self.rate_limit_per_minute:
            return True
        
        return False
    
    def escalate_aged_groups(self) -> List[AlertGroup]:
        """
        Check and escalate aged alert groups.
        
        Returns:
            List of escalated groups
        """
        active_groups = self.grouper.get_active_groups()
        escalated = self.prioritizer.escalate_aged_alerts(active_groups)
        
        if escalated:
            self.logger.info(f"Escalated {len(escalated)} aged alert groups")
        
        return escalated
    
    def get_active_alerts(
        self,
        min_priority: Optional[AlertPriority] = None,
    ) -> List[AlertGroup]:
        """
        Get active alert groups.
        
        Args:
            min_priority: Minimum priority level
            
        Returns:
            List of alert groups sorted by priority
        """
        groups = self.grouper.get_active_groups()
        
        # Filter by priority if specified
        if min_priority:
            groups = [g for g in groups if g.priority.value >= min_priority.value]
        
        # Sort by priority
        groups = self.prioritizer.sort_by_priority(groups)
        
        return groups
    
    def get_critical_alerts(self) -> List[AlertGroup]:
        """Get only critical priority alerts."""
        return self.get_active_alerts(min_priority=AlertPriority.CRITICAL)
    
    def get_high_priority_alerts(self) -> List[AlertGroup]:
        """Get critical and high priority alerts."""
        return self.get_active_alerts(min_priority=AlertPriority.HIGH)
    
    def suppress_noise(self) -> int:
        """
        Apply noise reduction rules.
        
        Suppresses:
        - Low priority alerts in large groups
        - Duplicate alerts
        
        Returns:
            Number of alerts suppressed
        """
        suppressed_count = 0
        
        for group in self.grouper.get_active_groups():
            # Suppress low priority in large groups
            if group.count > 10 and group.priority == AlertPriority.LOW:
                for alert in group.alerts:
                    if not alert.suppressed:
                        alert.suppressed = True
                        suppressed_count += 1
        
        self.metrics.suppressed_alerts += suppressed_count
        return suppressed_count
    
    def update_adaptive_thresholds(self) -> None:
        """Manually trigger adaptive threshold update."""
        if self.enable_adaptive_thresholds:
            self.adaptive_thresholds.update_baselines()
            self.logger.info("Updated adaptive thresholds")
    
    def get_metrics(self) -> AlertMetrics:
        """Get current metrics."""
        # Update active groups count
        self.metrics.active_groups = len(self.grouper.get_active_groups())
        return self.metrics
    
    def get_history(self, hours: int = 24) -> List[AlertEntity]:
        """Get alert history for last N hours."""
        seconds = hours * 3600
        return self.history.get_recent(seconds)
    
    def clear_all(self) -> None:
        """Clear all state (for testing)."""
        self.deduplicator.clear()
        self.grouper.clear()
        self.adaptive_thresholds.clear()
        self.history.clear()
        self._alert_timestamps.clear()
        self.metrics = AlertMetrics()
