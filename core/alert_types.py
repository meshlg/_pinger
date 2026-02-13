"""
Alert data models for smart alert system.

Defines core entities for intelligent alert management including
deduplication, grouping, prioritization, and historical tracking.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class AlertPriority(Enum):
    """Alert priority levels for dynamic prioritization."""
    
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    
    def __lt__(self, other: AlertPriority) -> bool:
        """Enable comparison for sorting."""
        return self.value < other.value
    
    def __str__(self) -> str:
        return self.name


class AlertType(Enum):
    """Types of alerts in the system."""
    
    PACKET_LOSS = "packet_loss"
    HIGH_LATENCY = "high_latency"
    CONNECTION_LOST = "connection_lost"
    HIGH_JITTER = "high_jitter"
    HIGH_AVG_LATENCY = "high_avg_latency"
    MTU_ISSUE = "mtu_issue"
    ROUTE_CHANGE = "route_change"
    DNS_FAILURE = "dns_failure"
    IP_CHANGE = "ip_change"
    HOP_ISSUE = "hop_issue"
    MEMORY_EXCEEDED = "memory_exceeded"
    ANOMALY = "anomaly"
    
    def __str__(self) -> str:
        return self.value


@dataclass
class AlertContext:
    """
    Context information for alert grouping and correlation.
    
    Attributes:
        service: Service name (e.g., "ping", "dns", "mtu")
        component: Component name (e.g., "network", "latency", "connectivity")
        problem_type: Type of problem (e.g., "performance", "availability")
        target: Target of monitoring (IP, domain, etc.)
        metadata: Additional context-specific data
    """
    
    service: str
    component: str
    problem_type: str
    target: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service": self.service,
            "component": self.component,
            "problem_type": self.problem_type,
            "target": self.target,
            "metadata": self.metadata,
        }
    
    def matches(self, other: AlertContext, strict: bool = False) -> bool:
        """
        Check if contexts match for grouping.
        
        Args:
            other: Another context to compare
            strict: If True, all fields must match. If False, service+component+problem_type
        """
        if strict:
            return (
                self.service == other.service
                and self.component == other.component
                and self.problem_type == other.problem_type
                and self.target == other.target
            )
        else:
            return (
                self.service == other.service
                and self.component == other.component
                and self.problem_type == other.problem_type
            )


@dataclass
class AlertEntity:
    """
    Core alert entity with all metadata for smart processing.
    
    Attributes:
        alert_type: Type of alert
        message: Human-readable alert message
        priority: Current priority level
        context: Context for grouping/correlation
        timestamp: When alert was created
        fingerprint: Unique identifier for deduplication
        metadata: Additional alert-specific data
        suppressed: Whether alert is suppressed
        group_id: ID of group this alert belongs to
    """
    
    alert_type: AlertType
    message: str
    priority: AlertPriority
    context: AlertContext
    timestamp: datetime = field(default_factory=datetime.now)
    fingerprint: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    suppressed: bool = False
    group_id: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Generate fingerprint if not provided."""
        if not self.fingerprint:
            self.fingerprint = self._generate_fingerprint()
    
    def _generate_fingerprint(self) -> str:
        """
        Generate unique fingerprint for deduplication.
        
        Based on: alert_type + context (service, component, problem_type, target)
        This allows same type of alert from same context to be deduplicated.
        """
        components = [
            str(self.alert_type.value),
            self.context.service,
            self.context.component,
            self.context.problem_type,
            self.context.target,
        ]
        
        # Include key metadata fields if present
        if "threshold" in self.metadata:
            components.append(str(self.metadata["threshold"]))
        
        fingerprint_str = "|".join(components)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "alert_type": self.alert_type.value,
            "message": self.message,
            "priority": self.priority.name,
            "context": self.context.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "fingerprint": self.fingerprint,
            "metadata": self.metadata,
            "suppressed": self.suppressed,
            "group_id": self.group_id,
        }


