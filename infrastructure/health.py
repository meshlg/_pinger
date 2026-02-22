from __future__ import annotations

"""Health check HTTP server for Kubernetes/Docker health probes."""

import json
import logging
import secrets
import threading
import time
import base64
import ipaddress
import os
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING

from infrastructure.metrics import (
    HEALTH_AUTH_FAILURES_TOTAL,
    HEALTH_BLOCKED_IPS_TOTAL,
    HEALTH_RATE_LIMITED_TOTAL,
)

if TYPE_CHECKING:
    from stats_repository import StatsRepository


# Module-level cached credentials/tokens (loaded once)
_cached_config: dict = {}
_credentials_loaded: bool = False


class RateLimiter:
    """Thread-safe rate limiter for IP-based request limiting.
    
    Implements a sliding window algorithm for rate limiting.
    Protects against:
    - Brute force authentication attacks
    - DoS attacks on health endpoint
    """
    
    def __init__(
        self,
        max_requests_per_minute: int = 60,
        max_failed_auth_per_minute: int = 10,
        block_duration_seconds: int = 300,
    ) -> None:
        """Initialize rate limiter.
        
        Args:
            max_requests_per_minute: Maximum requests per IP per minute
            max_failed_auth_per_minute: Maximum failed auth attempts per IP per minute
            block_duration_seconds: Duration to block IP after too many failed attempts
        """
        self._max_requests = max_requests_per_minute
        self._max_failed_auth = max_failed_auth_per_minute
        self._block_duration = block_duration_seconds
        
        # Request timestamps per IP: {ip: [timestamp1, timestamp2, ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)
        # Failed auth timestamps per IP
        self._failed_auth: dict[str, list[float]] = defaultdict(list)
        # Blocked IPs with block expiry time: {ip: expiry_timestamp}
        self._blocked: dict[str, float] = {}
        
        self._lock = threading.RLock()
    
    def _cleanup_old_entries(self, entries: list[float], window_seconds: float) -> list[float]:
        """Remove entries older than the window."""
        cutoff = time.time() - window_seconds
        return [ts for ts in entries if ts > cutoff]
    
    def is_blocked(self, ip: str) -> bool:
        """Check if IP is currently blocked."""
        with self._lock:
            if ip in self._blocked:
                if time.time() < self._blocked[ip]:
                    return True
                # Block expired
                del self._blocked[ip]
            return False
    
    def check_request(self, ip: str) -> tuple[bool, str]:
        """Check if request from IP is allowed.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        now = time.time()
        
        with self._lock:
            # Check if blocked
            if self.is_blocked(ip):
                remaining = int(self._blocked[ip] - now)
                return False, f"IP blocked for {remaining}s due to too many failed auth attempts"
            
            # Cleanup and count recent requests
            self._requests[ip] = self._cleanup_old_entries(self._requests[ip], 60.0)
            self._requests[ip].append(now)
            
            if len(self._requests[ip]) > self._max_requests:
                HEALTH_RATE_LIMITED_TOTAL.inc()
                return False, f"Rate limit exceeded ({self._max_requests} requests/minute)"
            
            return True, ""
    
    def record_failed_auth(self, ip: str) -> None:
        """Record a failed authentication attempt."""
        now = time.time()
        HEALTH_AUTH_FAILURES_TOTAL.inc()
        
        with self._lock:
            self._failed_auth[ip] = self._cleanup_old_entries(self._failed_auth[ip], 60.0)
            self._failed_auth[ip].append(now)
            
            # Check if should block
            if len(self._failed_auth[ip]) >= self._max_failed_auth:
                self._blocked[ip] = now + self._block_duration
                HEALTH_BLOCKED_IPS_TOTAL.inc()
                logging.warning(
                    f"Health endpoint: IP {ip} blocked for {self._block_duration}s "
                    f"after {len(self._failed_auth[ip])} failed auth attempts"
                )
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        with self._lock:
            return {
                "tracked_ips": len(self._requests),
                "blocked_ips": len([ip for ip, exp in self._blocked.items() if time.time() < exp]),
                "config": {
                    "max_requests_per_minute": self._max_requests,
                    "max_failed_auth_per_minute": self._max_failed_auth,
                    "block_duration_seconds": self._block_duration,
                }
            }


# Global rate limiter instance (configured on server start)
_rate_limiter: RateLimiter | None = None


def _get_rate_limiter() -> RateLimiter | None:
    """Get the global rate limiter instance."""
    return _rate_limiter


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


def _is_valid_ip(value: str) -> bool:
    """Return True if value is a valid IPv4/IPv6 literal."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _is_trusted_proxy(client_ip: str) -> bool:
    """Return True if direct client IP is explicitly configured as trusted proxy.

    HEALTH_TRUSTED_PROXIES supports comma-separated IPs and CIDRs.
    Example: "127.0.0.1,10.0.0.0/8,192.168.1.10"
    """
    trusted_raw = os.environ.get("HEALTH_TRUSTED_PROXIES", "").strip()
    if not trusted_raw:
        return False

    try:
        client_addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for entry in trusted_raw.split(","):
        candidate = entry.strip()
        if not candidate:
            continue
        try:
            if "/" in candidate:
                if client_addr in ipaddress.ip_network(candidate, strict=False):
                    return True
            elif client_addr == ipaddress.ip_address(candidate):
                return True
        except ValueError:
            logging.warning(f"Invalid HEALTH_TRUSTED_PROXIES entry ignored: {candidate}")

    return False

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
        # Use timing-safe comparison to prevent timing attacks
        expected_user = credentials.get("basic_user") or ""
        expected_pass = credentials.get("basic_pass") or ""
        return (secrets.compare_digest(username, expected_user) and 
                secrets.compare_digest(password, expected_pass))
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
    expected_token = credentials.get("token") or ""
    
    provided_token = handler.headers.get(token_header)
    if not provided_token:
        return False
    
    # Use timing-safe comparison to prevent timing attacks
    return secrets.compare_digest(provided_token, expected_token)


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check requests."""
    
    stats_repo: StatsRepository | None = None
    
    def _get_client_ip(self) -> str:
        """Get client IP address from request."""
        direct_ip = self.client_address[0] if self.client_address else "unknown"

        # Only trust X-Forwarded-For from explicitly configured proxies.
        forwarded = self.headers.get("X-Forwarded-For")
        if not forwarded:
            return direct_ip

        if not _is_trusted_proxy(direct_ip):
            return direct_ip

        # Take the first IP (original client) and validate it.
        forwarded_ip = forwarded.split(",")[0].strip()
        if _is_valid_ip(forwarded_ip):
            return forwarded_ip

        logging.debug(f"Ignoring invalid X-Forwarded-For value from trusted proxy {direct_ip}: {forwarded_ip}")
        return direct_ip
    
    def _check_rate_limit(self) -> bool:
        """Check if request is allowed by rate limiter.
        
        Returns:
            True if request is allowed, False if rate limited
        """
        limiter = _get_rate_limiter()
        if limiter is None:
            return True  # Rate limiting disabled
        
        ip = self._get_client_ip()

        # Check rate limit
        allowed, reason = limiter.check_request(ip)
        if not allowed:
            self._send_rate_limit_response(reason)
            return False
        
        return True
    
    def _send_rate_limit_response(self, reason: str) -> None:
        """Send 429 Too Many Requests response."""
        self.send_response(429)
        self.send_header("Content-Type", "application/json")
        self.send_header("Retry-After", "60")
        self.end_headers()
        response = {"error": "Too Many Requests", "reason": reason}
        self.wfile.write(json.dumps(response).encode())
    
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
            # Record failed auth attempt
            limiter = _get_rate_limiter()
            if limiter:
                limiter.record_failed_auth(self._get_client_ip())
            self._send_auth_response("Basic")
            return False
        
        if auth_type == "token":
            if _check_token_auth(self, credentials):
                return True
            # Record failed auth attempt
            limiter = _get_rate_limiter()
            if limiter:
                limiter.record_failed_auth(self._get_client_ip())
            self._send_auth_response(credentials.get("token_header", "X-Health-Token"))
            return False
        
        # Both methods - either is valid
        if _check_basic_auth(self, credentials) or _check_token_auth(self, credentials):
            return True
        # Record failed auth attempt
        limiter = _get_rate_limiter()
        if limiter:
            limiter.record_failed_auth(self._get_client_ip())
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
        # Check rate limit first
        if not self._check_rate_limit():
            return
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
        - Rate limiting to prevent brute force and DoS attacks
    """
    
    def __init__(
        self,
        addr: str = "127.0.0.1",
        port: int = 8080,
        stats_repo: StatsRepository | None = None,
        rate_limit_enabled: bool = True,
        max_requests_per_minute: int = 60,
        max_failed_auth_per_minute: int = 10,
        block_duration_seconds: int = 300,
    ) -> None:
        """Initialize health server.
        
        Args:
            addr: Network address to bind to
            port: Port to listen on
            stats_repo: Optional stats repository for readiness checks
            rate_limit_enabled: Enable rate limiting
            max_requests_per_minute: Maximum requests per IP per minute
            max_failed_auth_per_minute: Maximum failed auth attempts per IP per minute
            block_duration_seconds: Duration to block IP after too many failed attempts
        """
        self.addr = addr
        self.port = port
        self.stats_repo = stats_repo
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._running = False
        
        # Initialize rate limiter
        global _rate_limiter
        if rate_limit_enabled:
            _rate_limiter = RateLimiter(
                max_requests_per_minute=max_requests_per_minute,
                max_failed_auth_per_minute=max_failed_auth_per_minute,
                block_duration_seconds=block_duration_seconds,
            )
        else:
            _rate_limiter = None
    
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
                rate_desc = "rate limiting enabled" if _rate_limiter else "no rate limiting"
                logging.info(f"Health server started on http://127.0.0.1:{self.port} (localhost-only, {rate_desc})")
            else:
                auth_desc = {
                    "none": "NO AUTH (INSECURE!)",
                    "basic": "Basic Auth",
                    "token": f"Token ({credentials.get('token_header', 'X-Health-Token')})",
                    "both": "Basic or Token",
                }.get(auth_type, "Unknown")
                rate_desc = "rate limiting enabled" if _rate_limiter else "no rate limiting"
                logging.info(f"Health server started on http://{self.addr}:{self.port} ({auth_desc}, {rate_desc})")
                
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


