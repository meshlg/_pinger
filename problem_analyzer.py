"""
Intelligent Problem Analysis System.

A comprehensive multi-layered system for deep analysis of network problems,
including pattern recognition, causal analysis, predictive analytics,
and solution generation with effectiveness estimation.

Architecture:
    Layer 1: Data Collection & Preprocessing
    Layer 2: Deep Analysis Engine (anomalies, correlations, patterns)
    Layer 3: Causal Analysis & Root Cause Detection
    Layer 4: Classification & Prioritization
    Layer 5: Learning & Experience Accumulation
    Layer 6: Solution Generation & Recommendations
    Layer 7: Predictive Analytics
    Layer 8: Reporting & Visualization
"""

from __future__ import annotations

import copy
import logging
import math
import statistics
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from stats_repository import StatsRepository, StatsSnapshot

from config import (
    CONSECUTIVE_LOSS_THRESHOLD,
    INTERVAL,
    PROBLEM_HISTORY_SIZE,
    PROBLEM_LOG_SUPPRESSION_SECONDS,
    PROBLEM_LOSS_THRESHOLD,
    PROBLEM_LATENCY_THRESHOLD,
    PROBLEM_JITTER_THRESHOLD,
    PROBLEM_CONSECUTIVE_LOSS_THRESHOLD,
    t,
    ensure_utc,
)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class ProblemType(Enum):
    """Classification of problem types with severity levels."""

    # Network connectivity issues
    CONNECTION_LOST = auto()
    ISP_OUTAGE = auto()
    LOCAL_NETWORK = auto()

    # Performance issues
    HIGH_LATENCY = auto()
    HIGH_JITTER = auto()
    PACKET_LOSS = auto()

    # DNS issues
    DNS_FAILURE = auto()
    DNS_SLOW = auto()
    DNS_TIMEOUT = auto()

    # MTU issues
    MTU_LOW = auto()
    MTU_FRAGMENTED = auto()

    # Route issues
    ROUTE_CHANGE = auto()
    ROUTE_DEGRADATION = auto()
    HOP_TIMEOUT = auto()

    # Composite/derived issues
    INTERMITTENT = auto()
    CASCADING = auto()
    UNKNOWN = auto()

    def __str__(self) -> str:
        return self.name.lower().replace("_", " ")


class ProblemSeverity(Enum):
    """Severity levels for problems."""

    CRITICAL = 5  # Service completely unavailable
    HIGH = 4       # Major functionality impaired
    MEDIUM = 3     # Noticeable degradation
    LOW = 2        # Minor issues
    INFO = 1       # Informational, no impact

    def __lt__(self, other: ProblemSeverity) -> bool:
        return self.value < other.value

    def __ge__(self, other: ProblemSeverity) -> bool:
        return self.value >= other.value


class ProblemPriority(Enum):
    """Priority levels for problem resolution."""

    URGENT = 4     # Immediate attention required
    HIGH = 3       # Address within hours
    MEDIUM = 2     # Address within days
    LOW = 1        # Address when possible

    def __lt__(self, other: ProblemPriority) -> bool:
        return self.value < other.value


class ConfidenceLevel(Enum):
    """Confidence levels for analysis results."""

    VERY_HIGH = 0.95
    HIGH = 0.85
    MEDIUM = 0.70
    LOW = 0.50
    VERY_LOW = 0.30


class AnomalyType(Enum):
    """Types of detected anomalies."""

    SPIKE = auto()
    DROP = auto()
    TREND_UP = auto()
    TREND_DOWN = auto()
    OSCILLATION = auto()
    OUTLIER = auto()
    PATTERN_BREAK = auto()


@dataclass
class MetricAnomaly:
    """Detected anomaly in a metric."""

    metric_name: str
    anomaly_type: AnomalyType
    value: float
    expected_range: Tuple[float, float]
    deviation_sigma: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "anomaly_type": self.anomaly_type.name,
            "value": self.value,
            "expected_range": list(self.expected_range),
            "deviation_sigma": self.deviation_sigma,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
        }


@dataclass
class CorrelationResult:
    """Result of correlation analysis between metrics.

    Note: significance_score is a heuristic estimate based on correlation magnitude,
    not a statistically rigorous p-value. It should be interpreted as an internal
    confidence indicator rather than a formal statistical significance test.
    """

    metric_a: str
    metric_b: str
    correlation_coefficient: float  # -1 to 1
    significance_score: float  # Heuristic confidence score (0.0-1.0), NOT a real p-value
    significance: str  # "strong", "moderate", "weak", "none" - based on magnitude
    lag_seconds: float = 0.0  # Time lag if cross-correlation

    @property
    def is_significant(self) -> bool:
        """Check if correlation is considered significant based on heuristic criteria.

        Warning: This uses internal heuristics, not formal statistical testing.
        """
        return abs(self.correlation_coefficient) > 0.5 and self.significance_score > 0.9

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_a": self.metric_a,
            "metric_b": self.metric_b,
            "correlation_coefficient": self.correlation_coefficient,
            "significance_score": self.significance_score,
            "significance": self.significance,
            "lag_seconds": self.lag_seconds,
        }


@dataclass
class CausalFactor:
    """A factor contributing to a problem."""

    factor_id: str
    name: str
    description: str
    contribution_weight: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    is_root_cause: bool = False
    related_metrics: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor_id": self.factor_id,
            "name": self.name,
            "description": self.description,
            "contribution_weight": self.contribution_weight,
            "confidence": self.confidence,
            "is_root_cause": self.is_root_cause,
            "related_metrics": self.related_metrics,
            "evidence": self.evidence,
        }


@dataclass
class SolutionRecommendation:
    """Recommended solution for a problem."""

    solution_id: str
    title: str
    description: str
    steps: List[str]
    effectiveness_score: float  # 0.0 to 1.0
    risk_level: str  # "low", "medium", "high"
    resource_cost: str  # "low", "medium", "high"
    estimated_time_minutes: int
    prerequisites: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    success_probability: float = 0.0
    historical_success_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "solution_id": self.solution_id,
            "title": self.title,
            "description": self.description,
            "steps": self.steps,
            "effectiveness_score": self.effectiveness_score,
            "risk_level": self.risk_level,
            "resource_cost": self.resource_cost,
            "estimated_time_minutes": self.estimated_time_minutes,
            "prerequisites": self.prerequisites,
            "side_effects": self.side_effects,
            "success_probability": self.success_probability,
            "historical_success_rate": self.historical_success_rate,
        }


@dataclass
class ProblemClassification:
    """Complete classification of a detected problem."""

    problem_type: ProblemType
    severity: ProblemSeverity
    priority: ProblemPriority
    confidence: float
    description: str
    affected_components: List[str]
    impact_assessment: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_type": self.problem_type.name,
            "severity": self.severity.name,
            "priority": self.priority.name,
            "confidence": self.confidence,
            "description": self.description,
            "affected_components": self.affected_components,
            "impact_assessment": self.impact_assessment,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ProblemRecord:
    """Complete record of a problem occurrence."""

    record_id: str
    classification: ProblemClassification
    anomalies: List[MetricAnomaly]
    causal_factors: List[CausalFactor]
    solutions: List[SolutionRecommendation]
    snapshot_data: Dict[str, Any]
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    resolution_method: Optional[str] = None
    effectiveness_feedback: Optional[float] = None  # User feedback on solution

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "classification": self.classification.to_dict(),
            "anomalies": [a.to_dict() for a in self.anomalies],
            "causal_factors": [f.to_dict() for f in self.causal_factors],
            "solutions": [s.to_dict() for s in self.solutions],
            "snapshot_data": self.snapshot_data,
            "resolved": self.resolved,
            "resolution_time": self.resolution_time.isoformat() if self.resolution_time else None,
            "resolution_method": self.resolution_method,
            "effectiveness_feedback": self.effectiveness_feedback,
        }


@dataclass
class PredictionResult:
    """Result of predictive analysis."""

    prediction_type: str
    probability: float
    time_horizon_minutes: int
    predicted_problem_type: ProblemType
    confidence: float
    contributing_factors: List[str]
    preventive_actions: List[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_type": self.prediction_type,
            "probability": self.probability,
            "time_horizon_minutes": self.time_horizon_minutes,
            "predicted_problem_type": self.predicted_problem_type.name,
            "confidence": self.confidence,
            "contributing_factors": self.contributing_factors,
            "preventive_actions": self.preventive_actions,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AnalysisReport:
    """Comprehensive analysis report."""

    report_id: str
    generated_at: datetime
    time_range: Tuple[datetime, datetime]
    summary: str
    problem_statistics: Dict[str, Any]
    trend_analysis: Dict[str, Any]
    patterns_detected: List[Dict[str, Any]]
    recommendations: List[SolutionRecommendation]
    predictions: List[PredictionResult]
    metrics_summary: Dict[str, Any]
    health_score: float  # 0-100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "time_range": [t.isoformat() for t in self.time_range],
            "summary": self.summary,
            "problem_statistics": self.problem_statistics,
            "trend_analysis": self.trend_analysis,
            "patterns_detected": self.patterns_detected,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "predictions": [p.to_dict() for p in self.predictions],
            "metrics_summary": self.metrics_summary,
            "health_score": self.health_score,
        }


# =============================================================================
# CONFIGURATION AND RULES
# =============================================================================

@dataclass
class AnalysisRule:
    """Configurable rule for problem analysis."""

    rule_id: str
    name: str
    description: str
    condition: Callable[[Dict[str, Any]], bool]
    problem_type: ProblemType
    severity: ProblemSeverity
    priority: ProblemPriority
    enabled: bool = True
    cooldown_seconds: float = 60.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThresholdConfig:
    """Configurable threshold for a metric."""

    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison: str  # "greater", "less", "range"
    unit: str = ""
    adaptive: bool = False
    baseline_window_hours: int = 24


class AnalysisConfig:
    """Configuration for the analysis system."""

    def __init__(self) -> None:
        self.thresholds: Dict[str, ThresholdConfig] = {}
        self.rules: Dict[str, AnalysisRule] = {}
        self.learning_enabled: bool = True
        self.prediction_enabled: bool = True
        self.history_size: int = PROBLEM_HISTORY_SIZE
        self.anomaly_sigma_threshold: float = 2.0
        self.correlation_window_minutes: int = 30
        self.prediction_horizon_minutes: int = 60
        self.min_samples_for_analysis: int = 5
        self.ping_interval_seconds: float = INTERVAL  # Real ping interval from config
        self._initialize_default_thresholds()

    def _initialize_default_thresholds(self) -> None:
        """Initialize default threshold configurations."""
        self.thresholds = {
            "latency": ThresholdConfig(
                metric_name="latency",
                warning_threshold=PROBLEM_LATENCY_THRESHOLD * 0.7,
                critical_threshold=PROBLEM_LATENCY_THRESHOLD,
                comparison="greater",
                unit="ms",
                adaptive=True,
            ),
            "packet_loss": ThresholdConfig(
                metric_name="packet_loss",
                warning_threshold=PROBLEM_LOSS_THRESHOLD * 0.5,
                critical_threshold=PROBLEM_LOSS_THRESHOLD,
                comparison="greater",
                unit="%",
                adaptive=True,
            ),
            "jitter": ThresholdConfig(
                metric_name="jitter",
                warning_threshold=PROBLEM_JITTER_THRESHOLD * 0.7,
                critical_threshold=PROBLEM_JITTER_THRESHOLD,
                comparison="greater",
                unit="ms",
                adaptive=True,
            ),
            "consecutive_losses": ThresholdConfig(
                metric_name="consecutive_losses",
                warning_threshold=PROBLEM_CONSECUTIVE_LOSS_THRESHOLD * 0.5,
                critical_threshold=PROBLEM_CONSECUTIVE_LOSS_THRESHOLD,
                comparison="greater",
                unit="count",
                adaptive=False,
            ),
        }

    def add_threshold(self, config: ThresholdConfig) -> None:
        """Add or update a threshold configuration."""
        self.thresholds[config.metric_name] = config

    def add_rule(self, rule: AnalysisRule) -> None:
        """Add or update an analysis rule."""
        self.rules[rule.rule_id] = rule

    def get_threshold(self, metric_name: str) -> Optional[ThresholdConfig]:
        """Get threshold configuration for a metric."""
        return self.thresholds.get(metric_name)

    def is_threshold_breached(
        self,
        metric_name: str,
        value: float,
        level: str = "critical",
    ) -> bool:
        """Check whether a value breaches the configured threshold."""
        threshold = self.get_threshold(metric_name)
        if threshold is None:
            return False

        if threshold.comparison == "range":
            low = min(threshold.warning_threshold, threshold.critical_threshold)
            high = max(threshold.warning_threshold, threshold.critical_threshold)
            return value < low or value > high

        target = threshold.warning_threshold if level == "warning" else threshold.critical_threshold

        if threshold.comparison == "greater":
            return value >= target
        if threshold.comparison == "less":
            return value <= target

        return False

    def get_matching_rules(self, snapshot: Dict[str, Any]) -> List[AnalysisRule]:
        """Return enabled analysis rules whose conditions match the snapshot."""
        matched_rules: List[AnalysisRule] = []
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            try:
                if rule.condition(snapshot):
                    matched_rules.append(rule)
            except Exception as exc:
                logging.debug(f"Analysis rule '{rule.rule_id}' evaluation error: {exc}")

        return sorted(
            matched_rules,
            key=lambda rule: (rule.severity.value, rule.priority.value),
            reverse=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "learning_enabled": self.learning_enabled,
            "prediction_enabled": self.prediction_enabled,
            "history_size": self.history_size,
            "anomaly_sigma_threshold": self.anomaly_sigma_threshold,
            "correlation_window_minutes": self.correlation_window_minutes,
            "prediction_horizon_minutes": self.prediction_horizon_minutes,
            "thresholds": {
                k: {
                    "warning_threshold": v.warning_threshold,
                    "critical_threshold": v.critical_threshold,
                    "comparison": v.comparison,
                    "unit": v.unit,
                    "adaptive": v.adaptive,
                }
                for k, v in self.thresholds.items()
            },
        }