@dataclass
class AlertGroup:
    """
    Group of related alerts for aggregation and reduced noise.
    
    Attributes:
        group_id: Unique group identifier
        alerts: List of alerts in this group
        context: Shared context for the group
        priority: Highest priority among alerts
        created_at: When group was created
        updated_at: Last update time
        count: Number of alerts in group
        active: Whether group is still active
    """
    
    group_id: str
    alerts: List[AlertEntity] = field(default_factory=list)
    context: Optional[AlertContext] = None
    priority: AlertPriority = AlertPriority.LOW
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    count: int = 0
    active: bool = True
    
    def add_alert(self, alert: AlertEntity) -> None:
        """Add alert to group and update metadata."""
        self.alerts.append(alert)
        self.count = len(self.alerts)
        self.updated_at = datetime.now(timezone.utc)
        
        # Update priority to highest in group
        if alert.priority > self.priority:
            self.priority = alert.priority
        
        # Set context from first alert if not set
        if not self.context:
            self.context = alert.context
        
        # Mark alert as grouped
        alert.group_id = self.group_id
    
    def get_summary(self) -> str:
        """Get human-readable summary of group."""
        if not self.alerts:
            return "Empty alert group"
        
        first_alert = self.alerts[0]
        if self.count == 1:
            return first_alert.message
        
        return f"{first_alert.message} (+{self.count - 1} similar)"
    
    def get_age_seconds(self) -> float:
        """Get age of group in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()
    
    def should_escalate(self, escalation_threshold_seconds: float) -> bool:
        """Check if group should be escalated based on age."""
        return self.active and self.get_age_seconds() >= escalation_threshold_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "group_id": self.group_id,
            "alert_count": self.count,
            "priority": self.priority.name,
            "context": self.context.to_dict() if self.context else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "age_seconds": self.get_age_seconds(),
            "summary": self.get_summary(),
            "active": self.active,
            "alerts": [a.to_dict() for a in self.alerts],
        }


@dataclass
class AlertHistory:
    """
    Historical record of alerts for analysis and baseline calculation.
    
    Attributes:
        entries: List of historical alert records
        max_size: Maximum number of entries to keep
        retention_seconds: How long to keep entries
    """
    
    entries: List[AlertEntity] = field(default_factory=list)
    max_size: int = 500
    retention_seconds: float = 172800.0  # 48 hours default
    
    def add(self, alert: AlertEntity) -> None:
        """Add alert to history with automatic cleanup."""
        self.entries.append(alert)
        self._cleanup()
    
    def _cleanup(self) -> None:
        """Remove old entries based on size and retention."""
        # Remove by retention time
        cutoff_time = datetime.now(timezone.utc).timestamp() - self.retention_seconds
        self.entries = [
            e for e in self.entries
            if e.timestamp.timestamp() >= cutoff_time
        ]
        
        # Remove by size (keep most recent)
        if len(self.entries) > self.max_size:
            self.entries = self.entries[-self.max_size:]
    
    def get_by_type(self, alert_type: AlertType) -> List[AlertEntity]:
        """Get all alerts of specific type."""
        return [e for e in self.entries if e.alert_type == alert_type]
    
    def get_by_context(self, context: AlertContext) -> List[AlertEntity]:
        """Get all alerts matching context."""
        return [e for e in self.entries if e.context.matches(context)]
    
    def get_recent(self, seconds: float) -> List[AlertEntity]:
        """Get alerts from last N seconds."""
        cutoff = datetime.now(timezone.utc).timestamp() - seconds
        return [e for e in self.entries if e.timestamp.timestamp() >= cutoff]
    
    def get_count_by_priority(self) -> Dict[AlertPriority, int]:
        """Get counts by priority level."""
        counts: Dict[AlertPriority, int] = {p: 0 for p in AlertPriority}
        for entry in self.entries:
            counts[entry.priority] += 1
        return counts
    
    def clear(self) -> None:
        """Clear all history."""
        self.entries.clear()
