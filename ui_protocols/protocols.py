"""
UI data provider protocol.

Defines the interface that UI depends on, following Dependency Inversion Principle.
UI should depend on abstractions, not concrete implementations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


@runtime_checkable
class StatsDataProvider(Protocol):
    """
    Protocol defining the interface for statistics data access.
    
    This allows UI to depend on an abstraction rather than the concrete Monitor class,
    following the Dependency Inversion Principle (DIP).
    
    Any class that implements these methods can be used with MonitorUI:
    - Monitor
    - MockMonitor (for testing)
    - RemoteMonitor (for distributed scenarios)
    """
    
    def get_stats_snapshot(self) -> StatsSnapshot:
        """
        Get an immutable snapshot of current statistics.
        
        Returns:
            StatsSnapshot containing all current statistics data including:
            - total, success, failure counts
            - latency statistics (min, max, current)
            - connection status
            - MTU/TTL information
            - route analysis data
            - active alerts
            - etc.
        """
        ...
    
    @property
    def stats_lock(self) -> Any:
        """
        Get the lock for thread-safe access to statistics.
        
        Used for coordinating access when displaying real-time data.
        """
        ...
    
    @property
    def recent_results(self) -> Any:
        """
        Get the deque of recent ping results (True/False).
        
        Used for calculating packet loss percentages.
        """
        ...
    
    def cleanup_alerts(self) -> None:
        """
        Clean up old/expired visual alerts.
        
        Called periodically by UI to maintain alert list.
        """
        ...
