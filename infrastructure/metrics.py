from __future__ import annotations

"""Prometheus metrics initialization and management."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prometheus_client import Counter, Gauge, Histogram

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    
    METRICS_AVAILABLE = True
    
    # Ping metrics
    PING_TOTAL = Counter("pinger_pings_total", "Total pings")
    PING_SUCCESS = Counter("pinger_pings_success_total", "Successful pings")
    PING_FAILURE = Counter("pinger_pings_failure_total", "Failed pings")
    PING_LATENCY_MS = Histogram("pinger_ping_latency_ms", "Ping latency ms")
    
    # Packet loss
    PACKET_LOSS_GAUGE = Gauge("pinger_packet_loss_percent", "Recent packet loss percent")
    
    # MTU metrics
    MTU_PROBLEMS_TOTAL = Counter("pinger_mtu_problems_total", "Total MTU problems detected")
    MTU_STATUS_GAUGE = Gauge("pinger_mtu_status", "MTU status (0=ok,1=low,2=fragmented)")
    
    # Route metrics
    ROUTE_CHANGES_TOTAL = Counter("pinger_route_changes_total", "Total significant route changes")
    ROUTE_CHANGED_GAUGE = Gauge("pinger_route_changed", "Is route currently changed (0/1)")
    
except ImportError:
    METRICS_AVAILABLE = False
    # Create dummy classes for when prometheus is not available
    class _DummyCounter:
        def inc(self, *args, **kwargs): pass
    class _DummyGauge:
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
    class _DummyHistogram:
        def observe(self, *args, **kwargs): pass
    
    PING_TOTAL = _DummyCounter()
    PING_SUCCESS = _DummyCounter()
    PING_FAILURE = _DummyCounter()
    PING_LATENCY_MS = _DummyHistogram()
    PACKET_LOSS_GAUGE = _DummyGauge()
    MTU_PROBLEMS_TOTAL = _DummyCounter()
    MTU_STATUS_GAUGE = _DummyGauge()
    ROUTE_CHANGES_TOTAL = _DummyCounter()
    ROUTE_CHANGED_GAUGE = _DummyGauge()
    
    def start_http_server(*args, **kwargs):  # type: ignore
        pass


def start_metrics_server(port: int = 8000) -> None:
    """Start Prometheus metrics HTTP server."""
    if not METRICS_AVAILABLE:
        logging.warning("Prometheus metrics not available, metrics server not started")
        return
    
    try:
        start_http_server(port)
        logging.info(f"Prometheus metrics server started on port {port}")
    except Exception as exc:
        logging.error(f"Failed to start metrics server: {exc}")
