from __future__ import annotations

"""Health check HTTP server for Kubernetes/Docker health probes."""

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from stats_repository import StatsRepository


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check requests."""
    
    stats_repo: StatsRepository | None = None
    
    def do_GET(self) -> None:
        """Handle GET requests for health checks."""
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
    
    def __init__(self, port: int = 8080, stats_repo: StatsRepository | None = None) -> None:
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
            self.server = HTTPServer(("0.0.0.0", self.port), HealthHandler)
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


def start_health_server(port: int = 8080, stats_repo: StatsRepository | None = None) -> HealthServer:
    """Create and start health server."""
    server = HealthServer(port, stats_repo)
    server.start()
    return server
