from __future__ import annotations

"""Prometheus metrics initialization and management."""

import base64
import json
import logging
import os
import secrets
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry

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
    
    # Smart Alert System metrics
    ALERTS_TOTAL = Counter("pinger_alerts_total", "Total alerts generated")
    ALERTS_DEDUPLICATED_TOTAL = Counter("pinger_alerts_deduplicated_total", "Alerts deduplicated")
    ALERTS_SUPPRESSED_TOTAL = Counter("pinger_alerts_suppressed_total", "Alerts suppressed")
    ALERTS_RATE_LIMITED_TOTAL = Counter("pinger_alerts_rate_limited_total", "Alerts rate limited")
    ALERT_GROUPS_ACTIVE = Gauge("pinger_alert_groups_active", "Active alert groups")
    ALERT_PRIORITY_GAUGE = Gauge("pinger_alert_priority", "Alerts by priority", ["priority"])
    
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
    ALERTS_TOTAL = _DummyCounter()
    ALERTS_DEDUPLICATED_TOTAL = _DummyCounter()
    ALERTS_SUPPRESSED_TOTAL = _DummyCounter()
    ALERTS_RATE_LIMITED_TOTAL = _DummyCounter()
    ALERT_GROUPS_ACTIVE = _DummyGauge()
    ALERT_PRIORITY_GAUGE = _DummyGauge()
    
    def start_http_server(*args, **kwargs):  # type: ignore
        pass


def _get_metrics_auth_credentials() -> tuple[str, str] | None:
    """Get metrics auth credentials from environment variables.
    
    Returns:
        Tuple of (username, password) if METRICS_AUTH_USER and METRICS_AUTH_PASS are set,
        None otherwise.
    """
    user = os.environ.get("METRICS_AUTH_USER")
    password = os.environ.get("METRICS_AUTH_PASS")
    if user and password:
        return (user, password)
    return None


def _check_basic_auth(auth_header: str | None, credentials: tuple[str, str]) -> bool:
    """Check if request has valid basic auth header.
    
    Args:
        auth_header: The Authorization header value
        credentials: Tuple of (username, password)
        
    Returns:
        True if valid credentials provided, False otherwise.
    """
    if not auth_header:
        return False
    
    try:
        scheme, encoded = auth_header.split(" ", 1)
        if scheme.lower() != "basic":
            return False
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
        return (
            secrets.compare_digest(username, credentials[0])
            and secrets.compare_digest(password, credentials[1])
        )
    except Exception:
        return False


class AuthenticatedMetricsHandler(BaseHTTPRequestHandler):
    """Metrics handler with optional basic auth."""
    
    def do_GET(self) -> None:
        """Handle GET requests for metrics."""
        credentials = _get_metrics_auth_credentials()
        
        # Check authentication if credentials are configured
        if credentials is not None:
            auth_header = self.headers.get("Authorization")
            if not _check_basic_auth(auth_header, credentials):
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="Metrics"')
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
                return
        
        # Serve metrics
        if self.path == "/metrics":
            try:
                from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, REGISTRY
                data = generate_latest(REGISTRY)
                self.send_response(200)
                self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as exc:
                logging.error(f"Metrics error: {exc}")
                self.send_error(500, "Internal Server Error")
        else:
            self.send_error(404)
    
    def log_message(self, format: str, *args) -> None:
        """Suppress default HTTP logging."""
        logging.debug(f"Metrics server: {format % args}")


class MetricsServer:
    """Prometheus metrics HTTP server with optional auth."""
    
    def __init__(self, addr: str = "127.0.0.1", port: int = 8000) -> None:
        self.addr = addr
        self.port = port
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._running = False
    
    def _check_security(self) -> bool:
        """Check security configuration and warn/fail if insecure.
        
        Returns:
            True if configuration is acceptable, False if should not start.
        """
        credentials = _get_metrics_auth_credentials()
        is_localhost = self.addr in ("127.0.0.1", "localhost")
        
        # Localhost binding - always allowed
        if is_localhost:
            return True
        
        # Non-localhost binding requires authentication
        if credentials is None:
            allow_no_auth = os.environ.get("METRICS_ALLOW_NO_AUTH", "").lower() in ("1", "true", "yes")
            if allow_no_auth:
                logging.warning(
                    f"METRICS_ADDR={self.addr} without authentication! "
                    f"Set METRICS_AUTH_USER and METRICS_AUTH_PASS (Basic Auth). "
                    f"Server will START but is INSECURE."
                )
                return True
            else:
                logging.error(
                    f"SECURITY ERROR: METRICS_ADDR={self.addr} requires authentication. "
                    f"Set METRICS_AUTH_USER and METRICS_AUTH_PASS (Basic Auth)\n"
                    f"  - Or set METRICS_ALLOW_NO_AUTH=1 to override (NOT recommended)"
                )
                return False
        
        return True
    
    def start(self) -> None:
        """Start metrics server in background thread."""
        if self._running:
            return
        
        # Security check
        if not self._check_security():
            logging.error("Metrics server not started due to security configuration.")
            return
        
        try:
            self.server = HTTPServer((self.addr, self.port), AuthenticatedMetricsHandler)
            self.thread = threading.Thread(target=self._serve, daemon=True)
            self.thread.start()
            self._running = True
            
            auth_status = "with auth" if _get_metrics_auth_credentials() else "no auth"
            if self.addr in ("127.0.0.1", "localhost"):
                logging.info(f"Metrics server started on http://127.0.0.1:{self.port} (localhost-only, {auth_status})")
            else:
                logging.info(f"Metrics server started on http://{self.addr}:{self.port} ({auth_status})")
        except Exception as exc:
            logging.error(f"Failed to start metrics server: {exc}")
    
    def _serve(self) -> None:
        """Server loop."""
        while self._running and self.server:
            try:
                self.server.handle_request()
            except Exception as exc:
                logging.debug(f"Metrics server request error: {exc}")
    
    def stop(self) -> None:
        """Stop metrics server."""
        self._running = False
        if self.server:
            self.server.shutdown()


def start_metrics_server(addr: str = "127.0.0.1", port: int = 8000) -> MetricsServer | None:
    """Start Prometheus metrics HTTP server with optional auth.
    
    Security:
        - Default binds to 127.0.0.1 (localhost only)
        - Set addr="0.0.0.0" for pod network (Kubernetes)
        - Authentication via METRICS_AUTH_USER + METRICS_AUTH_PASS (Basic Auth)
        - Set METRICS_ALLOW_NO_AUTH=1 to bypass auth requirement (not recommended)
    
    Args:
        addr: Network address to bind to (127.0.0.1 for localhost-only)
        port: Port to listen on
    
    Returns:
        MetricsServer instance or None if Prometheus client is not available
    """
    if not METRICS_AVAILABLE:
        logging.warning("Prometheus metrics not available, metrics server not started")
        return None
    
    try:
        server = MetricsServer(addr=addr, port=port)
        server.start()
        return server
    except Exception as exc:
        logging.error(f"Failed to start metrics server: {exc}")
        return None
