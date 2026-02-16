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


# Module-level cached credentials/tokens (loaded once)
_cached_config: dict = {}
_credentials_loaded: bool = False


def _read_secret(name: str) -> str | None:
    """Read secret from file (via _FILE env var) or direct env var."""
    # Try _FILE variant first (Docker Secrets)
    file_path = os.environ.get(f"{name}_FILE")
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    
    # Fallback to direct env var
    return os.environ.get(name)

def _load_security_config() -> dict:
    """Load and cache security configuration from environment.
    
    Returns:
        Dict with:
        - auth_type: "basic", "token", "both", or "none"
        - basic_user: str | None
        - basic_pass: str | None
        - token: str | None
    """
    global _cached_config, _credentials_loaded
    
    if _credentials_loaded:
        return _cached_config
    
    basic_user = _read_secret("HEALTH_AUTH_USER")
    basic_pass = _read_secret("HEALTH_AUTH_PASS")
    token = _read_secret("HEALTH_TOKEN")
    token_header = os.environ.get("HEALTH_TOKEN_HEADER", "X-Health-Token")
    
    # Determine auth type
    has_basic = bool(basic_user and basic_pass)
    has_token = bool(token)
    
    if has_basic and has_token:
        auth_type = "both"
    elif has_basic:
        auth_type = "basic"
    elif has_token:
        auth_type = "token"
    else:
        auth_type = "none"
    
    _cached_config = {
        "auth_type": auth_type,
        "basic_user": basic_user,
        "basic_pass": basic_pass,
        "token": token,
        "token_header": token_header,
    }
    
    _credentials_loaded = True
    return _cached_config


def _check_basic_auth(handler: BaseHTTPRequestHandler, credentials: dict) -> bool:
    """Check Basic Auth credentials.
    
    Args:
        handler: The HTTP request handler
        credentials: Dict with basic_user and basic_pass
        
    Returns:
        True if auth disabled, valid credentials provided, or header missing (partial auth).
    """
    auth_type = credentials.get("auth_type", "none")
    if auth_type not in ("basic", "both"):
        return True
    
    # If expecting basic auth, header is required
    auth_header = handler.headers.get("Authorization")
    if not auth_header:
        return False
    
    try:
        scheme, encoded = auth_header.split(" ", 1)
        if scheme.lower() != "basic":
            return False
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
        return (username == credentials.get("basic_user") and 
                password == credentials.get("basic_pass"))
    except Exception:
        return False


