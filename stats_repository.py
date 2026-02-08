"""Stats repository for clean data access."""
from __future__ import annotations

import threading
import statistics
from collections import deque
from datetime import datetime
from typing import Any, TypedDict, Optional

from config import (
    create_stats,
    t,
    ThresholdStates,
    WINDOW_SIZE,
    LATENCY_WINDOW,
)


class StatsSnapshot(TypedDict):
    """Immutable snapshot of monitoring stats for UI."""
    total: int
    success: int
    failure: int
    last_status: str
    last_latency_ms: str
    min_latency: float
    max_latency: float
    total_latency_sum: float
    latencies: list[float]
    jitter_history: list[float]
    consecutive_losses: int
    max_consecutive_losses: int
    public_ip: str
    country: str
    country_code: str | None
    start_time: datetime | None
    last_problem_time: datetime | None
    previous_ip: str | None
    ip_change_time: datetime | None
    threshold_states: ThresholdStates
    dns_resolve_time: float | None
    dns_status: str
    dns_results: dict[str, Any] | None  # Per-record-type DNS results
    last_traceroute_time: datetime | None
    traceroute_running: bool
    jitter: float
    local_mtu: int | None
    path_mtu: int | None
    mtu_status: str
    mtu_consecutive_issues: int
    mtu_consecutive_ok: int
    mtu_last_status_change: datetime | None
    last_ttl: int | None
    ttl_hops: int | None
    current_problem_type: str
    problem_prediction: str
    problem_pattern: str
    route_hops: list[dict[str, Any]]
    route_problematic_hop: int | None
    route_changed: bool
    route_consecutive_changes: int
    route_consecutive_ok: int
    route_last_change_time: datetime | None
    route_last_diff_count: int
    active_alerts: list[dict[str, Any]]
    recent_results: list[bool]  # copy of recent results for UI
    hop_monitor_hops: list[dict[str, Any]]
    hop_monitor_discovering: bool