# =============================================================================
# LEARNING AND EXPERIENCE SYSTEM
# =============================================================================

class ExperienceStore:
    """
    Storage and retrieval of historical problem-solving experience.

    Enables learning from past incidents to improve future analysis
    and solution recommendations.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self.max_history = max_history
        self._experiences: deque[ProblemRecord] = deque(maxlen=max_history)
        self._solution_outcomes: Dict[str, List[Tuple[bool, float]]] = {}
        self._pattern_memory: Dict[str, int] = {}
        self._lock = threading.RLock()

    def record_experience(self, record: ProblemRecord) -> None:
        """Record or update a problem occurrence and its resolution."""
        with self._lock:
            stored_record = copy.deepcopy(record)

            for index, existing_record in enumerate(self._experiences):
                if existing_record.record_id == stored_record.record_id:
                    self._experiences[index] = stored_record
                    break
            else:
                self._experiences.append(stored_record)

            self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        """Rebuild derived indexes from stored experience snapshots."""
        self._solution_outcomes = {}
        self._pattern_memory = {}

        for record in self._experiences:
            pattern_key = record.classification.problem_type.name
            self._pattern_memory[pattern_key] = self._pattern_memory.get(pattern_key, 0) + 1

            if record.resolved and record.resolution_method and record.effectiveness_feedback is not None:
                if record.resolution_method not in self._solution_outcomes:
                    self._solution_outcomes[record.resolution_method] = []
                success = record.effectiveness_feedback >= 0.7
                self._solution_outcomes[record.resolution_method].append((success, record.effectiveness_feedback))

    def get_similar_problems(self, problem_type: ProblemType, limit: int = 10) -> List[ProblemRecord]:
        """Find similar historical problems."""
        with self._lock:
            similar = [
                e for e in self._experiences
                if e.classification.problem_type == problem_type
            ]
            ordered = sorted(similar, key=lambda x: x.classification.timestamp, reverse=True)[:limit]
            return copy.deepcopy(ordered)

    def get_solution_success_rate(self, solution_id: str) -> Optional[float]:
        """
        Calculate historical success rate for a solution.

        Returns:
            Float success rate (0.0-1.0) if solution has history,
            None if no historical data exists (unknown solution).
        """
        with self._lock:
            if solution_id not in self._solution_outcomes:
                return None  # No history - unknown solution
            outcomes = self._solution_outcomes[solution_id]
            if not outcomes:
                return None  # Empty outcomes - no history
            successes = sum(1 for s, _ in outcomes if s)
            return successes / len(outcomes)

    def get_effective_solutions(self, problem_type: ProblemType) -> List[Tuple[str, float]]:
        """Get solutions that were effective for a problem type."""
        with self._lock:
            similar = self.get_similar_problems(problem_type, limit=50)
            solution_scores: Dict[str, List[float]] = {}

            for record in similar:
                # Use 'is not None' to preserve effectiveness_feedback == 0.0
                if record.resolved and record.resolution_method and record.effectiveness_feedback is not None:
                    if record.resolution_method not in solution_scores:
                        solution_scores[record.resolution_method] = []
                    solution_scores[record.resolution_method].append(record.effectiveness_feedback)

            # Calculate average effectiveness
            effective = [
                (sol, sum(scores) / len(scores))
                for sol, scores in solution_scores.items()
                if len(scores) >= 2  # Need at least 2 data points
            ]
            return sorted(effective, key=lambda x: x[1], reverse=True)

    def get_problem_frequency(self, problem_type: ProblemType, hours: int = 24) -> int:
        """Get frequency of a problem type in recent hours."""
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            return sum(
                1 for e in self._experiences
                if e.classification.problem_type == problem_type
                and ensure_utc(e.classification.timestamp) is not None
                and ensure_utc(e.classification.timestamp) >= cutoff
            )

    def get_pattern_probability(self, problem_type: ProblemType) -> float:
        """Get probability of a problem type based on historical frequency."""
        with self._lock:
            if not self._pattern_memory:
                return 0.0
            total = sum(self._pattern_memory.values())
            if total == 0:
                return 0.0
            return self._pattern_memory.get(problem_type.name, 0) / total

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics of the experience store."""
        with self._lock:
            total = len(self._experiences)
            resolved = sum(1 for e in self._experiences if e.resolved)

            severity_counts: Dict[str, int] = {}
            for exp in self._experiences:
                sev = exp.classification.severity.name
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

            return {
                "total_problems": total,
                "resolved_problems": resolved,
                "resolution_rate": resolved / total if total > 0 else 0.0,
                "unique_solutions_tried": len(self._solution_outcomes),
                "severity_distribution": severity_counts,
                "pattern_distribution": dict(self._pattern_memory),
            }

    def get_records_in_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[ProblemRecord]:
        """Get problem records within a specific time range."""
        with self._lock:
            records = []
            for record in self._experiences:
                ts = ensure_utc(record.classification.timestamp)
                if ts is not None and start_time <= ts <= end_time:
                    records.append(copy.deepcopy(record))
            return sorted(records, key=lambda r: r.classification.timestamp, reverse=True)

    def get_statistics_for_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Get statistics for a specific time range."""
        with self._lock:
            records = self.get_records_in_time_range(start_time, end_time)

            total = len(records)
            resolved = sum(1 for r in records if r.resolved)

            severity_counts: Dict[str, int] = {}
            pattern_counts: Dict[str, int] = {}

            for record in records:
                sev = record.classification.severity.name
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

                pattern = record.classification.problem_type.name
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

            return {
                "total_problems": total,
                "resolved_problems": resolved,
                "resolution_rate": resolved / total if total > 0 else 0.0,
                "severity_distribution": severity_counts,
                "pattern_distribution": pattern_counts,
            }

    def get_hourly_distribution(
        self,
        problem_type: ProblemType,
        days_back: int = 7,
    ) -> Dict[int, int]:
        """
        Get hourly distribution of a problem type.

        Returns a dictionary mapping hour (0-23) to count of problems
        that occurred at that hour in the specified time range.
        """
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
            hour_counts: Dict[int, int] = {}

            for record in self._experiences:
                if record.classification.problem_type != problem_type:
                    continue
                ts = ensure_utc(record.classification.timestamp)
                if ts is None or ts < cutoff:
                    continue
                hour = ts.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1

            return hour_counts


# =============================================================================
# DEEP ANALYSIS ENGINE
# =============================================================================

class DeepAnalysisEngine:
    """
    Layer 2: Deep analysis engine for detecting anomalies,
    correlations, and hidden patterns in metrics data.
    """

    def __init__(self, config: AnalysisConfig) -> None:
        self.config = config
        self._metric_history: Dict[str, deque[float]] = {}
        self._baseline_stats: Dict[str, Dict[str, float]] = {}
        self._lock = threading.RLock()

    def ingest_metrics(self, snapshot: Dict[str, Any]) -> None:
        """Ingest metrics from a snapshot for analysis."""
        with self._lock:
            # Extract and store relevant metrics
            metrics_to_track = ["latency", "jitter", "packet_loss"]

            latency = snapshot.get("last_latency_ms")
            if latency and latency != t("na"):
                try:
                    latency_val = float(latency)
                    self._append_metric("latency", latency_val)
                except (ValueError, TypeError):
                    pass

            jitter = snapshot.get("jitter", 0)
            if isinstance(jitter, (int, float)):
                self._append_metric("jitter", float(jitter))

            # Calculate packet loss percentage
            total = snapshot.get("total", 0)
            failure = snapshot.get("failure", 0)
            if total > 0:
                loss_pct = (failure / total) * 100
                self._append_metric("packet_loss", loss_pct)

            # Update baselines periodically
            self._update_baselines()

    def _append_metric(self, metric_name: str, value: float) -> None:
        """Append a metric value to history."""
        if metric_name not in self._metric_history:
            self._metric_history[metric_name] = deque(maxlen=1000)
        self._metric_history[metric_name].append(value)

    def _update_baselines(self) -> None:
        """Update baseline statistics for all metrics."""
        for metric_name, values in self._metric_history.items():
            if len(values) >= self.config.min_samples_for_analysis:
                values_list = list(values)
                self._baseline_stats[metric_name] = {
                    "mean": statistics.mean(values_list),
                    "std_dev": statistics.stdev(values_list) if len(values_list) > 1 else 0.0,
                    "median": statistics.median(values_list),
                    "min": min(values_list),
                    "max": max(values_list),
                    "count": len(values_list),
                }

    def detect_anomalies(self, snapshot: Dict[str, Any]) -> List[MetricAnomaly]:
        """Detect anomalies in current metrics compared to baseline and thresholds."""
        anomalies: List[MetricAnomaly] = []

        with self._lock:
            for metric_name, threshold_config in self.config.thresholds.items():
                current_value = self._extract_metric_value(snapshot, metric_name)
                if current_value is None:
                    continue

                baseline = self._baseline_stats.get(metric_name)
                baseline_ready = (
                    threshold_config.adaptive
                    and baseline is not None
                    and baseline["count"] >= self.config.min_samples_for_analysis
                )
                warning_triggered = self.config.is_threshold_breached(
                    metric_name, current_value, level="warning"
                )
                critical_triggered = self.config.is_threshold_breached(
                    metric_name, current_value, level="critical"
                )

                deviation_sigma = 0.0
                sigma_triggered = False
                expected_range = self._expected_range_from_threshold(
                    threshold_config,
                    level="warning",
                )
                context: Dict[str, Any] = {
                    "adaptive": threshold_config.adaptive,
                    "warning_triggered": warning_triggered,
                    "critical_triggered": critical_triggered,
                }
                anomaly_type = self._threshold_anomaly_type(threshold_config, current_value)

                if baseline_ready and baseline is not None:
                    mean = baseline["mean"]
                    std_dev = baseline["std_dev"] or 1.0
                    deviation_sigma = abs(current_value - mean) / std_dev
                    sigma_triggered = deviation_sigma > self.config.anomaly_sigma_threshold
                    expected_range = (mean - 2 * std_dev, mean + 2 * std_dev)
                    context.update({"baseline_mean": mean, "baseline_std": std_dev})

                    if sigma_triggered:
                        anomaly_type = self._determine_anomaly_type(metric_name, current_value, baseline)

                if not warning_triggered and not sigma_triggered:
                    continue

                if sigma_triggered and critical_triggered:
                    context["trigger"] = "baseline_and_critical_threshold"
                elif sigma_triggered and warning_triggered:
                    context["trigger"] = "baseline_and_warning_threshold"
                elif sigma_triggered:
                    context["trigger"] = "baseline"
                elif critical_triggered:
                    context["trigger"] = "critical_threshold"
                else:
                    context["trigger"] = "warning_threshold"

                anomaly = MetricAnomaly(
                    metric_name=metric_name,
                    anomaly_type=anomaly_type,
                    value=current_value,
                    expected_range=expected_range,
                    deviation_sigma=deviation_sigma,
                    timestamp=datetime.now(timezone.utc),
                    context=context,
                )
                anomalies.append(anomaly)

        return anomalies

    def _expected_range_from_threshold(
        self,
        threshold_config: ThresholdConfig,
        level: str = "warning",
    ) -> Tuple[float, float]:
        """Build an expected range from a threshold configuration."""
        if threshold_config.comparison == "range":
            low = min(threshold_config.warning_threshold, threshold_config.critical_threshold)
            high = max(threshold_config.warning_threshold, threshold_config.critical_threshold)
            return (low, high)

        threshold_value = (
            threshold_config.warning_threshold
            if level == "warning"
            else threshold_config.critical_threshold
        )

        if threshold_config.comparison == "less":
            return (threshold_value, math.inf)

        return (-math.inf, threshold_value)

    def _threshold_anomaly_type(
        self,
        threshold_config: ThresholdConfig,
        current_value: float,
    ) -> AnomalyType:
        """Determine anomaly type from threshold semantics."""
        if threshold_config.comparison == "less":
            return AnomalyType.DROP

        if threshold_config.comparison == "range":
            low = min(threshold_config.warning_threshold, threshold_config.critical_threshold)
            high = max(threshold_config.warning_threshold, threshold_config.critical_threshold)
            if current_value < low:
                return AnomalyType.DROP
            if current_value > high:
                return AnomalyType.SPIKE

        return AnomalyType.SPIKE

    def _extract_metric_value(self, snapshot: Dict[str, Any], metric_name: str) -> Optional[float]:
        """Extract metric value from snapshot."""
        if metric_name == "latency":
            latency = snapshot.get("last_latency_ms")
            if latency and latency != t("na"):
                try:
                    return float(latency)
                except (ValueError, TypeError):
                    pass
        elif metric_name == "jitter":
            jitter = snapshot.get("jitter", 0)
            if isinstance(jitter, (int, float)):
                return float(jitter)
        elif metric_name == "packet_loss":
            total = snapshot.get("total", 1)
            failure = snapshot.get("failure", 0)
            return (failure / total) * 100 if total > 0 else 0.0
        elif metric_name == "consecutive_losses":
            return float(snapshot.get("consecutive_losses", 0))
        return None

    def _determine_anomaly_type(
        self,
        metric_name: str,
        current_value: float,
        baseline: Dict[str, float],
    ) -> AnomalyType:
        """Determine the type of anomaly detected."""
        mean = baseline["mean"]

        if current_value > mean * 1.5:
            return AnomalyType.SPIKE
        elif current_value < mean * 0.5:
            return AnomalyType.DROP

        # Check for trend (simplified)
        values = list(self._metric_history.get(metric_name, []))
        if len(values) >= 10:
            recent = values[-5:]
            older = values[-10:-5]
            if statistics.mean(recent) > statistics.mean(older) * 1.2:
                return AnomalyType.TREND_UP
            elif statistics.mean(recent) < statistics.mean(older) * 0.8:
                return AnomalyType.TREND_DOWN

        return AnomalyType.OUTLIER

    def analyze_correlations(self) -> List[CorrelationResult]:
        """Analyze correlations between different metrics."""
        correlations: List[CorrelationResult] = []

        with self._lock:
            metric_names = list(self._metric_history.keys())
            for i, metric_a in enumerate(metric_names):
                for metric_b in metric_names[i + 1:]:
                    result = self._calculate_correlation(metric_a, metric_b)
                    if result:
                        correlations.append(result)

        return correlations

    def _calculate_correlation(self, metric_a: str, metric_b: str) -> Optional[CorrelationResult]:
        """Calculate Pearson correlation between two metrics."""
        values_a = list(self._metric_history.get(metric_a, []))
        values_b = list(self._metric_history.get(metric_b, []))

        min_len = min(len(values_a), len(values_b))
        if min_len < self.config.min_samples_for_analysis:
            return None

        # Align series by taking the most recent values
        values_a = values_a[-min_len:]
        values_b = values_b[-min_len:]

        try:
            # Calculate Pearson correlation coefficient
            n = len(values_a)
            mean_a = statistics.mean(values_a)
            mean_b = statistics.mean(values_b)

            std_a = statistics.stdev(values_a) if len(values_a) > 1 else 0.0
            std_b = statistics.stdev(values_b) if len(values_b) > 1 else 0.0

            if std_a == 0 or std_b == 0:
                return None

            covariance = sum(
                (values_a[i] - mean_a) * (values_b[i] - mean_b)
                for i in range(n)
            ) / n

            correlation = covariance / (std_a * std_b)

            # Determine significance level based on correlation magnitude
            abs_corr = abs(correlation)
            if abs_corr > 0.7:
                significance = "strong"
            elif abs_corr > 0.4:
                significance = "moderate"
            elif abs_corr > 0.2:
                significance = "weak"
            else:
                significance = "none"

            # Heuristic confidence score (NOT a statistical p-value)
            # Higher score = higher confidence in the correlation
            # This is an internal metric for ranking correlations, not formal statistics
            significance_score = 0.95 if abs_corr > 0.7 else 0.80 if abs_corr > 0.5 else 0.60 if abs_corr > 0.3 else 0.30

            return CorrelationResult(
                metric_a=metric_a,
                metric_b=metric_b,
                correlation_coefficient=correlation,
                significance_score=significance_score,
                significance=significance,
            )

        except (statistics.StatisticsError, ZeroDivisionError):
            return None

    def detect_patterns(self) -> List[Dict[str, Any]]:
        """Detect patterns in metric history."""
        patterns: List[Dict[str, Any]] = []

        with self._lock:
            for metric_name, values in self._metric_history.items():
                if len(values) < 20:
                    continue

                values_list = list(values)

                # Detect oscillation
                if self._detect_oscillation(values_list):
                    patterns.append({
                        "type": "oscillation",
                        "metric": metric_name,
                        "description": f"Oscillating pattern detected in {metric_name}",
                        "confidence": 0.7,
                    })

                # Detect trend
                trend = self._detect_trend(values_list)
                if trend:
                    patterns.append({
                        "type": "trend",
                        "metric": metric_name,
                        "direction": trend,
                        "description": f"{trend.capitalize()} trend in {metric_name}",
                        "confidence": 0.8,
                    })

                # Detect periodicity (simplified)
                periodicity = self._detect_periodicity(values_list)
                if periodicity:
                    patterns.append({
                        "type": "periodic",
                        "metric": metric_name,
                        "period": periodicity,
                        "description": f"Periodic pattern (~{periodicity} samples) in {metric_name}",
                        "confidence": 0.6,
                    })

        return patterns

    def _detect_oscillation(self, values: List[float]) -> bool:
        """Detect if values are oscillating."""
        if len(values) < 10:
            return False

        # Count direction changes
        direction_changes = 0
        for i in range(2, len(values)):
            prev_diff = values[i - 1] - values[i - 2]
            curr_diff = values[i] - values[i - 1]
            if prev_diff * curr_diff < 0:  # Direction changed
                direction_changes += 1

        # If more than 40% of points are direction changes, it's oscillating
        return direction_changes / (len(values) - 2) > 0.4

    def _detect_trend(self, values: List[float]) -> Optional[str]:
        """Detect trend direction in values."""
        if len(values) < 10:
            return None

        # Simple linear regression
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)

        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return None

        slope = numerator / denominator

        # Determine trend significance
        if slope > 0.01 * y_mean:  # More than 1% increase per sample
            return "increasing"
        elif slope < -0.01 * y_mean:  # More than 1% decrease per sample
            return "decreasing"

        return None

    def _detect_periodicity(self, values: List[float]) -> Optional[int]:
        """Detect periodicity in values (simplified autocorrelation)."""
        if len(values) < 30:
            return None

        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0.0
        if std == 0:
            return None

        # Normalize values
        normalized = [(v - mean) / std for v in values]

        # Check autocorrelation at different lags
        best_lag = 0
        best_corr = 0.0

        for lag in range(5, min(len(values) // 3, 50)):
            corr = sum(
                normalized[i] * normalized[i + lag]
                for i in range(len(values) - lag)
            ) / (len(values) - lag)

            if corr > best_corr and corr > 0.5:
                best_corr = corr
                best_lag = lag

        return best_lag if best_lag > 0 else None

    def get_metric_statistics(self, metric_name: str) -> Optional[Dict[str, float]]:
        """Get statistics for a specific metric."""
        with self._lock:
            return self._baseline_stats.get(metric_name)


# =============================================================================
# CAUSAL ANALYSIS ENGINE
# =============================================================================

class CausalAnalysisEngine:
    """
    Layer 3: Multi-factor causal analysis for determining
    root causes and contributing factors of problems.
    """

    def __init__(self, config: AnalysisConfig, experience_store: ExperienceStore) -> None:
        self.config = config
        self.experience_store = experience_store
        self._causal_rules = self._build_causal_rules()

    def _build_causal_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Build causal rules for problem types."""
        return {
            ProblemType.ISP_OUTAGE.name: [
                {
                    "factor_id": "high_consecutive_loss",
                    "name": "High Consecutive Packet Loss",
                    "weight": 0.8,
                    "metrics": ["consecutive_losses", "packet_loss"],
                    "condition": lambda s: self._check_consecutive_losses(s),
                },
                {
                    "factor_id": "connection_lost",
                    "name": "Connection Lost",
                    "weight": 0.9,
                    "metrics": ["threshold_states"],
                    "condition": lambda s: s.get("threshold_states", {}).get("connection_lost", False),
                },
            ],
            ProblemType.HIGH_LATENCY.name: [
                {
                    "factor_id": "elevated_latency",
                    "name": "Elevated Latency",
                    "weight": 0.7,
                    "metrics": ["latency"],
                    "condition": lambda s: self._check_latency(s),
                },
                {
                    "factor_id": "high_jitter",
                    "name": "High Jitter",
                    "weight": 0.5,
                    "metrics": ["jitter"],
                    "condition": lambda s: self._check_jitter(s),
                },
            ],
            ProblemType.DNS_FAILURE.name: [
                {
                    "factor_id": "dns_resolve_failed",
                    "name": "DNS Resolution Failed",
                    "weight": 0.9,
                    "metrics": ["dns_status"],
                    "condition": lambda s: s.get("dns_status") == t("failed"),
                },
                {
                    "factor_id": "dns_slow",
                    "name": "Slow DNS Response",
                    "weight": 0.6,
                    "metrics": ["dns_resolve_time"],
                    "condition": lambda s: s.get("dns_resolve_time", 0) > 1000,
                },
            ],
            ProblemType.MTU_LOW.name: [
                {
                    "factor_id": "mtu_issue",
                    "name": "MTU Configuration Issue",
                    "weight": 0.8,
                    "metrics": ["mtu_status"],
                    "condition": lambda s: s.get("mtu_status") in [t("mtu_low"), t("mtu_fragmented")],
                },
            ],
            ProblemType.ROUTE_CHANGE.name: [
                {
                    "factor_id": "route_changed",
                    "name": "Network Route Changed",
                    "weight": 0.7,
                    "metrics": ["route_changed"],
                    "condition": lambda s: s.get("route_changed", False),
                },
                {
                    "factor_id": "hop_timeout",
                    "name": "Hop Timeout Detected",
                    "weight": 0.6,
                    "metrics": ["route_problematic_hop"],
                    "condition": lambda s: s.get("route_problematic_hop") is not None,
                },
            ],
        }

    def _check_consecutive_losses(self, snapshot: Dict[str, Any]) -> bool:
        """Check if consecutive losses exceed configured threshold."""
        return self.config.is_threshold_breached(
            "consecutive_losses",
            float(snapshot.get("consecutive_losses", 0)),
            level="critical",
        )

    def _check_latency(self, snapshot: Dict[str, Any]) -> bool:
        """Check if latency is elevated."""
        latency = snapshot.get("last_latency_ms")
        if latency and latency != t("na"):
            try:
                return self.config.is_threshold_breached(
                    "latency",
                    float(latency),
                    level="critical",
                )
            except (ValueError, TypeError):
                pass
        return False

    def _check_jitter(self, snapshot: Dict[str, Any]) -> bool:
        """Check if jitter exceeds configured threshold."""
        jitter = snapshot.get("jitter", 0)
        if isinstance(jitter, (int, float)):
            return self.config.is_threshold_breached(
                "jitter",
                float(jitter),
                level="critical",
            )
        return False

    def analyze_causes(
        self,
        problem_type: ProblemType,
        snapshot: Dict[str, Any],
        anomalies: List[MetricAnomaly],
        correlations: List[CorrelationResult],
    ) -> List[CausalFactor]:
        """
        Analyze potential causes for a detected problem.

        Uses multi-factor analysis considering:
        - Direct metric violations
        - Anomaly patterns
        - Correlations between metrics
        - Historical experience
        """
        factors: List[CausalFactor] = []

        # Apply causal rules
        rules = self._causal_rules.get(problem_type.name, [])
        for rule in rules:
            if rule["condition"](snapshot):
                factor = CausalFactor(
                    factor_id=rule["factor_id"],
                    name=rule["name"],
                    description=f"Detected via rule: {rule['factor_id']}",
                    contribution_weight=rule["weight"],
                    confidence=0.8,
                    related_metrics=rule["metrics"],
                    evidence=[f"Rule condition satisfied: {rule['factor_id']}"],
                )
                factors.append(factor)

        # Analyze anomalies as potential causes
        for anomaly in anomalies:
            factor = CausalFactor(
                factor_id=f"anomaly_{anomaly.metric_name}",
                name=f"{anomaly.metric_name.title()} Anomaly",
                description=f"Anomaly detected: {anomaly.anomaly_type.name}",
                contribution_weight=min(anomaly.deviation_sigma / 5.0, 1.0),
                confidence=0.7,
                related_metrics=[anomaly.metric_name],
                evidence=[f"Deviation: {anomaly.deviation_sigma:.2f} sigma"],
            )
            factors.append(factor)

        # Consider correlations
        for corr in correlations:
            if corr.is_significant and abs(corr.correlation_coefficient) > 0.6:
                factor = CausalFactor(
                    factor_id=f"corr_{corr.metric_a}_{corr.metric_b}",
                    name=f"Correlation: {corr.metric_a} <-> {corr.metric_b}",
                    description=f"Strong correlation ({corr.correlation_coefficient:.2f}) detected",
                    contribution_weight=abs(corr.correlation_coefficient) * 0.5,
                    confidence=0.6,
                    related_metrics=[corr.metric_a, corr.metric_b],
                    evidence=[f"Correlation coefficient: {corr.correlation_coefficient:.2f}"],
                )
                factors.append(factor)

        # Sort by contribution weight and mark root cause
        if factors:
            factors.sort(key=lambda f: f.contribution_weight, reverse=True)
            factors[0].is_root_cause = True

        return factors

    def identify_root_cause(self, factors: List[CausalFactor]) -> Optional[CausalFactor]:
        """Identify the most likely root cause from factors."""
        if not factors:
            return None

        # Return the factor with highest weight and confidence
        root_candidates = [f for f in factors if f.is_root_cause]
        if root_candidates:
            return root_candidates[0]

        return max(factors, key=lambda f: f.contribution_weight * f.confidence)