def _check_token_auth(handler: BaseHTTPRequestHandler, credentials: dict) -> bool:
    """Check token auth via custom header.
    
    Args:
        handler: The HTTP request handler
        credentials: Dict with token and token_header
        
    Returns:
        True if auth disabled, valid token provided, or header missing (partial auth).
    """
    auth_type = credentials.get("auth_type", "none")
    if auth_type not in ("token", "both"):
        return True
    
    # If expecting token auth, header is required
    token_header = credentials.get("token_header", "X-Health-Token")
    expected_token = credentials.get("token")
    
    provided_token = handler.headers.get(token_header)
    if not provided_token:
        return False
    
    return provided_token == expected_token


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check requests."""
    
    stats_repo: StatsRepository | None = None
    
    def _require_auth(self) -> bool:
        """Check if authentication is required and valid.
        
        Supports:
        - Basic Auth (Authorization: Basic <base64>)
        - Token Auth (X-Health-Token: <token>)
        - Both methods (either is accepted)
        """
        credentials = _load_security_config()
        auth_type = credentials.get("auth_type", "none")
        
        if auth_type == "none":
            return True
        
        # Check auth
        if auth_type == "basic":
            if _check_basic_auth(self, credentials):
                return True
            self._send_auth_response("Basic")
            return False
        
        if auth_type == "token":
            if _check_token_auth(self, credentials):
                return True
            self._send_auth_response(credentials.get("token_header", "X-Health-Token"))
            return False
        
        # Both methods - either is valid
        if _check_basic_auth(self, credentials) or _check_token_auth(self, credentials):
            return True
        self._send_auth_response("Basic or " + credentials.get("token_header", "X-Health-Token"))
        return False
    
    def _send_auth_response(self, method: str) -> None:
        """Send 401 Unauthorized response."""
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="Health"')
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"error": f"Unauthorized - requires {method} authentication"}
        self.wfile.write(json.dumps(response).encode())
    
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
    """Health check HTTP server for container orchestration.
    
    Security:
        - Default binding to 127.0.0.1 (localhost-only)
        - Auth required for non-localhost bindings
        - Supports Basic Auth and Token Auth
        - GET-only endpoints (safe from CSRF attacks)
    """
    
    def __init__(self, addr: str = "127.0.0.1", port: int = 8080, stats_repo: StatsRepository | None = None) -> None:
        self.addr = addr
        self.port = port
        self.stats_repo = stats_repo
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._running = False
    
    def _check_security(self) -> bool:
        """Check security configuration and warn/fail if insecure.
        
        Returns:
            True if configuration is acceptable, False if should not start.
        """
        credentials = _load_security_config()
        auth_type = credentials.get("auth_type", "none")
        is_localhost = self.addr in ("127.0.0.1", "localhost")
        
        # Localhost binding - always allowed
        if is_localhost:
            return True
        
        # Non-localhost binding requires authentication
        if auth_type == "none":
            allow_no_auth = os.environ.get("HEALTH_ALLOW_NO_AUTH", "").lower() in ("1", "true", "yes")
            if allow_no_auth:
                logging.warning(
                    f"HEALTH_ADDR={self.addr} without authentication! "
                    f"Set HEALTH_AUTH_USER/PASS (Basic) or HEALTH_TOKEN. "
                    f"Server will START but is INSECURE."
                )
                return True
            else:
                logging.error(
                    f"SECURITY ERROR: HEALTH_ADDR={self.addr} requires authentication. "
                    f"Set one of:\n"
                    f"  - HEALTH_AUTH_USER and HEALTH_AUTH_PASS (Basic Auth)\n"
                    f"  - HEALTH_TOKEN (Token Auth)\n"
                    f"  - Or set HEALTH_ALLOW_NO_AUTH=1 to override (NOT recommended)"
                )
                return False
        
        return True
    
    def start(self) -> None:
        """Start health server in background thread."""
        if self._running:
            return
        
        # Security check
        if not self._check_security():
            logging.error("Health server not started due to security configuration.")
            return
        
        try:
            HealthHandler.stats_repo = self.stats_repo
            self.server = HTTPServer((self.addr, self.port), HealthHandler)
            self.thread = threading.Thread(target=self._serve, daemon=True)
            self.thread.start()
            self._running = True
            
            # Log configuration
            credentials = _load_security_config()
            auth_type = credentials.get("auth_type", "none")
            
            if self.addr in ("127.0.0.1", "localhost"):
                logging.info(f"Health server started on http://127.0.0.1:{self.port} (localhost-only)")
            else:
                auth_desc = {
                    "none": "NO AUTH (INSECURE!)",
                    "basic": "Basic Auth",
                    "token": f"Token ({credentials.get('token_header', 'X-Health-Token')})",
                    "both": "Basic or Token",
                }.get(auth_type, "Unknown")
                logging.info(f"Health server started on http://{self.addr}:{self.port} ({auth_desc})")
                
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


def start_health_server(addr: str = "127.0.0.1", port: int = 8080, stats_repo: StatsRepository | None = None) -> HealthServer:
    """Create and start health server.
    
    Security:
        - Default binds to 127.0.0.1 (localhost only)
        - Set addr="0.0.0.0" for pod network (Kubernetes)
        - Authentication via environment variables:
            - Basic Auth: HEALTH_AUTH_USER + HEALTH_AUTH_PASS
            - Token Auth: HEALTH_TOKEN [+ HEALTH_TOKEN_HEADER]
            - Both: Either method is accepted
        - Set HEALTH_ALLOW_NO_AUTH=1 to bypass auth requirement (not recommended)
    
    Args:
        addr: Network address to bind to (127.0.0.1 for localhost-only)
        port: Port to listen on
        stats_repo: Optional stats repository for readiness checks
    
    Returns:
        HealthServer instance
    """
    server = HealthServer(addr, port, stats_repo)
    server.start()
    return server
