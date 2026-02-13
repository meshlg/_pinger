"""
Adaptive threshold system.

Provides dynamic threshold calculation based on historical data,
statistical analysis, and anomaly detection to reduce false positives.
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from stats_repository import StatsRepository


@dataclass
class ThresholdConfig:
    """Configuration for a single threshold."""
    
    metric_name: str
    default_value: float
    min_value: float
    max_value: float
    sigma_multiplier: float = 2.0  # Standard deviations for anomaly
    percentile: float = 95.0  # Percentile for threshold
    use_percentile: bool = False  # Use percentile vs sigma


@dataclass
class BaselineData:
    """Baseline statistics for a metric."""
    
    mean: float
    std_dev: float
    median: float
    p95: float
    p99: float
    min_value: float
    max_value: float
    sample_count: int
    last_updated: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mean": self.mean,
            "std_dev": self.std_dev,
            "median": self.median,
            "p95": self.p95,
            "p99": self.p99,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "sample_count": self.sample_count,
            "last_updated": self.last_updated.isoformat(),
        }


class AdaptiveThresholds:
    """
    Calculate and manage adaptive thresholds based on historical data.
    
    Uses statistical analysis (mean, std dev, percentiles) to determine
    dynamic thresholds that adapt to changing baseline performance.
    """
    
    def __init__(
        self,
        stats_repo: StatsRepository,
        baseline_window_hours: int = 24,
        update_interval_minutes: int = 60,
        anomaly_sigma: float = 2.0,
    ):
        """
        Initialize adaptive thresholds.
        
        Args:
            stats_repo: Repository for accessing historical data
            baseline_window_hours: Hours of data for baseline calculation
            update_interval_minutes: How often to recalculate baselines
            anomaly_sigma: Standard deviations for anomaly detection
        """
        self.stats_repo = stats_repo
        self.baseline_window_hours = baseline_window_hours
        self.update_interval_minutes = update_interval_minutes
        self.anomaly_sigma = anomaly_sigma
        
        # Baseline data cache: metric_name -> BaselineData
        self._baselines: Dict[str, BaselineData] = {}
        
        # Last update time for each metric
        self._last_update: Dict[str, datetime] = {}
        
        # Threshold configurations
        self._configs = self._build_threshold_configs()
        
        # Initialize baselines
        self._initialize_baselines()
    
    def _build_threshold_configs(self) -> Dict[str, ThresholdConfig]:
        """
        Build threshold configurations for monitored metrics.
        
        Returns:
            Dictionary mapping metric name to config
        """
        return {
            "latency": ThresholdConfig(
                metric_name="latency",
                default_value=100.0,
                min_value=20.0,
                max_value=500.0,
                sigma_multiplier=2.0,
                use_percentile=False,
            ),
            "avg_latency": ThresholdConfig(
                metric_name="avg_latency",
                default_value=100.0,
                min_value=20.0,
                max_value=300.0,
                sigma_multiplier=2.0,
                use_percentile=False,
            ),
            "packet_loss": ThresholdConfig(
                metric_name="packet_loss",
                default_value=5.0,
                min_value=1.0,
                max_value=20.0,
                percentile=95.0,
                use_percentile=True,
            ),
            "jitter": ThresholdConfig(
                metric_name="jitter",
                default_value=30.0,
                min_value=10.0,
                max_value=100.0,
                sigma_multiplier=2.0,
                use_percentile=False,
            ),
        }
    
    def _initialize_baselines(self) -> None:
        """Initialize baselines for all configured metrics."""
        for metric_name in self._configs:
            self._update_baseline(metric_name)
    
    def get_threshold(
        self,
        metric: str,
        context: Optional[Dict] = None
    ) -> float:
        """
        Get adaptive threshold for a metric.
        
        Args:
            metric: Metric name (e.g., "latency", "packet_loss")
            context: Additional context (not used currently, for future extension)
            
        Returns:
            Calculated threshold value
        """
        # Update baseline if needed
        if self._should_update_baseline(metric):
            self._update_baseline(metric)
        
        # Get baseline data
        baseline = self._baselines.get(metric)
        config = self._configs.get(metric)
        
        if not baseline or not config:
            # Return default if no baseline
            return config.default_value if config else 100.0
        
        # Calculate threshold
        if config.use_percentile:
            threshold = baseline.p95
        else:
            # Use mean + sigma * std_dev
            threshold = baseline.mean + (config.sigma_multiplier * baseline.std_dev)
        
        # Clamp to min/max
        threshold = max(config.min_value, min(config.max_value, threshold))
        
        return threshold
    
    def is_anomaly(
        self,
        metric: str,
        value: float,
        context: Optional[Dict] = None
    ) -> bool:
        """
        Check if a value is anomalous for the metric.
        
        Args:
            metric: Metric name
            value: Value to check
            context: Additional context
            
        Returns:
            True if value is anomalous
        """
        threshold = self.get_threshold(metric, context)
        return value > threshold
    
    def _should_update_baseline(self, metric: str) -> bool:
        """
        Check if baseline should be updated.
        
        Args:
            metric: Metric name
            
        Returns:
            True if update is needed
        """
        last_update = self._last_update.get(metric)
        
        if not last_update:
            return True
        
        age_minutes = (datetime.now(timezone.utc) - last_update).total_seconds() / 60
        return age_minutes >= self.update_interval_minutes
    
    def _update_baseline(self, metric: str) -> None:
        """
        Update baseline for a metric from historical data.
        
        Args:
            metric: Metric name to update
        """
        # Get historical data from stats repository
        data = self._get_historical_data(metric)
        
        if not data or len(data) < 10:
            # Not enough data, keep defaults
            return
        
        # Calculate statistics
        baseline = self._calculate_baseline(data)
        
        # Store baseline
        self._baselines[metric] = baseline
        self._last_update[metric] = datetime.now(timezone.utc)
    
    def _get_historical_data(self, metric: str) -> List[float]:
        """
        Get historical data for a metric from stats repository.
        
        Args:
            metric: Metric name
            
        Returns:
            List of historical values
        """
        # Access stats repository to get historical data
        # This depends on the metric type
        
        if metric == "latency":
            # Get recent latency values from stats dict
            with self.stats_repo.lock:
                stats = self.stats_repo.get_stats()
                latencies = stats.get("latencies", [])
            return list(latencies) if latencies else []
        
        elif metric == "avg_latency":
            # Calculate from total/success
            with self.stats_repo.lock:
                stats = self.stats_repo.get_stats()
                success = stats.get("success", 0)
                total_latency = stats.get("total_latency_sum", 0.0)
            
            if success > 0:
                avg = total_latency / success
                return [avg]  # Single value for now
            return []
        
        elif metric == "packet_loss":
            # Calculate from recent results using proper accessor
            recent_results = self.stats_repo.get_recent_results()
            with self.stats_repo.lock:
                results = list(recent_results)
            
            if not results:
                return []
            
            # Calculate rolling packet loss %
            window_size = min(30, len(results))
            if len(results) < window_size:
                return []
                
            loss_values = []
            for i in range(len(results) - window_size + 1):
                window = results[i:i + window_size]
                loss_pct = (window.count(False) / len(window)) * 100
                loss_values.append(loss_pct)
            
            return loss_values if loss_values else [0.0]
        
        elif metric == "jitter":
            with self.stats_repo.lock:
                stats = self.stats_repo.get_stats()
                jitter = stats.get("jitter", 0.0)
            return [jitter] if jitter > 0 else []
        
        return []
    
    def _calculate_baseline(self, data: List[float]) -> BaselineData:
        """
        Calculate baseline statistics from data.
        
        Args:
            data: List of values
            
        Returns:
            BaselineData with statistics
        """
        if not data:
            raise ValueError("Cannot calculate baseline from empty data")
        
        # Basic statistics
        mean = statistics.mean(data)
        std_dev = statistics.stdev(data) if len(data) > 1 else 0.0
        median = statistics.median(data)
        
        # Percentiles
        sorted_data = sorted(data)
        p95_idx = int(len(sorted_data) * 0.95)
        p99_idx = int(len(sorted_data) * 0.99)
        
        p95 = sorted_data[p95_idx] if p95_idx < len(sorted_data) else sorted_data[-1]
        p99 = sorted_data[p99_idx] if p99_idx < len(sorted_data) else sorted_data[-1]
        
        return BaselineData(
            mean=mean,
            std_dev=std_dev,
            median=median,
            p95=p95,
            p99=p99,
            min_value=min(data),
            max_value=max(data),
            sample_count=len(data),
            last_updated=datetime.now(timezone.utc),
        )
    
    def update_baselines(self) -> None:
        """Manually trigger update of all baselines."""
        for metric_name in self._configs:
            self._update_baseline(metric_name)
    
    def get_baseline(self, metric: str) -> Optional[BaselineData]:
        """Get baseline data for a metric."""
        return self._baselines.get(metric)
    
    def get_all_baselines(self) -> Dict[str, BaselineData]:
        """Get all baseline data."""
        return self._baselines.copy()
    
    def clear(self) -> None:
        """Clear all baselines."""
        self._baselines.clear()
        self._last_update.clear()
