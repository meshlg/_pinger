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
)


# Window sizes for statistics (moved from config.py for encapsulation)
WINDOW_SIZE = 1800  # Recent results window
LATENCY_WINDOW = 600  # Latency history window


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
                    
                    # Update jitter
                    if len(self._stats["latencies"]) >= 2:
                        latencies_list = list(self._stats["latencies"])
                        self._stats["jitter"] = statistics.mean(
                            abs(latencies_list[i] - latencies_list[i - 1])
                            for i in range(1, len(latencies_list))
                        )
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
        """Update DNS status."""
        with self._lock:
            self._stats["dns_resolve_time"] = resolve_time
            self._stats["dns_status"] = status

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

    def update_hop_monitor(self, hops: list[dict], discovering: bool = False) -> None:
        """Update hop monitor data."""
        with self._lock:
            self._stats["hop_monitor_hops"] = hops
            self._stats["hop_monitor_discovering"] = discovering
