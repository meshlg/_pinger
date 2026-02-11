"""
Alert grouping engine.

Provides intelligent grouping of related alerts based on context,
temporal correlation, and pattern clustering to reduce alert noise.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from core.alert_types import AlertContext, AlertEntity, AlertGroup, AlertType


class AlertGrouper:
    """
    Group related alerts to reduce noise and improve signal.
    
    Uses context-based grouping, temporal correlation, and root cause
    analysis to cluster related alerts together.
    """
    
    def __init__(
        self,
        group_window_seconds: int = 600,
        max_group_size: int = 20,
    ):
        """
        Initialize grouper.
        
        Args:
            group_window_seconds: Time window for grouping (default: 10 minutes)
            max_group_size: Maximum alerts per group
        """
        self.group_window_seconds = group_window_seconds
        self.max_group_size = max_group_size
        
        # Active groups: group_id -> AlertGroup
        self._groups: Dict[str, AlertGroup] = {}
        
        # Context hash -> group_id mapping for fast lookup
        self._context_index: Dict[str, str] = {}
        
        # Root cause relationships (parent alert type -> child alert types)
        self._root_cause_map = self._build_root_cause_map()
    
    def _build_root_cause_map(self) -> Dict[AlertType, Set[AlertType]]:
        """
        Build map of root cause relationships.
        
        For example, CONNECTION_LOST can cause HIGH_LATENCY and PACKET_LOSS.
        These should be grouped together.
        """
        return {
            AlertType.CONNECTION_LOST: {
                AlertType.PACKET_LOSS,
                AlertType.HIGH_LATENCY,
                AlertType.HIGH_JITTER,
            },
            AlertType.MTU_ISSUE: {
                AlertType.PACKET_LOSS,
                AlertType.HIGH_LATENCY,
            },
            AlertType.ROUTE_CHANGE: {
                AlertType.HIGH_LATENCY,
                AlertType.PACKET_LOSS,
            },
            AlertType.DNS_FAILURE: {
                AlertType.CONNECTION_LOST,
            },
        }
    
    def group_alerts(self, alerts: List[AlertEntity]) -> List[AlertGroup]:
        """
        Group a list of alerts.
        
        Args:
            alerts: List of alerts to group
            
        Returns:
            List of alert groups
        """
        for alert in alerts:
            self.add_to_group(alert)
        
        return list(self._groups.values())
    
    def add_to_group(self, alert: AlertEntity) -> AlertGroup:
        """
        Add alert to appropriate group or create new group.
        
        Args:
            alert: Alert to add
            
        Returns:
            AlertGroup the alert was added to
        """
        # Clean expired groups first
        self._cleanup_expired_groups()
        
        # Try to find existing group
        group = self._find_matching_group(alert)
        
        if group:
            # Add to existing group if not full
            if group.count < self.max_group_size:
                group.add_alert(alert)
                return group
        
        # Create new group
        group = self._create_group(alert)
        group.add_alert(alert)
        
        return group
    
    def _find_matching_group(self, alert: AlertEntity) -> Optional[AlertGroup]:
        """
        Find existing group that matches alert.
        
        Checks:
        1. Exact context match
        2. Root cause correlation
        3. Temporal correlation
        
        Args:
            alert: Alert to find group for
            
        Returns:
            Matching group if found, None otherwise
        """
        # First check exact context match
        context_hash = self._hash_context(alert.context)
        if context_hash in self._context_index:
            group_id = self._context_index[context_hash]
            group = self._groups.get(group_id)
            if group and group.active:
                return group
        
        # Check for root cause correlation
        correlated_group = self._find_correlated_group(alert)
        if correlated_group:
            return correlated_group
        
        # Check temporal correlation (same service/component, close time)
        temporal_group = self._find_temporal_group(alert)
        if temporal_group:
            return temporal_group
        
        return None
    
    def _find_correlated_group(self, alert: AlertEntity) -> Optional[AlertGroup]:
        """
        Find group with correlated root cause.
        
        Args:
            alert: Alert to check
            
        Returns:
            Correlated group if found
        """
        for group in self._groups.values():
            if not group.active or not group.alerts:
                continue
            
            # Check if any alert in group is a root cause of this alert
            for existing_alert in group.alerts:
                if self._is_correlated(existing_alert, alert):
                    return group
        
        return None
    
    def _is_correlated(self, alert1: AlertEntity, alert2: AlertEntity) -> bool:
        """
        Check if two alerts are correlated (root cause relationship).
        
        Args:
            alert1: First alert
            alert2: Second alert
            
        Returns:
            True if correlated
        """
        # Check if alert1 is root cause of alert2
        if alert1.alert_type in self._root_cause_map:
            related_types = self._root_cause_map[alert1.alert_type]
            if alert2.alert_type in related_types:
                # Must have same target/context
                if alert1.context.target == alert2.context.target:
                    return True
        
        # Check reverse
        if alert2.alert_type in self._root_cause_map:
            related_types = self._root_cause_map[alert2.alert_type]
            if alert1.alert_type in related_types:
                if alert1.context.target == alert2.context.target:
                    return True
        
        return False
    
    def _find_temporal_group(self, alert: AlertEntity) -> Optional[AlertGroup]:
        """
        Find group with temporal correlation.
        
        Alerts with same service and component within time window.
        
        Args:
            alert: Alert to check
            
        Returns:
            Temporally correlated group if found
        """
        now = time.time()
        
        for group in self._groups.values():
            if not group.active or not group.context:
                continue
            
            # Check if within time window
            age = now - group.created_at.timestamp()
            if age > self.group_window_seconds:
                continue
            
            # Check if service and component match
            if (
                group.context.service == alert.context.service
                and group.context.component == alert.context.component
            ):
                return group
        
        return None
    
    def _create_group(self, alert: AlertEntity) -> AlertGroup:
        """
        Create new alert group.
        
        Args:
            alert: Initial alert for the group
            
        Returns:
            New AlertGroup
        """
        group_id = str(uuid.uuid4())[:8]
        group = AlertGroup(
            group_id=group_id,
            context=alert.context,
        )
        
        self._groups[group_id] = group
        
        # Update index
        context_hash = self._hash_context(alert.context)
        self._context_index[context_hash] = group_id
        
        return group
    
    def _hash_context(self, context: AlertContext) -> str:
        """
        Generate hash for context-based indexing.
        
        Args:
            context: Alert context
            
        Returns:
            Hash string
        """
        key = f"{context.service}|{context.component}|{context.problem_type}|{context.target}"
        return hashlib.md5(key.encode()).hexdigest()[:8]
    
    def _cleanup_expired_groups(self) -> None:
        """Remove expired and inactive groups."""
        now = time.time()
        expired_groups = []
        
        for group_id, group in self._groups.items():
            # Mark as inactive if expired
            age = now - group.updated_at.timestamp()
            if age > self.group_window_seconds:
                group.active = False
                expired_groups.append(group_id)
        
        # Remove expired groups
        for group_id in expired_groups:
            group = self._groups[group_id]
            # Remove from context index
            if group.context:
                context_hash = self._hash_context(group.context)
                if context_hash in self._context_index:
                    del self._context_index[context_hash]
            # Remove from groups
            del self._groups[group_id]
    
    def get_active_groups(self) -> List[AlertGroup]:
        """Get all active groups."""
        return [g for g in self._groups.values() if g.active]
    
    def get_group_by_id(self, group_id: str) -> Optional[AlertGroup]:
        """Get group by ID."""
        return self._groups.get(group_id)
    
    def get_groups_by_priority(self, min_priority: int = 1) -> List[AlertGroup]:
        """
        Get groups with priority >= min_priority.
        
        Args:
            min_priority: Minimum priority value (1-4)
            
        Returns:
            Sorted list of groups (highest priority first)
        """
        groups = [
            g for g in self._groups.values()
            if g.active and g.priority.value >= min_priority
        ]
        return sorted(groups, key=lambda g: g.priority.value, reverse=True)
    
    def clear(self) -> None:
        """Clear all groups."""
        self._groups.clear()
        self._context_index.clear()
