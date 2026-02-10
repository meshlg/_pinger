"""
Type definitions and factory functions.

Contains TypedDict classes for statistics and factory functions to create instances.
"""

from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, TypedDict

from .settings import LATENCY_WINDOW, WINDOW_SIZE
from .i18n import t


# ─────────────────────────────────────────────────────────────────────────────
# TypedDict Classes
# ─────────────────────────────────────────────────────────────────────────────

class ThresholdStates(TypedDict):
    """Threshold alert states."""
    high_packet_loss: bool
    high_avg_latency: bool
    connection_lost: bool
    high_jitter: bool


class StatsDict(TypedDict):
    """Main statistics dictionary."""
    total: int
    success: int
    failure: int
    last_status: str
    last_latency_ms: str
    min_latency: float
    max_latency: float
    total_latency_sum: float
    latencies: Deque[float]
    consecutive_losses: int
    max_consecutive_losses: int
    public_ip: str
    country: str
    country_code: str | None
    start_time: datetime | None
    last_problem_time: datetime | None
    last_alert_time: datetime | None
    previous_ip: str | None
    ip_change_time: datetime | None
    active_alerts: list[Dict[str, Any]]
    threshold_states: ThresholdStates
    dns_resolve_time: float | None
    dns_status: str
    dns_results: Dict[str, Any]
    dns_benchmark: Dict[str, Any]
    last_traceroute_time: datetime | None
    traceroute_running: bool
    ping_missing_warned: bool
    jitter: float
    local_mtu: int | None
    path_mtu: int | None
    mtu_status: str
    mtu_consecutive_issues: int
    mtu_consecutive_ok: int
    mtu_last_status_change: datetime | None
    last_ttl: int | None
    ttl_hops: int | None
    ttl_history: Deque[int]
    current_problem_type: str
    problem_prediction: str
    problem_pattern: str
    problem_history: list[Dict[str, Any]]
    route_hops: list[Dict[str, Any]]
    route_problematic_hop: int | None
    route_changed: bool
    route_consecutive_changes: int
    route_consecutive_ok: int
    route_last_change_time: datetime | None
    route_last_diff_count: int
    route_history: list[Dict[str, Any]]


# ─────────────────────────────────────────────────────────────────────────────
# Factory Functions
# ─────────────────────────────────────────────────────────────────────────────

def create_stats() -> StatsDict:
    """Create a new statistics dictionary with default values."""
    return {
        "total": 0,
        "success": 0,
        "failure": 0,
        "last_status": t("na"),
        "last_latency_ms": t("na"),
        "min_latency": float("inf"),
        "max_latency": 0.0,
        "total_latency_sum": 0.0,
        "latencies": deque(maxlen=LATENCY_WINDOW),
        "jitter_history": deque(maxlen=LATENCY_WINDOW),
        "consecutive_losses": 0,
        "max_consecutive_losses": 0,
        "public_ip": "...",
        "country": "...",
        "country_code": None,
        "start_time": None,
        "last_problem_time": None,
        "last_alert_time": None,
        "previous_ip": None,
        "ip_change_time": None,
        "active_alerts": [],
        "threshold_states": {
            "high_packet_loss": False,
            "high_avg_latency": False,
            "connection_lost": False,
            "high_jitter": False,
        },
        "dns_resolve_time": None,
        "dns_status": "...",
        "dns_results": {},
        "dns_benchmark": {},
        "last_traceroute_time": None,
        "traceroute_running": False,
        "ping_missing_warned": False,
        "jitter": 0.0,
        "local_mtu": None,
        "path_mtu": None,
        "mtu_status": "...",
        "mtu_consecutive_issues": 0,
        "mtu_consecutive_ok": 0,
        "mtu_last_status_change": None,
        "last_ttl": None,
        "ttl_hops": None,
        "ttl_history": deque(maxlen=100),
        "current_problem_type": t("problem_none"),
        "problem_prediction": t("prediction_stable"),
        "problem_pattern": "...",
        "problem_history": [],
        "route_hops": [],
        "route_problematic_hop": None,
        "route_changed": False,
        "route_consecutive_changes": 0,
        "route_consecutive_ok": 0,
        "route_last_change_time": None,
        "route_last_diff_count": 0,
        "route_history": [],
    }


def create_recent_results() -> Deque[bool]:
    """Create a deque for storing recent ping results."""
    return deque(maxlen=WINDOW_SIZE)