def start_health_server(
    addr: str = "127.0.0.1",
    port: int = 8080,
    stats_repo: StatsRepository | None = None,
    rate_limit_enabled: bool = True,
    max_requests_per_minute: int = 60,
    max_failed_auth_per_minute: int = 10,
    block_duration_seconds: int = 300,
) -> HealthServer:
    """Create and start health server.
    
    Security:
        - Default binds to 127.0.0.1 (localhost only)
        - Set addr="0.0.0.0" for pod network (Kubernetes)
        - X-Forwarded-For is ignored unless HEALTH_TRUSTED_PROXIES is configured
        - Authentication via environment variables:
            - Basic Auth: HEALTH_AUTH_USER + HEALTH_AUTH_PASS
            - Token Auth: HEALTH_TOKEN [+ HEALTH_TOKEN_HEADER]
            - Both: Either method is accepted
        - Set HEALTH_ALLOW_NO_AUTH=1 to bypass auth requirement (not recommended)
        - Rate limiting enabled by default to prevent brute force attacks
    
    Rate Limiting Configuration (via environment variables):
        - HEALTH_RATE_LIMIT_ENABLED: Enable/disable rate limiting (default: true)
        - HEALTH_MAX_REQUESTS_PER_MINUTE: Max requests per IP (default: 60)
        - HEALTH_MAX_FAILED_AUTH_PER_MINUTE: Max failed auth attempts (default: 10)
        - HEALTH_BLOCK_DURATION_SECONDS: Block duration after too many failures (default: 300)
    
    Args:
        addr: Network address to bind to (127.0.0.1 for localhost-only)
        port: Port to listen on
        stats_repo: Optional stats repository for readiness checks
        rate_limit_enabled: Enable rate limiting (default: True)
        max_requests_per_minute: Maximum requests per IP per minute (default: 60)
        max_failed_auth_per_minute: Maximum failed auth attempts per IP per minute (default: 10)
        block_duration_seconds: Duration to block IP after too many failed attempts (default: 300)
    
    Returns:
        HealthServer instance
    """
    # Allow environment variable overrides for rate limiting
    if os.environ.get("HEALTH_RATE_LIMIT_ENABLED", "").lower() in ("0", "false", "no"):
        rate_limit_enabled = False
    
    env_max_requests = os.environ.get("HEALTH_MAX_REQUESTS_PER_MINUTE")
    if env_max_requests:
        try:
            max_requests_per_minute = int(env_max_requests)
        except ValueError:
            pass
    
    env_max_failed = os.environ.get("HEALTH_MAX_FAILED_AUTH_PER_MINUTE")
    if env_max_failed:
        try:
            max_failed_auth_per_minute = int(env_max_failed)
        except ValueError:
            pass
    
    env_block_duration = os.environ.get("HEALTH_BLOCK_DURATION_SECONDS")
    if env_block_duration:
        try:
            block_duration_seconds = int(env_block_duration)
        except ValueError:
            pass
    
    server = HealthServer(
        addr=addr,
        port=port,
        stats_repo=stats_repo,
        rate_limit_enabled=rate_limit_enabled,
        max_requests_per_minute=max_requests_per_minute,
        max_failed_auth_per_minute=max_failed_auth_per_minute,
        block_duration_seconds=block_duration_seconds,
    )
    server.start()
    return server
