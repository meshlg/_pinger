from __future__ import annotations

"""Health check HTTP server for Kubernetes/Docker health probes."""

import json
import logging
import threading
import base64
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stats_repository import StatsRepository


def _get_basic_auth_credentials() -> tuple[str, str] | None:
    """Get basic auth credentials from environment variables.
    
    Returns:
        Tuple of (username, password) if HEALTH_AUTH_USER and HEALTH_AUTH_PASS are set,
        None otherwise.
    """
    user = os.environ.get("HEALTH_AUTH_USER")
    password = os.environ.get("HEALTH_AUTH_PASS")
    if user and password:
        return (user, password)
    return None


def _check_basic_auth(handler: BaseHTTPRequestHandler, credentials: tuple[str, str] | None) -> bool:
    """Check if request has valid basic auth header.
    
    Args:
        handler: The HTTP request handler
        credentials: Tuple of (username, password) or None if auth disabled
        
    Returns:
        True if auth is disabled or valid credentials provided, False otherwise.
    """
    if credentials is None:
        return True
    
    auth_header = handler.headers.get("Authorization")
    if not auth_header:
        return False
    
    try:
        scheme, encoded = auth_header.split(" ", 1)
        if scheme.lower() != "basic":
            return False
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username == credentials[0] and password == credentials[1]
    except Exception:
        return False


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check requests."""
    
    stats_repo: StatsRepository | None = None
    
    def _require_auth(self) -> bool:
        """Check if authentication is required and valid."""
        credentials = _get_basic_auth_credentials()
        if credentials is None:
            return True
        if not _check_basic_auth(self, credentials):
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Health"')
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
            return False
        return True
    
    def do_GET(self) -> None:
        """Handle GET requests for health checks."""
        if not self._require_auth():
            return
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/ready":
            self._handle_ready()
        else:
            self.send_error(404)
    
    def _handle_health(self) -> None:
        """Basic health check - always returns 200 if server is running."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"status": "healthy", "service": "pinger"}
        self.wfile.write(json.dumps(response).encode())
    
    def _handle_ready(self) -> None:
        """Readiness check - returns 200 only if monitoring is operational."""
        if self.stats_repo is None:
            self.send_error(503)
            return
        
        # Check if we have any ping results
        snap = self.stats_repo.get_snapshot()
        total = snap.get("total", 0)
        
        if total > 0:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "status": "ready",
                "total_pings": total,
                "success": snap.get("success", 0),
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_error(503, "Not ready", "No ping results yet")
    
    def log_message(self, format: str, *args) -> None:
        """Suppress default HTTP logging."""
        logging.debug(f"Health server: {format % args}")


class HealthServer:
    """Health check HTTP server for container orchestration."""
    
    def __init__(self, addr: str = "0.0.0.0", port: int = 8080, stats_repo: StatsRepository | None = None) -> None:
        self.addr = addr
        self.port = port
        self.stats_repo = stats_repo
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._running = False
    
    def start(self) -> None:
        """Start health server in background thread."""
        if self._running:
            return
        
        try:
            HealthHandler.stats_repo = self.stats_repo
            self.server = HTTPServer((self.addr, self.port), HealthHandler)
            self.thread = threading.Thread(target=self._serve, daemon=True)
            self.thread.start()
            self._running = True
            logging.info(f"Health server started on port {self.port}")
        except Exception as exc:
            logging.error(f"Failed to start health server: {exc}")
    
    def _serve(self) -> None:
        """Server loop."""
        while self._running and self.server:
            try:
                self.server.handle_request()
            except Exception as exc:
                logging.debug(f"Health server request error: {exc}")
    
    def stop(self) -> None:
        """Stop health server."""
        self._running = False
        if self.server:
            self.server.shutdown()


def start_health_server(addr: str = "0.0.0.0", port: int = 8080, stats_repo: StatsRepository | None = None) -> HealthServer:
    """Create and start health server."""
    server = HealthServer(addr, port, stats_repo)
    server.start()
    return server