# =============================================================================
# CLASSIFICATION ENGINE
# =============================================================================

class ClassificationEngine:
    """
    Layer 4: Intelligent classification of problems with
    automatic type, severity, and priority determination.
    """

    def __init__(self, config: AnalysisConfig, experience_store: ExperienceStore) -> None:
        self.config = config
        self.experience_store = experience_store

    def classify_problem(
        self,
        snapshot: Dict[str, Any],
        anomalies: List[MetricAnomaly],
        causal_factors: List[CausalFactor],
    ) -> ProblemClassification:
        """
        Classify a problem based on all available evidence.

        Determines:
        - Problem type
        - Severity level
        - Priority for resolution
        - Confidence in classification
        """
        matched_rules = self.config.get_matching_rules(snapshot)
        matched_rule = matched_rules[0] if matched_rules else None

        # Determine problem type
        problem_type = matched_rule.problem_type if matched_rule else self._determine_type(snapshot, anomalies)

        # Determine severity
        severity = (
            matched_rule.severity
            if matched_rule
            else self._determine_severity(snapshot, anomalies, problem_type)
        )

        # Determine priority
        priority = (
            matched_rule.priority
            if matched_rule
            else self._determine_priority(problem_type, severity, causal_factors)
        )

        # Calculate confidence
        confidence = self._calculate_confidence(anomalies, causal_factors)
        if matched_rule:
            confidence = max(confidence, 0.85)

        # Build description
        description = self._build_description(problem_type, severity, causal_factors)
        if matched_rule:
            description = f"{description} (configured rule: {matched_rule.name})"

        # Identify affected components
        affected = self._identify_affected_components(snapshot, problem_type)

        # Impact assessment
        impact = self._assess_impact(problem_type, severity, snapshot)

        return ProblemClassification(
            problem_type=problem_type,
            severity=severity,
            priority=priority,
            confidence=confidence,
            description=description,
            affected_components=affected,
            impact_assessment=impact,
        )

    def _determine_type(self, snapshot: Dict[str, Any], anomalies: List[MetricAnomaly]) -> ProblemType:
        """Determine the type of problem."""
        # Check for connection loss first (highest priority)
        connection_lost = snapshot.get("threshold_states", {}).get("connection_lost", False)
        consecutive_losses = float(snapshot.get("consecutive_losses", 0))

        if connection_lost or self.config.is_threshold_breached(
            "consecutive_losses",
            consecutive_losses,
            level="critical",
        ):
            return ProblemType.ISP_OUTAGE

        # Check DNS
        dns_status = snapshot.get("dns_status", "")
        if dns_status == t("failed"):
            return ProblemType.DNS_FAILURE
        elif dns_status == t("slow"):
            return ProblemType.DNS_SLOW

        # Check MTU
        mtu_status = snapshot.get("mtu_status", "")
        if mtu_status == t("mtu_low"):
            return ProblemType.MTU_LOW
        elif mtu_status == t("mtu_fragmented"):
            return ProblemType.MTU_FRAGMENTED

        # Check route
        if snapshot.get("route_changed", False):
            return ProblemType.ROUTE_CHANGE

        latency = snapshot.get("last_latency_ms")
        if latency and latency != t("na"):
            try:
                if self.config.is_threshold_breached("latency", float(latency), level="critical"):
                    return ProblemType.HIGH_LATENCY
            except (ValueError, TypeError):
                pass

        # Check for high latency
        latency_anomaly = next(
            (a for a in anomalies if a.metric_name == "latency"),
            None
        )
        if latency_anomaly:
            return ProblemType.HIGH_LATENCY

        jitter = snapshot.get("jitter", 0)
        if isinstance(jitter, (int, float)) and self.config.is_threshold_breached(
            "jitter",
            float(jitter),
            level="critical",
        ):
            return ProblemType.HIGH_JITTER

        # Check for jitter
        jitter_anomaly = next(
            (a for a in anomalies if a.metric_name == "jitter"),
            None
        )
        if jitter_anomaly:
            return ProblemType.HIGH_JITTER

        recent_results = snapshot.get("recent_results", [])
        total = snapshot.get("total", 1)
        failure = snapshot.get("failure", 0)
        loss_pct = (
            (recent_results.count(False) / len(recent_results)) * 100
            if recent_results
            else (failure / total) * 100 if total > 0 else 0.0
        )
        if self.config.is_threshold_breached("packet_loss", loss_pct, level="critical"):
            return ProblemType.PACKET_LOSS

        # Check for packet loss
        loss_anomaly = next(
            (a for a in anomalies if a.metric_name == "packet_loss"),
            None
        )
        if loss_anomaly:
            return ProblemType.PACKET_LOSS

        return ProblemType.UNKNOWN

    def _determine_severity(
        self,
        snapshot: Dict[str, Any],
        anomalies: List[MetricAnomaly],
        problem_type: ProblemType,
    ) -> ProblemSeverity:
        """Determine severity level of the problem."""
        # Critical: Connection completely lost
        if problem_type == ProblemType.ISP_OUTAGE:
            if snapshot.get("threshold_states", {}).get("connection_lost", False):
                return ProblemSeverity.CRITICAL
            return ProblemSeverity.HIGH

        # High: DNS failure or high packet loss
        if problem_type == ProblemType.DNS_FAILURE:
            return ProblemSeverity.HIGH

        # Check anomaly severity
        max_deviation = max(
            (a.deviation_sigma for a in anomalies),
            default=0.0
        )

        if max_deviation > 4.0:
            return ProblemSeverity.HIGH
        elif max_deviation > 3.0:
            return ProblemSeverity.MEDIUM
        elif max_deviation > 2.0:
            return ProblemSeverity.LOW

        # Default based on problem type
        if problem_type in [ProblemType.ROUTE_CHANGE, ProblemType.MTU_LOW]:
            return ProblemSeverity.MEDIUM

        return ProblemSeverity.LOW

    def _determine_priority(
        self,
        problem_type: ProblemType,
        severity: ProblemSeverity,
        causal_factors: List[CausalFactor],
    ) -> ProblemPriority:
        """Determine priority for resolution."""
        # Critical severity = urgent priority
        if severity == ProblemSeverity.CRITICAL:
            return ProblemPriority.URGENT

        # High severity = high priority
        if severity == ProblemSeverity.HIGH:
            return ProblemPriority.HIGH

        # Consider historical frequency
        frequency = self.experience_store.get_problem_frequency(problem_type, hours=1)

        if frequency >= 3:
            # Recurring problem - increase priority
            if severity == ProblemSeverity.MEDIUM:
                return ProblemPriority.HIGH

        # Consider root cause confidence
        root_cause = next((f for f in causal_factors if f.is_root_cause), None)
        if root_cause and root_cause.confidence > 0.8:
            # Clear root cause - can be addressed efficiently
            return ProblemPriority.MEDIUM

        return ProblemPriority.LOW

    def _calculate_confidence(
        self,
        anomalies: List[MetricAnomaly],
        causal_factors: List[CausalFactor],
    ) -> float:
        """Calculate confidence in the classification."""
        if not anomalies and not causal_factors:
            return 0.3

        # Base confidence from anomalies
        anomaly_confidence = 0.0
        if anomalies:
            avg_deviation = sum(a.deviation_sigma for a in anomalies) / len(anomalies)
            anomaly_confidence = min(avg_deviation / 5.0, 0.5)

        # Factor confidence
        factor_confidence = 0.0
        if causal_factors:
            factor_confidence = sum(f.confidence for f in causal_factors) / len(causal_factors) * 0.5

        return min(anomaly_confidence + factor_confidence, 0.95)

    def _build_description(
        self,
        problem_type: ProblemType,
        severity: ProblemSeverity,
        causal_factors: List[CausalFactor],
    ) -> str:
        """Build human-readable description."""
        base = f"{severity.name} severity {problem_type.name.lower().replace('_', ' ')}"

        if causal_factors:
            root = next((f for f in causal_factors if f.is_root_cause), None)
            if root:
                base += f" caused by {root.name.lower()}"

        return base

    def _identify_affected_components(
        self,
        snapshot: Dict[str, Any],
        problem_type: ProblemType,
    ) -> List[str]:
        """Identify components affected by the problem."""
        affected = []

        if problem_type in [ProblemType.ISP_OUTAGE, ProblemType.PACKET_LOSS]:
            affected.append("network_connectivity")
            affected.append("data_transfer")

        if problem_type == ProblemType.DNS_FAILURE:
            affected.append("dns_resolution")
            affected.append("name_resolution")

        if problem_type == ProblemType.HIGH_LATENCY:
            affected.append("response_time")
            affected.append("user_experience")

        if problem_type == ProblemType.ROUTE_CHANGE:
            affected.append("network_path")
            affected.append("routing")

        if problem_type in [ProblemType.MTU_LOW, ProblemType.MTU_FRAGMENTED]:
            affected.append("packet_transmission")
            affected.append("data_integrity")

        return affected

    def _assess_impact(
        self,
        problem_type: ProblemType,
        severity: ProblemSeverity,
        snapshot: Dict[str, Any],
    ) -> str:
        """Assess the impact of the problem."""
        if severity == ProblemSeverity.CRITICAL:
            return "Complete service disruption. Immediate attention required."

        if severity == ProblemSeverity.HIGH:
            return "Significant degradation. Users likely experiencing issues."

        if severity == ProblemSeverity.MEDIUM:
            return "Noticeable impact. Performance degradation detected."

        if severity == ProblemSeverity.LOW:
            return "Minor impact. May affect some operations."

        return "Informational. No immediate impact detected."