class StatsRepository:
    """
    Repository for managing monitoring statistics.
    Provides thread-safe access and immutable snapshots for UI.
    """

    def __init__(self) -> None:
        self._stats: dict[str, Any] = create_stats()
        self._recent_results: deque[bool] = deque(maxlen=WINDOW_SIZE)
        self._stats["latencies"] = deque(maxlen=LATENCY_WINDOW)
        self._stats["jitter_history"] = deque(maxlen=LATENCY_WINDOW)
        self._lock = threading.RLock()

    @property
    def lock(self) -> threading.RLock:
        """Get the stats lock for atomic operations."""
        return self._lock

    def get_stats(self) -> dict[str, Any]:
        """Get direct stats dict (for service updates). Use with lock!"""
        return self._stats

    def get_recent_results(self) -> deque[bool]:
        """Get recent results deque. Use with lock!"""
        return self._recent_results

    def get_snapshot(self) -> StatsSnapshot:
        """Get immutable snapshot for UI."""
        with self._lock:
            return {
                "total": self._stats["total"],
                "success": self._stats["success"],
                "failure": self._stats["failure"],
                "last_status": self._stats["last_status"],
                "last_latency_ms": self._stats["last_latency_ms"],
                "min_latency": self._stats["min_latency"],
                "max_latency": self._stats["max_latency"],
                "total_latency_sum": self._stats["total_latency_sum"],
                "latencies": list(self._stats["latencies"]),
                "jitter_history": list(self._stats.get("jitter_history", [])),
                "consecutive_losses": self._stats["consecutive_losses"],
                "max_consecutive_losses": self._stats["max_consecutive_losses"],
                "public_ip": self._stats["public_ip"],
                "country": self._stats["country"],
                "country_code": self._stats["country_code"],
                "start_time": self._stats["start_time"],
                "last_problem_time": self._stats["last_problem_time"],
                "previous_ip": self._stats["previous_ip"],
                "ip_change_time": self._stats["ip_change_time"],
                "threshold_states": dict(self._stats["threshold_states"]),
                "dns_resolve_time": self._stats["dns_resolve_time"],
                "dns_status": self._stats["dns_status"],
                "dns_results": dict(self._stats.get("dns_results", {})),
                "dns_benchmark": dict(self._stats.get("dns_benchmark", {})),
                "last_traceroute_time": self._stats["last_traceroute_time"],
                "traceroute_running": self._stats["traceroute_running"],
                "jitter": self._stats["jitter"],
                "local_mtu": self._stats["local_mtu"],
                "path_mtu": self._stats["path_mtu"],
                "mtu_status": self._stats.get("mtu_status", t("na")),
                "mtu_consecutive_issues": self._stats.get("mtu_consecutive_issues", 0),
                "mtu_consecutive_ok": self._stats.get("mtu_consecutive_ok", 0),
                "mtu_last_status_change": self._stats.get("mtu_last_status_change"),
                "last_ttl": self._stats["last_ttl"],
                "ttl_hops": self._stats["ttl_hops"],
                "current_problem_type": self._stats["current_problem_type"],
                "problem_prediction": self._stats["problem_prediction"],
                "problem_pattern": self._stats["problem_pattern"],
                "route_hops": list(self._stats.get("route_hops", [])),
                "route_problematic_hop": self._stats.get("route_problematic_hop"),
                "route_changed": self._stats.get("route_changed", False),
                "route_consecutive_changes": self._stats.get("route_consecutive_changes", 0),
                "route_consecutive_ok": self._stats.get("route_consecutive_ok", 0),
                "route_last_change_time": self._stats.get("route_last_change_time"),
                "route_last_diff_count": self._stats.get("route_last_diff_count", 0),
                "active_alerts": list(self._stats.get("active_alerts", [])),
                "recent_results": list(self._recent_results),
                "hop_monitor_hops": list(self._stats.get("hop_monitor_hops", [])),
                "hop_monitor_discovering": self._stats.get("hop_monitor_discovering", False),
            }

    def update_after_ping(
        self,
        ok: bool,
        latency: float | None,
        alert_on_high_latency: bool = False,
        high_latency_threshold: float = 100.0,
        alert_on_packet_loss: bool = False,
    ) -> tuple[bool, bool]:
        """
        Update stats after a ping result.
        Returns (high_latency_flag, loss_flag).
        """
        high_latency_flag = False
        loss_flag = False

        with self._lock:
            self._stats["total"] += 1
            
            if ok:
                self._stats["success"] += 1
                self._stats["consecutive_losses"] = 0
                self._stats["last_status"] = t("status_ok")
                
                if latency is not None:
                    self._stats["last_latency_ms"] = f"{latency:.2f}"
                    self._stats["total_latency_sum"] += latency
                    self._stats["latencies"].append(latency)
                    self._stats["min_latency"] = min(self._stats["min_latency"], latency)
                    self._stats["max_latency"] = max(self._stats["max_latency"], latency)
                    
                    if alert_on_high_latency and latency > high_latency_threshold:
                        high_latency_flag = True
                    
                    # Update jitter incrementally (exponential moving average)
                    if len(self._stats["latencies"]) >= 2:
                        prev = self._stats["latencies"][-2]
                        diff = abs(latency - prev)
                        alpha = 0.1  # smoothing factor
                        old_jitter = self._stats["jitter"]
                        self._stats["jitter"] = old_jitter + alpha * (diff - old_jitter)
                        self._stats["jitter_history"].append(self._stats["jitter"])
                    elif len(self._stats["latencies"]) == 1:
                        self._stats["jitter_history"].append(self._stats["jitter"])
                else:
                    self._stats["last_latency_ms"] = t("na")
            else:
                self._stats["failure"] += 1
                self._stats["consecutive_losses"] += 1
                self._stats["last_status"] = t("status_timeout")
                self._stats["last_latency_ms"] = t("na")
                self._stats["max_consecutive_losses"] = max(
                    self._stats["max_consecutive_losses"],
                    self._stats["consecutive_losses"],
                )
                self._stats["last_problem_time"] = datetime.now()
                
                if alert_on_packet_loss:
                    loss_flag = True
            
            # Add to recent results (thread-safe via lock)
            self._recent_results.append(ok)

        return high_latency_flag, loss_flag

    def set_start_time(self, time: datetime) -> None:
        """Set monitoring start time."""
        with self._lock:
            self._stats["start_time"] = time

    def update_dns(self, resolve_time: float | None, status: str) -> None:
        """Update DNS status (legacy - for backward compatibility)."""
        with self._lock:
            self._stats["dns_resolve_time"] = resolve_time
            self._stats["dns_status"] = status

    def update_dns_detailed(self, dns_results: list[dict]) -> None:
        """Update DNS status with per-record-type details.
        
        Args:
            dns_results: List of DNS query results, each containing:
                - record_type: str (A, AAAA, CNAME, etc.)
                - success: bool
                - response_time_ms: float | None
                - status: str
                - ttl: int | None
                - records: list
                - error: str | None
        """
        with self._lock:
            # Store detailed results by record type
            self._stats["dns_results"] = {
                r["record_type"]: {
                    "success": r["success"],
                    "response_time_ms": r.get("response_time_ms"),
                    "status": r["status"],
                    "ttl": r.get("ttl"),
                    "record_count": len(r.get("records", [])),
                    "error": r.get("error"),
                }
                for r in dns_results
            }
            
            # Calculate overall status
            successful = [r for r in dns_results if r["success"]]
            if not dns_results:
                self._stats["dns_status"] = t("failed")
                self._stats["dns_resolve_time"] = None
            elif not successful:
                self._stats["dns_status"] = t("failed")
                self._stats["dns_resolve_time"] = None
            else:
                # Use average response time across all successful queries
                avg_time = sum(r["response_time_ms"] for r in successful if r["response_time_ms"]) / len(successful)
                self._stats["dns_resolve_time"] = avg_time
                # Status is ok only if all types succeeded
                self._stats["dns_status"] = t("ok") if len(successful) == len(dns_results) else t("slow")

    def update_dns_benchmark(self, benchmark_results: list[dict]) -> None:
        """Update DNS benchmark results (Cached/Uncached/DotCom).
        
        Args:
            benchmark_results: List of benchmark results, each containing:
                - server: str
                - test_type: str ("cached", "uncached", "dotcom")
                - domain: str
                - queries: int
                - min_ms: float | None
                - avg_ms: float | None
                - max_ms: float | None
                - std_dev: float | None
                - reliability: float
                - response_time_ms: float | None
                - success: bool
                - status: str
                - error: str | None
        """
        with self._lock:
            self._stats["dns_benchmark"] = {
                r["test_type"]: {
                    "server": r.get("server", "system"),
                    "domain": r["domain"],
                    "queries": r.get("queries", 0),
                    "min_ms": r.get("min_ms"),
                    "avg_ms": r.get("avg_ms"),
                    "max_ms": r.get("max_ms"),
                    "std_dev": r.get("std_dev"),
                    "reliability": r.get("reliability", 0.0),
                    "response_time_ms": r.get("response_time_ms"),
                    "success": r["success"],
                    "status": r["status"],
                    "error": r.get("error"),
                }
                for r in benchmark_results
            }

    def update_mtu(self, local_mtu: int | None, path_mtu: int | None, status: str) -> None:
        """Update MTU info."""
        with self._lock:
            self._stats["local_mtu"] = local_mtu
            self._stats["path_mtu"] = path_mtu
            self._stats["mtu_status"] = status

    def update_ttl(self, ttl: int | None, hops: int | None) -> None:
        """Update TTL info."""
        with self._lock:
            self._stats["last_ttl"] = ttl
            self._stats["ttl_hops"] = hops
            if ttl is not None:
                self._stats["ttl_history"].append(ttl)

    def update_public_ip(self, ip: str, country: str, country_code: str | None) -> None:
        """Update public IP info."""
        with self._lock:
            self._stats["public_ip"] = ip
            self._stats["country"] = country
            self._stats["country_code"] = country_code

    def update_ip_change(self, old_ip: str, new_ip: str) -> None:
        """Record IP change."""
        with self._lock:
            self._stats["previous_ip"] = old_ip
            self._stats["ip_change_time"] = datetime.now()

    def update_route(
        self,
        hops: list[dict],
        problematic_hop: int | None,
        route_changed: bool,
        diff_count: int = 0,
    ) -> None:
        """Update route analysis info."""
        with self._lock:
            self._stats["route_hops"] = hops
            self._stats["route_problematic_hop"] = problematic_hop
            self._stats["route_changed"] = route_changed
            self._stats["route_last_diff_count"] = diff_count

    def update_problem_analysis(
        self,
        problem_type: str,
        prediction: str,
        pattern: str,
    ) -> None:
        """Update problem analysis results."""
        with self._lock:
            self._stats["current_problem_type"] = problem_type
            self._stats["problem_prediction"] = prediction
            self._stats["problem_pattern"] = pattern

    def update_threshold_state(self, key: str, value: bool) -> None:
        """Update a threshold state."""
        with self._lock:
            self._stats["threshold_states"][key] = value

    def get_threshold_state(self, key: str) -> bool:
        """Get a threshold state."""
        with self._lock:
            return self._stats["threshold_states"].get(key, False)

    def get_consecutive_losses(self) -> int:
        """Get current consecutive losses count."""
        with self._lock:
            return self._stats["consecutive_losses"]

    def update_mtu_hysteresis(self, is_issue: bool) -> tuple[int, int]:
        """Update MTU hysteresis counters. Returns (consecutive_issues, consecutive_ok)."""
        with self._lock:
            if is_issue:
                self._stats["mtu_consecutive_issues"] = self._stats.get("mtu_consecutive_issues", 0) + 1
                self._stats["mtu_consecutive_ok"] = 0
            else:
                self._stats["mtu_consecutive_ok"] = self._stats.get("mtu_consecutive_ok", 0) + 1
                self._stats["mtu_consecutive_issues"] = 0
            return self._stats["mtu_consecutive_issues"], self._stats["mtu_consecutive_ok"]

    def get_mtu_status(self) -> str:
        """Get current MTU status."""
        with self._lock:
            return self._stats.get("mtu_status", t("mtu_ok"))

    def set_mtu_status_change_time(self) -> None:
        """Record MTU status change time."""
        with self._lock:
            self._stats["mtu_last_status_change"] = datetime.now()

    def update_route_hysteresis(self, is_change: bool) -> tuple[int, int]:
        """Update route change hysteresis counters. Returns (consecutive_changes, consecutive_ok)."""
        with self._lock:
            if is_change:
                self._stats["route_consecutive_changes"] = self._stats.get("route_consecutive_changes", 0) + 1
                self._stats["route_consecutive_ok"] = 0
            else:
                self._stats["route_consecutive_ok"] = self._stats.get("route_consecutive_ok", 0) + 1
                self._stats["route_consecutive_changes"] = 0
            return self._stats["route_consecutive_changes"], self._stats["route_consecutive_ok"]

    def set_route_changed(self, changed: bool) -> None:
        """Set route changed flag with timestamp."""
        with self._lock:
            self._stats["route_changed"] = changed
            self._stats["route_last_change_time"] = datetime.now()

    def is_route_changed(self) -> bool:
        """Get current route changed state."""
        with self._lock:
            return self._stats.get("route_changed", False)

    def set_traceroute_running(self, running: bool) -> None:
        """Set traceroute running state."""
        with self._lock:
            self._stats["traceroute_running"] = running
            if running:
                self._stats["last_traceroute_time"] = datetime.now()

    def is_traceroute_running(self) -> bool:
        """Check if traceroute is currently running."""
        with self._lock:
            return self._stats.get("traceroute_running", False)

    def get_last_traceroute_time(self) -> datetime | None:
        """Get last traceroute time."""
        with self._lock:
            return self._stats.get("last_traceroute_time")

    def update_hop_monitor(self, hops: list[dict], discovering: bool = False) -> None:
        """Update hop monitor data."""
        with self._lock:
            self._stats["hop_monitor_hops"] = hops
            self._stats["hop_monitor_discovering"] = discovering

    def get_memory_usage_mb(self) -> float | None:
        """Get current memory usage in MB. Returns None if monitoring disabled."""
        from config import ENABLE_MEMORY_MONITORING
        if not ENABLE_MEMORY_MONITORING:
            return None
        
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except (ImportError, Exception):
            return None

    def check_memory_limit(self) -> tuple[bool, float | None]:
        """Check if memory usage exceeds limit. Returns (exceeded, current_mb)."""
        from config import MAX_MEMORY_MB
        
        current_mb = self.get_memory_usage_mb()
        if current_mb is None:
            return False, None
        
        exceeded = current_mb > MAX_MEMORY_MB
        return exceeded, current_mb

    def cleanup_old_data(self) -> dict[str, int]:
        """Clean up old data to prevent memory leaks. Returns items removed per collection."""
        from config import (
            MAX_ALERTS_HISTORY,
            MAX_PROBLEM_HISTORY,
            MAX_ROUTE_HISTORY,
            MAX_DNS_BENCHMARK_HISTORY,
        )
        
        cleaned = {}
        
        with self._lock:
            # Clean old alerts
            alerts = self._stats.get("active_alerts", [])
            if len(alerts) > MAX_ALERTS_HISTORY:
                removed = len(alerts) - MAX_ALERTS_HISTORY
                self._stats["active_alerts"] = alerts[-MAX_ALERTS_HISTORY:]
                cleaned["alerts"] = removed
            
            # Clean problem history
            problem_history = self._stats.get("problem_history", [])
            if len(problem_history) > MAX_PROBLEM_HISTORY:
                removed = len(problem_history) - MAX_PROBLEM_HISTORY
                self._stats["problem_history"] = problem_history[-MAX_PROBLEM_HISTORY:]
                cleaned["problems"] = removed
            
            # Clean route history
            route_history = self._stats.get("route_history", [])
            if len(route_history) > MAX_ROUTE_HISTORY:
                removed = len(route_history) - MAX_ROUTE_HISTORY
                self._stats["route_history"] = route_history[-MAX_ROUTE_HISTORY:]
                cleaned["routes"] = removed
        
        return cleaned
