"""
Alert prioritization system.

Provides dynamic priority calculation based on business impact,
user impact, service criticality, and time-based escalation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from core.alert_types import AlertEntity, AlertGroup, AlertPriority, AlertType


@dataclass
class PriorityWeights:
    """Weights for priority calculation."""
    
    business_impact: float = 0.4
    user_impact: float = 0.3
    service_criticality: float = 0.2
    time_factor: float = 0.1


class AlertPrioritizer:
    """
    Calculate and manage alert priorities dynamically.
    
    Considers multiple factors:
    - Business impact (revenue, SLA, compliance)
    - User impact (number of affected users)
    - Service criticality (core vs non-core services)
    - Time factor (age-based escalation)
    """
    
    def __init__(
        self,
        weights: Optional[PriorityWeights] = None,
        escalation_threshold_seconds: float = 1800.0,  # 30 minutes
    ):
        """
        Initialize prioritizer.
        
        Args:
            weights: Priority weights configuration
            escalation_threshold_seconds: Time before escalating priority
        """
        self.weights = weights or PriorityWeights()
        self.escalation_threshold_seconds = escalation_threshold_seconds
        
        # Service criticality mapping
        self._service_criticality = self._build_service_criticality_map()
        
        # Alert type impact mapping
        self._alert_impact = self._build_alert_impact_map()
    
    def _build_service_criticality_map(self) -> Dict[str, float]:
        """
        Build service criticality scores (0-1).
        
        Higher score = more critical service.
        """
        return {
            "ping": 1.0,         # Core connectivity monitoring
            "network": 1.0,      # Network layer issues
            "dns": 0.8,          # DNS resolution
            "mtu": 0.6,          # MTU issues
            "route": 0.7,        # Routing changes
            "ip": 0.5,           # IP changes
            "hop": 0.6,          # Hop monitoring
            "memory": 0.9,       # Memory issues
            "default": 0.5,      # Unknown services
        }
    
    def _build_alert_impact_map(self) -> Dict[AlertType, Dict[str, float]]:
        """
        Build alert type impact scores.
        
        Returns dict with:
        - business_impact: 0-1 score for business impact
        - user_impact: 0-1 score for user impact
        """
        return {
            AlertType.CONNECTION_LOST: {
                "business_impact": 1.0,
                "user_impact": 1.0,
            },
            AlertType.PACKET_LOSS: {
                "business_impact": 0.7,
                "user_impact": 0.8,
            },
            AlertType.HIGH_LATENCY: {
                "business_impact": 0.6,
                "user_impact": 0.7,
            },
            AlertType.HIGH_JITTER: {
                "business_impact": 0.5,
                "user_impact": 0.6,
            },
            AlertType.HIGH_AVG_LATENCY: {
                "business_impact": 0.6,
                "user_impact": 0.7,
            },
            AlertType.MTU_ISSUE: {
                "business_impact": 0.5,
                "user_impact": 0.6,
            },
            AlertType.ROUTE_CHANGE: {
                "business_impact": 0.4,
                "user_impact": 0.3,
            },
            AlertType.DNS_FAILURE: {
                "business_impact": 0.8,
                "user_impact": 0.9,
            },
            AlertType.IP_CHANGE: {
                "business_impact": 0.3,
                "user_impact": 0.2,
            },
            AlertType.HOP_ISSUE: {
                "business_impact": 0.5,
                "user_impact": 0.4,
            },
            AlertType.MEMORY_EXCEEDED: {
                "business_impact": 0.9,
                "user_impact": 0.7,
            },
            AlertType.ANOMALY: {
                "business_impact": 0.6,
                "user_impact": 0.5,
            },
        }
    
    def calculate_priority(
        self,
        alert: AlertEntity,
        context: Optional[Dict] = None,
    ) -> AlertPriority:
        """
        Calculate priority for an alert.
        
        Args:
            alert: Alert to prioritize
            context: Additional context (e.g., current metrics)
            
        Returns:
            Calculated AlertPriority
        """
        # Get impact scores
        impacts = self._alert_impact.get(
            alert.alert_type,
            {"business_impact": 0.5, "user_impact": 0.5}
        )
        
        business_score = impacts["business_impact"]
        user_score = impacts["user_impact"]
        
        # Get service criticality
        service_score = self._service_criticality.get(
            alert.context.service,
            self._service_criticality["default"]
        )
        
        # Calculate time factor (escalation based on age)
        time_score = self._calculate_time_factor(alert)
        
        # Weighted score
        total_score = (
            business_score * self.weights.business_impact +
            user_score * self.weights.user_impact +
            service_score * self.weights.service_criticality +
            time_score * self.weights.time_factor
        )
        
        # Map score to priority level
        priority = self._score_to_priority(total_score)
        
        return priority
    
    def _calculate_time_factor(self, alert: AlertEntity) -> float:
        """
        Calculate time-based escalation factor.
        
        Returns 0-1 score, where higher means older alert.
        
        Args:
            alert: Alert to calculate for
            
        Returns:
            Time factor score 0-1
        """
        age_seconds = (datetime.now() - alert.timestamp).total_seconds()
        
        # Normalize to 0-1 based on escalation threshold
        # Alerts older than threshold get max score
        normalized = min(1.0, age_seconds / self.escalation_threshold_seconds)
        
        return normalized
    
    def _score_to_priority(self, score: float) -> AlertPriority:
        """
        Convert numeric score to AlertPriority enum.
        
        Args:
            score: Score 0-1
            
        Returns:
            AlertPriority
        """
        if score >= 0.8:
            return AlertPriority.CRITICAL
        elif score >= 0.6:
            return AlertPriority.HIGH
        elif score >= 0.4:
            return AlertPriority.MEDIUM
        else:
            return AlertPriority.LOW
    
    def escalate_aged_alerts(self, groups: List[AlertGroup]) -> List[AlertGroup]:
        """
        Escalate priority for long-standing alert groups.
        
        Args:
            groups: List of alert groups to check
            
        Returns:
            List of groups that were escalated
        """
        escalated = []
        
        for group in groups:
            if not group.active:
                continue
            
            # Check if group should be escalated
            if group.should_escalate(self.escalation_threshold_seconds):
                # Escalate all alerts in group
                for alert in group.alerts:
                    old_priority = alert.priority
                    new_priority = self._escalate_priority(old_priority)
                    
                    if new_priority != old_priority:
                        alert.priority = new_priority
                
                # Update group priority to highest
                group.priority = max(
                    (a.priority for a in group.alerts),
                    default=group.priority
                )
                
                escalated.append(group)
        
        return escalated
    
    def _escalate_priority(self, current: AlertPriority) -> AlertPriority:
        """
        Escalate priority by one level.
        
        Args:
            current: Current priority
            
        Returns:
            Escalated priority (capped at CRITICAL)
        """
        if current == AlertPriority.CRITICAL:
            return AlertPriority.CRITICAL
        elif current == AlertPriority.HIGH:
            return AlertPriority.CRITICAL
        elif current == AlertPriority.MEDIUM:
            return AlertPriority.HIGH
        else:  # LOW
            return AlertPriority.MEDIUM
    
    def recalculate_group_priority(self, group: AlertGroup) -> AlertPriority:
        """
        Recalculate priority for entire group.
        
        Takes highest priority among all alerts.
        
        Args:
            group: Alert group
            
        Returns:
            Calculated priority
        """
        if not group.alerts:
            return AlertPriority.LOW
        
        # Get highest priority
        max_priority = max(
            (alert.priority for alert in group.alerts),
            default=AlertPriority.LOW
        )
        
        # Apply time-based escalation
        if group.should_escalate(self.escalation_threshold_seconds):
            max_priority = self._escalate_priority(max_priority)
        
        return max_priority
    
    def sort_by_priority(
        self,
        groups: List[AlertGroup],
        reverse: bool = True
    ) -> List[AlertGroup]:
        """
        Sort groups by priority.
        
        Args:
            groups: List of groups to sort
            reverse: If True, highest priority first
            
        Returns:
            Sorted list
        """
        return sorted(
            groups,
            key=lambda g: (g.priority.value, g.get_age_seconds()),
            reverse=reverse
        )