# =============================================================================
# SOLUTION GENERATOR
# =============================================================================

class SolutionGenerator:
    """
    Layer 6: Generate actionable solutions with effectiveness
    estimation and risk assessment.
    """

    def __init__(self, config: AnalysisConfig, experience_store: ExperienceStore) -> None:
        self.config = config
        self.experience_store = experience_store
        self._solution_templates = self._build_solution_templates()

    def _build_solution_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """Build solution templates for problem types."""
        return {
            ProblemType.ISP_OUTAGE.name: [
                {
                    "id": "check_isp_status",
                    "title": "Check ISP Status",
                    "description": "Verify if there's a known outage with your ISP",
                    "steps": [
                        "Visit your ISP's status page",
                        "Check social media for outage reports",
                        "Contact ISP support if outage is confirmed",
                    ],
                    "effectiveness": 0.8,
                    "risk": "low",
                    "cost": "low",
                    "time": 5,
                },
                {
                    "id": "restart_network_equipment",
                    "title": "Restart Network Equipment",
                    "description": "Power cycle your modem and router",
                    "steps": [
                        "Unplug modem and router",
                        "Wait 30 seconds",
                        "Plug in modem first, wait for sync",
                        "Plug in router, wait for startup",
                    ],
                    "effectiveness": 0.7,
                    "risk": "low",
                    "cost": "low",
                    "time": 10,
                },
            ],
            ProblemType.DNS_FAILURE.name: [
                {
                    "id": "change_dns_server",
                    "title": "Change DNS Server",
                    "description": "Switch to a reliable public DNS server",
                    "steps": [
                        "Open network settings",
                        "Change DNS to 8.8.8.8 (Google) or 1.1.1.1 (Cloudflare)",
                        "Flush DNS cache",
                        "Test resolution",
                    ],
                    "effectiveness": 0.85,
                    "risk": "low",
                    "cost": "low",
                    "time": 5,
                },
                {
                    "id": "flush_dns_cache",
                    "title": "Flush DNS Cache",
                    "description": "Clear local DNS cache",
                    "steps": [
                        "Open command prompt/terminal",
                        "Run: ipconfig /flushdns (Windows) or sudo dscacheutil -flushcache (macOS)",
                        "Test DNS resolution",
                    ],
                    "effectiveness": 0.6,
                    "risk": "low",
                    "cost": "low",
                    "time": 2,
                },
            ],
            ProblemType.HIGH_LATENCY.name: [
                {
                    "id": "check_network_congestion",
                    "title": "Check Network Congestion",
                    "description": "Identify and resolve network congestion",
                    "steps": [
                        "Check for heavy bandwidth usage",
                        "Pause large downloads/uploads",
                        "Disconnect unused devices",
                        "Consider QoS settings on router",
                    ],
                    "effectiveness": 0.7,
                    "risk": "low",
                    "cost": "low",
                    "time": 10,
                },
                {
                    "id": "optimize_wifi",
                    "title": "Optimize WiFi Connection",
                    "description": "Improve WiFi signal and reduce interference",
                    "steps": [
                        "Move closer to router",
                        "Switch to less congested channel",
                        "Consider 5GHz band if available",
                        "Check for interference sources",
                    ],
                    "effectiveness": 0.65,
                    "risk": "low",
                    "cost": "low",
                    "time": 15,
                },
            ],
            ProblemType.MTU_LOW.name: [
                {
                    "id": "adjust_mtu",
                    "title": "Adjust MTU Settings",
                    "description": "Configure optimal MTU for your connection",
                    "steps": [
                        "Test optimal MTU with ping tests",
                        "Adjust MTU in network adapter settings",
                        "Common values: 1500 (default), 1492 (PPPoE), 1400 (VPN)",
                        "Test connection after changes",
                    ],
                    "effectiveness": 0.8,
                    "risk": "medium",
                    "cost": "low",
                    "time": 15,
                },
            ],
            ProblemType.ROUTE_CHANGE.name: [
                {
                    "id": "monitor_route",
                    "title": "Monitor Route Stability",
                    "description": "Track route changes and identify patterns",
                    "steps": [
                        "Run traceroute to destination",
                        "Compare with previous routes",
                        "Note problematic hops",
                        "Contact ISP if route is suboptimal",
                    ],
                    "effectiveness": 0.6,
                    "risk": "low",
                    "cost": "low",
                    "time": 10,
                },
            ],
        }

    def generate_solutions(
        self,
        classification: ProblemClassification,
        causal_factors: List[CausalFactor],
    ) -> List[SolutionRecommendation]:
        """Generate solution recommendations for a problem."""
        solutions: List[SolutionRecommendation] = []

        # Get templates for problem type
        templates = self._solution_templates.get(
            classification.problem_type.name,
            []
        )

        for template in templates:
            # Get historical success rate
            historical_rate = self.experience_store.get_solution_success_rate(template["id"])

            # Adjust effectiveness based on historical data
            base_effectiveness = template["effectiveness"]
            if historical_rate is not None:
                # Weight towards historical data when we have it
                adjusted_effectiveness = (base_effectiveness * 0.3) + (historical_rate * 0.7)
            else:
                # No history - use template's base effectiveness score
                adjusted_effectiveness = base_effectiveness

            solution = SolutionRecommendation(
                solution_id=template["id"],
                title=template["title"],
                description=template["description"],
                steps=template["steps"],
                effectiveness_score=adjusted_effectiveness,
                risk_level=template["risk"],
                resource_cost=template["cost"],
                estimated_time_minutes=template["time"],
                success_probability=adjusted_effectiveness,
                historical_success_rate=historical_rate if historical_rate is not None else 0.0,
            )
            solutions.append(solution)

        # Add factor-specific solutions
        for factor in causal_factors:
            if factor.is_root_cause:
                factor_solutions = self._generate_factor_specific_solutions(factor)
                solutions.extend(factor_solutions)

        # Sort by effectiveness
        solutions.sort(key=lambda s: s.effectiveness_score, reverse=True)

        return solutions[:5]  # Return top 5 solutions

    def _generate_factor_specific_solutions(self, factor: CausalFactor) -> List[SolutionRecommendation]:
        """Generate solutions specific to a causal factor."""
        solutions: List[SolutionRecommendation] = []

        # Add solutions based on factor type
        if "consecutive_loss" in factor.factor_id:
            solutions.append(SolutionRecommendation(
                solution_id=f"factor_{factor.factor_id}_check",
                title="Investigate Connection Stability",
                description="Check for intermittent connection issues",
                steps=[
                    "Monitor connection over time",
                    "Check cable connections",
                    "Verify signal strength if using WiFi",
                ],
                effectiveness_score=0.75,
                risk_level="low",
                resource_cost="low",
                estimated_time_minutes=10,
            ))

        if "dns" in factor.factor_id.lower():
            solutions.append(SolutionRecommendation(
                solution_id=f"factor_{factor.factor_id}_dns",
                title="DNS Troubleshooting",
                description="Comprehensive DNS diagnostics",
                steps=[
                    "Test with alternative DNS servers",
                    "Check DNS configuration",
                    "Verify domain resolution",
                ],
                effectiveness_score=0.8,
                risk_level="low",
                resource_cost="low",
                estimated_time_minutes=8,
            ))

        return solutions


