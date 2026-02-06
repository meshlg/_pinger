from __future__ import annotations

"""Infrastructure layer for metrics and health endpoints."""

from .metrics import (
    METRICS_AVAILABLE,
    PING_TOTAL,
    PING_SUCCESS,
    PING_FAILURE,
    PING_LATENCY_MS,
    PACKET_LOSS_GAUGE,
    MTU_PROBLEMS_TOTAL,
    MTU_STATUS_GAUGE,
    ROUTE_CHANGES_TOTAL,
    ROUTE_CHANGED_GAUGE,
    start_metrics_server,
)

from .health import HealthServer, start_health_server

__all__ = [
    # Metrics
    "METRICS_AVAILABLE",
    "PING_TOTAL",
    "PING_SUCCESS",
    "PING_FAILURE",
    "PING_LATENCY_MS",
    "PACKET_LOSS_GAUGE",
    "MTU_PROBLEMS_TOTAL",
    "MTU_STATUS_GAUGE",
    "ROUTE_CHANGES_TOTAL",
    "ROUTE_CHANGED_GAUGE",
    "start_metrics_server",
    # Health
    "HealthServer",
    "start_health_server",
]
