"""
Core handlers for ping cycle operations.

This package provides separated handlers following Single Responsibility Principle:
- PingHandler: Executes ping and returns results
- AlertHandler: Handles alert logic based on ping results
- MetricsHandler: Updates Prometheus metrics

Background Task System:
- BackgroundTask: ABC for all periodic background monitors
- TaskOrchestrator: Registry and lifecycle manager for background tasks

Smart Alert System:
- SmartAlertManager: Intelligent alert processing with deduplication, grouping, prioritization
- AlertTypes: Data models for alerts
- AlertDeduplicator: Fingerprint-based deduplication
- AlertGrouper: Context-based grouping
- AlertPrioritizer: Dynamic prioritization
- AdaptiveThresholds: Historical data-based threshold calculation
"""

from .ping_handler import PingHandler, PingResult
from .alert_handler import AlertHandler
from .metrics_handler import MetricsHandler

# Background task infrastructure
from .background_task import BackgroundTask
from .task_orchestrator import TaskOrchestrator

# Smart alert system
from .smart_alert_manager import SmartAlertManager, AlertAction, AlertMetrics
from .alert_types import (
    AlertEntity,
    AlertPriority,
    AlertType,
    AlertContext,
    AlertGroup,
    AlertHistory,
)
from .alert_deduplicator import AlertDeduplicator
from .alert_grouper import AlertGrouper
from .alert_prioritizer import AlertPrioritizer
from .adaptive_thresholds import AdaptiveThresholds

__all__ = [
    # Original handlers
    "PingHandler",
    "PingResult",
    "AlertHandler",
    "MetricsHandler",
    # Background task infrastructure
    "BackgroundTask",
    "TaskOrchestrator",
    # Smart alert system
    "SmartAlertManager",
    "AlertAction",
    "AlertMetrics",
    "AlertEntity",
    "AlertPriority",
    "AlertType",
    "AlertContext",
    "AlertGroup",
    "AlertHistory",
    "AlertDeduplicator",
    "AlertGrouper",
    "AlertPrioritizer",
    "AdaptiveThresholds",
]