# =============================================================================
# PREDICTIVE ANALYTICS ENGINE
# =============================================================================

class PredictiveEngine:
    """
    Layer 7: Predictive analytics for forecasting potential
    problems before they occur.
    """

    def __init__(self, config: AnalysisConfig, experience_store: ExperienceStore) -> None:
        self.config = config
        self.experience_store = experience_store
        self._prediction_history: deque[PredictionResult] = deque(maxlen=100)
        self._trend_data: Dict[str, List[Tuple[datetime, float]]] = {}

    def update_trend_data(self, metric_name: str, value: float) -> None:
        """Update trend data for a metric."""
        now = datetime.now(timezone.utc)
        if metric_name not in self._trend_data:
            self._trend_data[metric_name] = []
        self._trend_data[metric_name].append((now, value))

        # Keep only recent data
        cutoff = now - timedelta(hours=1)
        self._trend_data[metric_name] = [
            (t, v) for t, v in self._trend_data[metric_name]
            if t >= cutoff
        ]

    def predict_problems(
        self,
        snapshot: Dict[str, Any],
        anomalies: List[MetricAnomaly],
        store_predictions: bool = True,
    ) -> List[PredictionResult]:
        """Generate predictions about potential future problems.

        Args:
            snapshot: Current metrics snapshot
            anomalies: Detected anomalies
            store_predictions: If True, store predictions in history for accuracy tracking.
                             Set to False for read-only queries like get_predictions().
        """
        predictions: List[PredictionResult] = []

        # Trend-based predictions
        trend_predictions = self._analyze_trends()
        predictions.extend(trend_predictions)

        # Pattern-based predictions
        pattern_predictions = self._analyze_patterns(snapshot)
        predictions.extend(pattern_predictions)

        # Historical frequency predictions
        history_predictions = self._analyze_history()
        predictions.extend(history_predictions)

        # Anomaly escalation predictions
        if anomalies:
            escalation_pred = self._predict_escalation(anomalies)
            if escalation_pred:
                predictions.append(escalation_pred)

        # Store predictions only when explicitly requested (e.g., during analysis)
        if store_predictions:
            for pred in predictions:
                self._prediction_history.append(pred)

        return predictions

    def _analyze_trends(self) -> List[PredictionResult]:
        """Analyze trends for potential problems."""
        predictions: List[PredictionResult] = []

        for metric_name, data_points in self._trend_data.items():
            if len(data_points) < 10:
                continue

            # Extract values and timestamps
            values = [v for _, v in data_points]
            if len(values) < 10:
                continue

            # Calculate trend
            trend = self._calculate_trend_slope(values)
            if trend is None:
                continue

            # Get threshold
            threshold_config = self.config.thresholds.get(metric_name)
            if not threshold_config:
                continue

            # Predict if trend will cross threshold
            current_value = values[-1]
            time_to_threshold = self._estimate_time_to_threshold(
                current_value, trend, threshold_config.critical_threshold
            )

            if time_to_threshold is not None and time_to_threshold < self.config.prediction_horizon_minutes:
                predictions.append(PredictionResult(
                    prediction_type="trend_based",
                    probability=min(0.9, abs(trend) * 10),
                    time_horizon_minutes=int(time_to_threshold),
                    predicted_problem_type=self._metric_to_problem_type(metric_name),
                    confidence=0.7,
                    contributing_factors=[f"Increasing trend in {metric_name}"],
                    preventive_actions=self._get_preventive_actions(metric_name),
                ))

        return predictions

    def _calculate_trend_slope(self, values: List[float]) -> Optional[float]:
        """Calculate the slope of a trend using linear regression."""
        n = len(values)
        if n < 2:
            return None

        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)

        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return None

        return numerator / denominator

    def _estimate_time_to_threshold(
        self,
        current: float,
        slope: float,
        threshold: float,
    ) -> Optional[float]:
        """Estimate minutes until threshold is reached.

        Uses the configured ping interval (INTERVAL) to convert
        samples to real time, ensuring accurate predictions regardless
        of the actual ping frequency.
        """
        if slope <= 0:
            return None  # Not increasing

        if current >= threshold:
            return 0  # Already at threshold

        # Linear extrapolation: slope is per sample
        # Convert samples to seconds using the real ping interval
        samples_to_threshold = (threshold - current) / slope
        seconds_to_threshold = samples_to_threshold * self.config.ping_interval_seconds
        return seconds_to_threshold / 60  # Convert to minutes

    def _metric_to_problem_type(self, metric_name: str) -> ProblemType:
        """Map metric name to problem type."""
        mapping = {
            "latency": ProblemType.HIGH_LATENCY,
            "jitter": ProblemType.HIGH_JITTER,
            "packet_loss": ProblemType.PACKET_LOSS,
        }
        return mapping.get(metric_name, ProblemType.UNKNOWN)

    def _get_preventive_actions(self, metric_name: str) -> List[str]:
        """Get preventive actions for a metric."""
        actions = {
            "latency": [
                "Monitor network usage",
                "Check for bandwidth-heavy applications",
                "Consider QoS prioritization",
            ],
            "jitter": [
                "Check for network congestion",
                "Verify stable connection",
                "Consider wired connection over WiFi",
            ],
            "packet_loss": [
                "Check cable connections",
                "Monitor for interference",
                "Verify router health",
            ],
        }
        return actions.get(metric_name, ["Monitor the situation"])

    def _analyze_patterns(self, snapshot: Dict[str, Any]) -> List[PredictionResult]:
        """Analyze patterns for predictions using time-based seasonality."""
        predictions: List[PredictionResult] = []

        # Time-based pattern analysis
        current_hour = datetime.now(timezone.utc).hour

        # Check for time-based patterns from history
        for problem_type in ProblemType:
            # Get hourly distribution for this problem type
            hourly_dist = self.experience_store.get_hourly_distribution(
                problem_type, days_back=7
            )

            if not hourly_dist:
                continue

            # Calculate average hourly rate
            total_problems = sum(hourly_dist.values())
            if total_problems < 3:
                continue  # Need at least 3 occurrences for pattern detection

            avg_per_hour = total_problems / 24
            current_hour_count = hourly_dist.get(current_hour, 0)

            # Check if current hour has significantly higher rate than average
            # Using a threshold of 2x average to detect "peak hours"
            if avg_per_hour > 0 and current_hour_count >= avg_per_hour * 2:
                # This is a peak hour for this problem type
                probability = min(0.85, current_hour_count / (avg_per_hour * 3))
                predictions.append(PredictionResult(
                    prediction_type="time_based_seasonality",
                    probability=probability,
                    time_horizon_minutes=60,
                    predicted_problem_type=problem_type,
                    confidence=0.75,
                    contributing_factors=[
                        f"Peak hour pattern: {current_hour_count} occurrences at hour {current_hour}:00",
                        f"Average: {avg_per_hour:.1f}/hour, Current: {current_hour_count}",
                    ],
                    preventive_actions=[
                        "Monitor closely during this hour",
                        "Prepare mitigation steps",
                        "Consider proactive measures",
                    ],
                ))
            elif current_hour_count >= 2 and current_hour_count > avg_per_hour:
                # Moderate increase at this hour
                probability = min(0.65, current_hour_count / (avg_per_hour * 2 + 1))
                predictions.append(PredictionResult(
                    prediction_type="time_based_pattern",
                    probability=probability,
                    time_horizon_minutes=60,
                    predicted_problem_type=problem_type,
                    confidence=0.55,
                    contributing_factors=[
                        f"Elevated occurrence at hour {current_hour}:00 ({current_hour_count} times)",
                    ],
                    preventive_actions=["Monitor closely"],
                ))

            # Also check for upcoming peak hours (within next 2 hours)
            for next_hour_offset in range(1, 3):
                next_hour = (current_hour + next_hour_offset) % 24
                next_hour_count = hourly_dist.get(next_hour, 0)
                if avg_per_hour > 0 and next_hour_count >= avg_per_hour * 2:
                    predictions.append(PredictionResult(
                        prediction_type="upcoming_peak_hour",
                        probability=min(0.70, next_hour_count / (avg_per_hour * 3)),
                        time_horizon_minutes=next_hour_offset * 60,
                        predicted_problem_type=problem_type,
                        confidence=0.60,
                        contributing_factors=[
                            f"Upcoming peak hour: {next_hour}:00 ({next_hour_count} historical occurrences)",
                        ],
                        preventive_actions=[
                            f"Prepare for increased {problem_type.name.lower()} risk at {next_hour}:00",
                        ],
                    ))

        return predictions

    def _analyze_history(self) -> List[PredictionResult]:
        """Analyze historical data for predictions."""
        predictions: List[PredictionResult] = []

        # Get overall statistics
        stats = self.experience_store.get_statistics()

        # Check for patterns in problem distribution
        pattern_dist = stats.get("pattern_distribution", {})
        total = sum(pattern_dist.values())

        if total > 0:
            for problem_name, count in pattern_dist.items():
                probability = count / total
                if probability > 0.3:  # More than 30% of problems
                    try:
                        problem_type = ProblemType[problem_name]
                        predictions.append(PredictionResult(
                            prediction_type="historical_frequency",
                            probability=probability,
                            time_horizon_minutes=120,
                            predicted_problem_type=problem_type,
                            confidence=0.5,
                            contributing_factors=[f"Historical frequency: {probability:.1%}"],
                            preventive_actions=self._get_preventive_actions(problem_name.lower()),
                        ))
                    except KeyError:
                        pass

        return predictions

    def _predict_escalation(self, anomalies: List[MetricAnomaly]) -> Optional[PredictionResult]:
        """Predict if current anomalies will escalate."""
        if not anomalies:
            return None

        # Check for multiple anomalies
        if len(anomalies) >= 2:
            return PredictionResult(
                prediction_type="anomaly_escalation",
                probability=0.7,
                time_horizon_minutes=15,
                predicted_problem_type=ProblemType.CASCADING,
                confidence=0.6,
                contributing_factors=[f"Multiple anomalies: {len(anomalies)}"],
                preventive_actions=[
                    "Investigate all anomalies immediately",
                    "Check for common root cause",
                ],
            )

        # Check for severe anomaly
        severe_anomalies = [a for a in anomalies if a.deviation_sigma > 3.0]
        if severe_anomalies:
            return PredictionResult(
                prediction_type="severe_anomaly",
                probability=0.8,
                time_horizon_minutes=10,
                predicted_problem_type=self._metric_to_problem_type(severe_anomalies[0].metric_name),
                confidence=0.7,
                contributing_factors=[f"Severe anomaly: {severe_anomalies[0].deviation_sigma:.1f} sigma"],
                preventive_actions=self._get_preventive_actions(severe_anomalies[0].metric_name),
            )

        return None

    def get_prediction_accuracy(self) -> float:
        """Calculate prediction accuracy from history."""
        # This would compare predictions with actual outcomes
        # Simplified implementation
        if len(self._prediction_history) < 10:
            return 0.5

        # In a real implementation, we would track which predictions came true
        return 0.7  # Placeholder


# =============================================================================
# REPORT GENERATOR
# =============================================================================

class ReportGenerator:
    """
    Layer 8: Generate comprehensive reports with visualization
    data and actionable recommendations.
    """

    def __init__(
        self,
        config: AnalysisConfig,
        experience_store: ExperienceStore,
        deep_analyzer: Optional[DeepAnalysisEngine] = None,
        predictive_engine: Optional[PredictiveEngine] = None,
    ) -> None:
        self.config = config
        self.experience_store = experience_store
        self._deep_analyzer = deep_analyzer
        self._predictive_engine = predictive_engine

    def generate_report(
        self,
        time_range: Tuple[datetime, datetime],
        include_predictions: bool = True,
    ) -> AnalysisReport:
        """Generate a comprehensive analysis report.

        The report filters data by the specified time_range to provide
        accurate period-specific analysis.
        """
        start_time, end_time = time_range

        # Get statistics filtered by time range
        stats = self.experience_store.get_statistics_for_time_range(start_time, end_time)

        # Get records for the time range
        records = self.experience_store.get_records_in_time_range(start_time, end_time)

        # Generate summary with time-filtered data
        summary = self._generate_summary(stats, start_time, end_time)

        # Problem statistics with time-filtered data
        problem_stats = self._generate_problem_statistics(stats)

        # Trend analysis using deep analyzer
        trend_analysis = self._generate_trend_analysis()

        # Patterns from time-filtered records
        patterns = self._generate_patterns_section(stats, records)

        # Recommendations based on time-filtered data
        recommendations = self._generate_recommendations(stats)

        # Predictions using predictive engine
        predictions: List[PredictionResult] = []
        if include_predictions and self._predictive_engine:
            predictions = self._generate_predictions_section()

        # Metrics summary from deep analyzer
        metrics_summary = self._generate_metrics_summary(start_time, end_time)

        # Health score based on time-filtered stats
        health_score = self._calculate_health_score(stats)

        return AnalysisReport(
            report_id=f"report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            generated_at=datetime.now(timezone.utc),
            time_range=time_range,
            summary=summary,
            problem_statistics=problem_stats,
            trend_analysis=trend_analysis,
            patterns_detected=patterns,
            recommendations=recommendations,
            predictions=predictions,
            metrics_summary=metrics_summary,
            health_score=health_score,
        )

    def _generate_summary(
        self,
        stats: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
    ) -> str:
        """Generate executive summary for the specified time range."""
        total = stats.get("total_problems", 0)
        resolved = stats.get("resolved_problems", 0)
        rate = stats.get("resolution_rate", 0.0)

        duration_hours = (end_time - start_time).total_seconds() / 3600

        if total == 0:
            return (
                f"No problems detected in the last {duration_hours:.1f} hours. "
                "System is operating normally."
            )

        health_status = "good" if rate > 0.8 else "needs attention"

        return (
            f"Analyzed {total} problem(s) over {duration_hours:.1f} hours "
            f"with {rate:.0%} resolution rate. "
            f"{resolved} problem(s) were successfully resolved. "
            f"System health is {health_status}."
        )

    def _generate_problem_statistics(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Generate problem statistics section from filtered stats."""
        return {
            "total_problems": stats.get("total_problems", 0),
            "resolved_problems": stats.get("resolved_problems", 0),
            "resolution_rate": stats.get("resolution_rate", 0.0),
            "severity_distribution": stats.get("severity_distribution", {}),
            "pattern_distribution": stats.get("pattern_distribution", {}),
        }

    def _generate_trend_analysis(self) -> Dict[str, Any]:
        """Generate trend analysis section using deep analyzer data."""
        trend_analysis: Dict[str, Any] = {
            "latency_trend": "stable",
            "packet_loss_trend": "stable",
            "jitter_trend": "stable",
            "overall_trend": "stable",
            "details": {},
        }

        if self._deep_analyzer is None:
            return trend_analysis

        # Analyze trends for each metric
        metrics_to_analyze = ["latency", "packet_loss", "jitter"]
        trends_found: List[str] = []

        for metric_name in metrics_to_analyze:
            metric_stats = self._deep_analyzer.get_metric_statistics(metric_name)

            if metric_stats is None or metric_stats.get("count", 0) < 10:
                continue

            # Get the trend from deep analyzer's pattern detection
            values = list(self._deep_analyzer._metric_history.get(metric_name, []))
            if len(values) < 10:
                continue

            trend = self._deep_analyzer._detect_trend(values)
            if trend:
                trend_analysis[f"{metric_name}_trend"] = trend
                trends_found.append(trend)
            else:
                trend_analysis[f"{metric_name}_trend"] = "stable"

            # Add detailed statistics
            trend_analysis["details"][metric_name] = {
                "mean": metric_stats.get("mean", 0),
                "std_dev": metric_stats.get("std_dev", 0),
                "min": metric_stats.get("min", 0),
                "max": metric_stats.get("max", 0),
                "sample_count": metric_stats.get("count", 0),
            }

        # Determine overall trend
        if trends_found:
            increasing_count = trends_found.count("increasing")
            decreasing_count = trends_found.count("decreasing")

            if increasing_count > decreasing_count and increasing_count > len(trends_found) // 2:
                trend_analysis["overall_trend"] = "degrading"
            elif decreasing_count > increasing_count and decreasing_count > len(trends_found) // 2:
                trend_analysis["overall_trend"] = "improving"

        return trend_analysis

    def _generate_patterns_section(
        self,
        stats: Dict[str, Any],
        records: List[ProblemRecord],
    ) -> List[Dict[str, Any]]:
        """Generate patterns detected section from filtered records."""
        patterns: List[Dict[str, Any]] = []

        # Frequency patterns from statistics
        pattern_dist = stats.get("pattern_distribution", {})

        for problem_name, count in pattern_dist.items():
            if count > 0:
                patterns.append({
                    "type": "frequency_pattern",
                    "problem_type": problem_name,
                    "occurrences": count,
                    "significance": "high" if count > 5 else "medium" if count > 2 else "low",
                })

        # Time-based patterns from records
        if len(records) >= 5:
            hour_counts: Dict[int, int] = {}
            for record in records:
                hour = record.classification.timestamp.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1

            # Find peak hours
            if hour_counts:
                max_hour = max(hour_counts, key=hour_counts.get)
                max_count = hour_counts[max_hour]
                if max_count >= 3:
                    patterns.append({
                        "type": "temporal_pattern",
                        "description": f"Peak problem hour: {max_hour}:00 ({max_count} occurrences)",
                        "significance": "high" if max_count > 5 else "medium",
                    })

        # Metric patterns from deep analyzer
        if self._deep_analyzer:
            detected_patterns = self._deep_analyzer.detect_patterns()
            for p in detected_patterns:
                patterns.append({
                    "type": p.get("type", "metric_pattern"),
                    "metric": p.get("metric", "unknown"),
                    "description": p.get("description", ""),
                    "confidence": p.get("confidence", 0.5),
                    "significance": "high" if p.get("confidence", 0) > 0.7 else "medium",
                })

        return patterns

    def _generate_recommendations(self, stats: Dict[str, Any]) -> List[SolutionRecommendation]:
        """Generate recommendations based on filtered statistics."""
        recommendations: List[SolutionRecommendation] = []

        pattern_dist = stats.get("pattern_distribution", {})

        for problem_name, count in sorted(pattern_dist.items(), key=lambda x: x[1], reverse=True)[:3]:
            try:
                problem_type = ProblemType[problem_name]
                effective = self.experience_store.get_effective_solutions(problem_type)

                for solution_id, effectiveness in effective[:2]:
                    recommendations.append(SolutionRecommendation(
                        solution_id=solution_id,
                        title=f"Address {problem_name.replace('_', ' ').title()}",
                        description=f"Based on {count} occurrences in the analysis period",
                        steps=["See detailed solution documentation"],
                        effectiveness_score=effectiveness,
                        risk_level="low",
                        resource_cost="low",
                        estimated_time_minutes=15,
                    ))
            except KeyError:
                pass

        return recommendations

    def _generate_predictions_section(self) -> List[PredictionResult]:
        """Generate predictions section using predictive engine."""
        if self._predictive_engine is None:
            return []

        # Get recent predictions from predictive engine
        predictions = list(self._predictive_engine._prediction_history)

        # Return only recent predictions (last hour)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_predictions = [
            p for p in predictions
            if p.timestamp >= cutoff
        ]

        return recent_predictions

    def _generate_metrics_summary(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Generate metrics summary from deep analyzer data."""
        duration_hours = (end_time - start_time).total_seconds() / 3600

        metrics_summary: Dict[str, Any] = {
            "monitoring_duration_hours": duration_hours,
            "total_pings": 0,
            "average_latency_ms": "N/A",
            "packet_loss_percent": "N/A",
            "average_jitter_ms": "N/A",
        }

        if self._deep_analyzer is None:
            return metrics_summary

        # Get statistics from deep analyzer
        for metric_name in ["latency", "jitter", "packet_loss"]:
            metric_stats = self._deep_analyzer.get_metric_statistics(metric_name)
            if metric_stats:
                if metric_name == "latency":
                    metrics_summary["average_latency_ms"] = round(metric_stats.get("mean", 0), 2)
                    metrics_summary["total_pings"] = metric_stats.get("count", 0)
                elif metric_name == "jitter":
                    metrics_summary["average_jitter_ms"] = round(metric_stats.get("mean", 0), 2)
                elif metric_name == "packet_loss":
                    metrics_summary["packet_loss_percent"] = round(metric_stats.get("mean", 0), 2)

        return metrics_summary

    def _calculate_health_score(self, stats: Dict[str, Any]) -> float:
        """Calculate overall health score (0-100) from filtered stats."""
        resolution_rate = stats.get("resolution_rate", 1.0)
        total_problems = stats.get("total_problems", 0)

        if total_problems == 0:
            return 100.0

        # Base score from resolution rate
        base_score = resolution_rate * 80

        # Penalty for problem frequency
        frequency_penalty = min(total_problems * 2, 30)

        # Calculate final score
        score = base_score + (100 - base_score) * 0.2 - frequency_penalty

        return max(0.0, min(100.0, score))


# =============================================================================
# EXTERNAL INTEGRATION LAYER
# =============================================================================

class ExternalIntegration:
    """
    Integration with external systems: logging, monitoring, metrics.
    """

    def __init__(self) -> None:
        self._log_handlers: List[Callable[[Dict[str, Any]], None]] = []
        self._metric_handlers: List[Callable[[str, float], None]] = []
        self._alert_handlers: List[Callable[[ProblemRecord], None]] = []

    def register_log_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Register a log handler."""
        self._log_handlers.append(handler)

    def register_metric_handler(self, handler: Callable[[str, float], None]) -> None:
        """Register a metric handler."""
        self._metric_handlers.append(handler)

    def register_alert_handler(self, handler: Callable[[ProblemRecord], None]) -> None:
        """Register an alert handler."""
        self._alert_handlers.append(handler)

    def emit_log(self, data: Dict[str, Any]) -> None:
        """Emit log to all registered handlers."""
        for handler in self._log_handlers:
            try:
                handler(data)
            except Exception as e:
                logging.debug(f"Log handler error: {e}")

    def emit_metric(self, name: str, value: float) -> None:
        """Emit metric to all registered handlers."""
        for handler in self._metric_handlers:
            try:
                handler(name, value)
            except Exception as e:
                logging.debug(f"Metric handler error: {e}")

    def emit_alert(self, record: ProblemRecord) -> None:
        """Emit alert to all registered handlers."""
        for handler in self._alert_handlers:
            try:
                handler(record)
            except Exception as e:
                logging.debug(f"Alert handler error: {e}")


# =============================================================================
# MAIN PROBLEM ANALYZER CLASS
# =============================================================================

class ProblemAnalyzer:
    """
    Intelligent Problem Analysis System.

    A comprehensive multi-layered system for deep analysis of network problems,
    orchestrating all analysis components for complete problem lifecycle management.

    Architecture Layers:
        1. Data Collection & Preprocessing
        2. Deep Analysis Engine (anomalies, correlations, patterns)
        3. Causal Analysis & Root Cause Detection
        4. Classification & Prioritization
        5. Learning & Experience Accumulation
        6. Solution Generation & Recommendations
        7. Predictive Analytics
        8. Reporting & Visualization
    """

    def __init__(self, stats_repo: StatsRepository | None = None) -> None:
        """Initialize the intelligent problem analyzer."""
        self._stats_repo = stats_repo

        # Configuration
        self.config = AnalysisConfig()

        # Core components (layers)
        self.experience_store = ExperienceStore(max_history=self.config.history_size)
        self.deep_analyzer = DeepAnalysisEngine(self.config)
        self.causal_analyzer = CausalAnalysisEngine(self.config, self.experience_store)
        self.classifier = ClassificationEngine(self.config, self.experience_store)
        self.solution_generator = SolutionGenerator(self.config, self.experience_store)
        self.predictive_engine = PredictiveEngine(self.config, self.experience_store)
        self.report_generator = ReportGenerator(
            self.config, self.experience_store, self.deep_analyzer, self.predictive_engine
        )
        self.external_integration = ExternalIntegration()

        # Problem tracking
        self.problem_history: deque[ProblemRecord] = deque(maxlen=self.config.history_size)
        self._current_problem: Optional[ProblemRecord] = None
        self._last_analysis_time: Optional[datetime] = None
        self._lock = threading.RLock()

        # Legacy compatibility
        self._legacy_history: deque[Dict[str, Any]] = deque(maxlen=PROBLEM_HISTORY_SIZE)

        logging.info("Intelligent Problem Analyzer initialized")

    # =========================================================================
    # Main Analysis Interface
    # =========================================================================

    def analyze_current_problem(self) -> str:
        """
        Analyze current network state and identify problem type.

        This is the main entry point for problem analysis, orchestrating
        all analysis layers to provide comprehensive problem assessment.

        Returns:
            Localized problem type string
        """
        if self._stats_repo is None:
            return t("problem_none")

        snapshot = self._stats_repo.get_snapshot()
        snapshot_dict = self._convert_snapshot(snapshot)

        # Layer 1: Ingest metrics
        self.deep_analyzer.ingest_metrics(snapshot_dict)

        # Update trend data for predictions
        self._update_trend_data(snapshot_dict)

        # Layer 2: Detect anomalies
        anomalies = self.deep_analyzer.detect_anomalies(snapshot_dict)

        # Layer 2: Analyze correlations
        correlations = self.deep_analyzer.analyze_correlations()

        # Determine if there's a problem
        if not self._has_problem(snapshot_dict, anomalies):
            self._record_no_problem()
            return t("problem_none")

        # Layer 3: Analyze causes
        preliminary_type = self._determine_preliminary_type(snapshot_dict, anomalies)
        causal_factors = self.causal_analyzer.analyze_causes(
            preliminary_type, snapshot_dict, anomalies, correlations
        )

        # Layer 4: Classify problem
        classification = self.classifier.classify_problem(
            snapshot_dict, anomalies, causal_factors
        )

        # Layer 5: Record experience
        record = self._create_problem_record(
            classification, anomalies, causal_factors, snapshot_dict
        )

        # Layer 6: Generate solutions
        solutions = self.solution_generator.generate_solutions(
            classification, causal_factors
        )
        record.solutions = solutions

        # Store record
        with self._lock:
            self._resolve_current_problem_locked()
            self.problem_history.append(record)
            self._current_problem = record
            # Only record experience if learning is enabled
            if self.config.learning_enabled:
                self.experience_store.record_experience(record)

        # Layer 8: External integration
        self.external_integration.emit_alert(record)

        # Legacy compatibility
        self._record_legacy_problem(classification.problem_type, snapshot_dict)

        # Update stats repository
        self._update_stats_repo(classification)

        return self._problem_type_to_string(classification.problem_type)

    def _convert_snapshot(self, snapshot: StatsSnapshot) -> Dict[str, Any]:
        """Convert StatsSnapshot to dictionary."""
        return dict(snapshot)

    def _get_latency_value(self, snapshot: Dict[str, Any]) -> Optional[float]:
        """Extract numeric latency from snapshot if available."""
        latency = snapshot.get("last_latency_ms")
        if latency and latency != t("na"):
            try:
                return float(latency)
            except (ValueError, TypeError):
                return None
        return None

    def _get_packet_loss_percentage(self, snapshot: Dict[str, Any]) -> float:
        """Calculate packet loss percentage from snapshot data."""
        recent_results = snapshot.get("recent_results", [])
        if recent_results:
            return (recent_results.count(False) / len(recent_results)) * 100

        total = snapshot.get("total", 1)
        failure = snapshot.get("failure", 0)
        return (failure / total) * 100 if total > 0 else 0.0

    def _has_problem(self, snapshot: Dict[str, Any], anomalies: List[MetricAnomaly]) -> bool:
        """Check if there's an actual problem."""
        # Check connection lost
        if snapshot.get("threshold_states", {}).get("connection_lost", False):
            return True

        # Check custom analysis rules
        if self.config.get_matching_rules(snapshot):
            return True

        # Check consecutive losses
        if self.config.is_threshold_breached(
            "consecutive_losses",
            float(snapshot.get("consecutive_losses", 0)),
            level="critical",
        ):
            return True

        # Check DNS failure
        if snapshot.get("dns_status") == t("failed"):
            return True

        # Check MTU issues
        mtu_status = snapshot.get("mtu_status", "")
        if mtu_status in [t("mtu_low"), t("mtu_fragmented")]:
            return True

        # Check for significant anomalies
        if any(a.deviation_sigma > 3.0 for a in anomalies):
            return True

        # Check packet loss
        if self.config.is_threshold_breached(
            "packet_loss",
            self._get_packet_loss_percentage(snapshot),
            level="critical",
        ):
            return True

        # Check latency
        latency = self._get_latency_value(snapshot)
        if latency is not None and self.config.is_threshold_breached(
            "latency",
            latency,
            level="critical",
        ):
            return True

        # Check jitter
        jitter = snapshot.get("jitter", 0)
        if isinstance(jitter, (int, float)) and self.config.is_threshold_breached(
            "jitter",
            float(jitter),
            level="critical",
        ):
            return True

        return False

    def _anomaly_to_problem_type(self, anomaly: MetricAnomaly) -> ProblemType:
        """Map an anomaly to the closest preliminary problem type."""
        mapping = {
            "latency": ProblemType.HIGH_LATENCY,
            "jitter": ProblemType.HIGH_JITTER,
            "packet_loss": ProblemType.PACKET_LOSS,
            "consecutive_losses": ProblemType.ISP_OUTAGE,
        }
        return mapping.get(anomaly.metric_name, ProblemType.UNKNOWN)

    def _determine_preliminary_type(
        self,
        snapshot: Dict[str, Any],
        anomalies: List[MetricAnomaly],
    ) -> ProblemType:
        """Determine preliminary problem type for causal analysis."""
        matched_rules = self.config.get_matching_rules(snapshot)
        if matched_rules:
            return matched_rules[0].problem_type

        if snapshot.get("threshold_states", {}).get("connection_lost", False):
            return ProblemType.ISP_OUTAGE

        if self.config.is_threshold_breached(
            "consecutive_losses",
            float(snapshot.get("consecutive_losses", 0)),
            level="critical",
        ):
            return ProblemType.ISP_OUTAGE

        if snapshot.get("dns_status") == t("failed"):
            return ProblemType.DNS_FAILURE

        mtu_status = snapshot.get("mtu_status", "")
        if mtu_status == t("mtu_low"):
            return ProblemType.MTU_LOW
        if mtu_status == t("mtu_fragmented"):
            return ProblemType.MTU_FRAGMENTED

        if snapshot.get("route_changed", False):
            return ProblemType.ROUTE_CHANGE

        latency = self._get_latency_value(snapshot)
        if latency is not None and self.config.is_threshold_breached(
            "latency",
            latency,
            level="critical",
        ):
            return ProblemType.HIGH_LATENCY

        jitter = snapshot.get("jitter", 0)
        if isinstance(jitter, (int, float)) and self.config.is_threshold_breached(
            "jitter",
            float(jitter),
            level="critical",
        ):
            return ProblemType.HIGH_JITTER

        if self.config.is_threshold_breached(
            "packet_loss",
            self._get_packet_loss_percentage(snapshot),
            level="critical",
        ):
            return ProblemType.PACKET_LOSS

        for anomaly in sorted(anomalies, key=lambda item: item.deviation_sigma, reverse=True):
            problem_type = self._anomaly_to_problem_type(anomaly)
            if problem_type != ProblemType.UNKNOWN:
                return problem_type

        return ProblemType.UNKNOWN

    def _create_problem_record(
        self,
        classification: ProblemClassification,
        anomalies: List[MetricAnomaly],
        causal_factors: List[CausalFactor],
        snapshot: Dict[str, Any],
    ) -> ProblemRecord:
        """Create a problem record."""
        import uuid
        return ProblemRecord(
            record_id=str(uuid.uuid4()),
            classification=classification,
            anomalies=anomalies,
            causal_factors=causal_factors,
            solutions=[],
            snapshot_data=snapshot,
        )

    def _resolve_current_problem_locked(self) -> None:
        """Resolve and clear the current problem while holding the analyzer lock."""
        if self._current_problem is None:
            return

        if not self._current_problem.resolved:
            self._current_problem.resolved = True
            self._current_problem.resolution_time = datetime.now(timezone.utc)
            # Only record experience if learning is enabled
            if self.config.learning_enabled:
                self.experience_store.record_experience(self._current_problem)

        self._current_problem = None

    def _record_no_problem(self) -> None:
        """Record that no problem was detected."""
        with self._lock:
            self._resolve_current_problem_locked()

    def _update_trend_data(self, snapshot: Dict[str, Any]) -> None:
        """Update trend data for predictive analysis."""
        latency = snapshot.get("last_latency_ms")
        if latency and latency != t("na"):
            try:
                self.predictive_engine.update_trend_data("latency", float(latency))
            except (ValueError, TypeError):
                pass

        jitter = snapshot.get("jitter", 0)
        if isinstance(jitter, (int, float)):
            self.predictive_engine.update_trend_data("jitter", float(jitter))

        total = snapshot.get("total", 1)
        failure = snapshot.get("failure", 0)
        loss_pct = (failure / total) * 100 if total > 0 else 0.0
        self.predictive_engine.update_trend_data("packet_loss", loss_pct)

    def _update_stats_repo(self, classification: ProblemClassification) -> None:
        """Update stats repository with analysis results."""
        if self._stats_repo:
            problem_str = self._problem_type_to_string(classification.problem_type)
            prediction = self.predict_problems(problem_str)
            pattern = self.identify_pattern()

            self._stats_repo.update_problem_analysis(problem_str, prediction, pattern)

    def _problem_type_to_string(self, problem_type: ProblemType) -> str:
        """Convert ProblemType to localized string."""
        mapping = {
            ProblemType.ISP_OUTAGE: t("problem_isp"),
            ProblemType.LOCAL_NETWORK: t("problem_local"),
            ProblemType.CONNECTION_LOST: t("problem_connection_lost"),
            ProblemType.DNS_FAILURE: t("problem_dns"),
            ProblemType.DNS_SLOW: t("problem_dns"),
            ProblemType.DNS_TIMEOUT: t("problem_dns_timeout"),
            ProblemType.MTU_LOW: t("problem_mtu"),
            ProblemType.MTU_FRAGMENTED: t("problem_mtu"),
            ProblemType.HIGH_LATENCY: t("problem_high_latency"),
            ProblemType.HIGH_JITTER: t("problem_high_jitter"),
            ProblemType.PACKET_LOSS: t("problem_packet_loss"),
            ProblemType.ROUTE_CHANGE: t("problem_route_change"),
            ProblemType.ROUTE_DEGRADATION: t("problem_route_degradation"),
            ProblemType.HOP_TIMEOUT: t("problem_hop_timeout"),
            ProblemType.INTERMITTENT: t("problem_intermittent"),
            ProblemType.CASCADING: t("problem_cascading"),
            ProblemType.UNKNOWN: t("problem_unknown"),
        }
        return mapping.get(problem_type, t("problem_unknown"))

    # =========================================================================
    # Predictive Analysis
    # =========================================================================

    def predict_problems(self, current_problem_type: str | None = None) -> str:
        """
        Predict likelihood of problems based on analysis.

        Args:
            current_problem_type: Current problem type if any

        Returns:
            Localized prediction string
        """
        # Return stable if predictions are disabled
        if not self.config.prediction_enabled:
            return t("prediction_stable")

        if current_problem_type and current_problem_type != t("problem_none"):
            return t("prediction_risk")

        if self._stats_repo is None:
            return t("prediction_stable")

        snapshot = self._stats_repo.get_snapshot()
        snapshot_dict = self._convert_snapshot(snapshot)

        # Get anomalies
        anomalies = self.deep_analyzer.detect_anomalies(snapshot_dict)

        # Get predictions without storing (read-only query)
        predictions = self.predictive_engine.predict_problems(
            snapshot_dict, anomalies, store_predictions=False
        )

        if not predictions:
            return t("prediction_stable")

        # Check for high probability predictions
        high_prob = [p for p in predictions if p.probability > 0.7]
        if high_prob:
            return t("prediction_risk")

        # Check for multiple moderate predictions
        moderate = [p for p in predictions if p.probability > 0.5]
        if len(moderate) >= 2:
            return t("prediction_risk")

        return t("prediction_stable")

    def get_predictions(self) -> List[PredictionResult]:
        """Get current predictions (read-only, does not modify prediction history)."""
        # Return empty list if predictions are disabled
        if not self.config.prediction_enabled:
            return []

        if self._stats_repo is None:
            return []

        snapshot = self._stats_repo.get_snapshot()
        snapshot_dict = self._convert_snapshot(snapshot)
        anomalies = self.deep_analyzer.detect_anomalies(snapshot_dict)

        # Get predictions without storing (read-only query)
        return self.predictive_engine.predict_problems(
            snapshot_dict, anomalies, store_predictions=False
        )

    # =========================================================================
    # Pattern Analysis
    # =========================================================================

    def identify_pattern(self) -> str:
        """
        Identify recurring problem patterns.

        Returns:
            Pattern description string
        """
        with self._lock:
            if len(self.problem_history) < 10:
                return "..."

            # Count problem types
            type_counts: Dict[ProblemType, int] = {}
            for record in self.problem_history:
                pt = record.classification.problem_type
                type_counts[pt] = type_counts.get(pt, 0) + 1

            if not type_counts:
                return "..."

            # Find dominant type
            dominant = max(type_counts, key=lambda k: type_counts[k])
            dominant_count = type_counts[dominant]

            if dominant_count >= len(self.problem_history) * 0.5:
                return self._problem_type_to_string(dominant)

            return "..."

    # =========================================================================
    # Legacy Compatibility
    # =========================================================================

    def _record_legacy_problem(self, problem_type: ProblemType, snap: Dict[str, Any]) -> None:
        """Record problem in legacy format for backward compatibility."""
        now = datetime.now(timezone.utc)
        last_record = self._legacy_history[-1] if self._legacy_history else None

        if last_record:
            last_ts = last_record.get("timestamp")
            last_ts = ensure_utc(last_ts)
            if last_ts is not None:
                delta = (now - last_ts).total_seconds()
                if delta < PROBLEM_LOG_SUPPRESSION_SECONDS:
                    return

        type_str = problem_type.name.lower()
        if type_str in ["isp_outage", "connection_lost"]:
            type_str = "isp"
        elif type_str in ["dns_failure", "dns_slow"]:
            type_str = "dns"
        elif type_str in ["mtu_low", "mtu_fragmented"]:
            type_str = "mtu"
        elif type_str in ["high_latency", "high_jitter", "packet_loss"]:
            type_str = "isp"
        else:
            type_str = "unknown"

        latency = snap.get("last_latency_ms", t("na"))
        total = snap.get("total", 1)
        failure = snap.get("failure", 0)

        problem_record = {
            "type": type_str,
            "timestamp": now,
            "latency": latency,
            "packet_loss": (failure / max(total, 1)) * 100,
            "jitter": snap.get("jitter", 0),
        }
        self._legacy_history.append(problem_record)
        logging.info(f"Problem recorded: {type_str}")

    def get_problem_summary(self) -> Dict[str, Any]:
        """Get summary of problem history (legacy compatible)."""
        with self._lock:
            if not self._legacy_history:
                return {"total": 0, "by_type": {}}

            by_type: Dict[str, int] = {}
            for p in self._legacy_history:
                pt = p.get("type", "unknown")
                by_type[pt] = by_type.get(pt, 0) + 1

            return {
                "total": len(self._legacy_history),
                "by_type": by_type,
            }

    # =========================================================================
    # Reporting
    # =========================================================================

    def generate_report(
        self,
        hours: int = 24,
        include_predictions: bool = True,
    ) -> AnalysisReport:
        """
        Generate comprehensive analysis report.

        Args:
            hours: Time range in hours
            include_predictions: Whether to include predictions

        Returns:
            AnalysisReport object
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        return self.report_generator.generate_report(
            (start_time, end_time),
            include_predictions=include_predictions,
        )

    def get_detailed_analysis(self) -> Dict[str, Any]:
        """Get detailed analysis of current state."""
        if self._stats_repo is None:
            return {"error": "No stats repository available"}

        snapshot = self._stats_repo.get_snapshot()
        snapshot_dict = self._convert_snapshot(snapshot)

        # Get all analysis data
        anomalies = self.deep_analyzer.detect_anomalies(snapshot_dict)
        correlations = self.deep_analyzer.analyze_correlations()
        patterns = self.deep_analyzer.detect_patterns()

        # Get predictions
        predictions = self.get_predictions()

        # Get statistics
        stats = self.experience_store.get_statistics()

        with self._lock:
            current_problem = (
                self._current_problem.to_dict()
                if self._current_problem and not self._current_problem.resolved
                else None
            )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "anomalies": [a.to_dict() for a in anomalies],
            "correlations": [c.to_dict() for c in correlations],
            "patterns": patterns,
            "predictions": [p.to_dict() for p in predictions],
            "experience_stats": stats,
            "current_problem": current_problem,
        }

    # =========================================================================
    # Configuration
    # =========================================================================

    def configure_threshold(self, metric_name: str, config: ThresholdConfig) -> None:
        """Configure threshold for a metric."""
        normalized_config = copy.deepcopy(config)
        normalized_config.metric_name = metric_name
        self.config.add_threshold(normalized_config)

    def configure_rule(self, rule: AnalysisRule) -> None:
        """Add or update an analysis rule."""
        self.config.add_rule(rule)

    def set_learning_enabled(self, enabled: bool) -> None:
        """Enable or disable learning."""
        self.config.learning_enabled = enabled

    def set_prediction_enabled(self, enabled: bool) -> None:
        """Enable or disable predictions."""
        self.config.prediction_enabled = enabled

    # =========================================================================
    # External Integration
    # =========================================================================

    def register_log_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Register external log handler."""
        self.external_integration.register_log_handler(handler)

    def register_metric_handler(self, handler: Callable[[str, float], None]) -> None:
        """Register external metric handler."""
        self.external_integration.register_metric_handler(handler)

    def register_alert_handler(self, handler: Callable[[ProblemRecord], None]) -> None:
        """Register external alert handler."""
        self.external_integration.register_alert_handler(handler)

    # =========================================================================
    # Solution Feedback
    # =========================================================================

    def record_solution_feedback(
        self,
        record_id: str,
        solution_id: str,
        effectiveness: float,
        resolved: bool,
    ) -> None:
        """
        Record feedback on solution effectiveness.

        Args:
            record_id: Problem record ID
            solution_id: Solution that was applied
            effectiveness: Effectiveness rating (0.0 to 1.0)
            resolved: Whether problem was resolved
        """
        with self._lock:
            for record in self.problem_history:
                if record.record_id == record_id:
                    record.resolved = resolved
                    record.resolution_time = datetime.now(timezone.utc)
                    record.resolution_method = solution_id
                    record.effectiveness_feedback = effectiveness
                    self.experience_store.record_experience(record)
                    if resolved and self._current_problem and self._current_problem.record_id == record_id:
                        self._current_problem = None
                    logging.info(f"Solution feedback recorded: {solution_id} = {effectiveness}")
                    break

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall analyzer statistics."""
        with self._lock:
            return {
                "experience": self.experience_store.get_statistics(),
                "problems_analyzed": len(self.problem_history),
                "predictions_made": len(self.predictive_engine._prediction_history),
                "config": self.config.to_dict(),
            }


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "ProblemAnalyzer",
    "ProblemType",
    "ProblemSeverity",
    "ProblemPriority",
    "ProblemClassification",
    "ProblemRecord",
    "SolutionRecommendation",
    "PredictionResult",
    "AnalysisReport",
    "MetricAnomaly",
    "CorrelationResult",
    "CausalFactor",
    "AnalysisConfig",
    "ThresholdConfig",
    "AnalysisRule",
]
