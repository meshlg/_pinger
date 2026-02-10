"""
Application configuration settings.

All configuration variables are defined here and can be overridden via environment variables.
"""

import locale
import os

# ─────────────────────────────────────────────────────────────────────────────
# Version
# ─────────────────────────────────────────────────────────────────────────────

VERSION = "2.3.3"

# ─────────────────────────────────────────────────────────────────────────────
# Language Detection
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_LANGUAGES = ["en", "ru"]


def _detect_system_language() -> str:
    """Detect system language and return supported language code."""
    try:
        # Get system locale
        system_locale = locale.getlocale()[0]
        if system_locale:
            lang_code = system_locale.lower()[:2]
            # Map common Russian locale codes
            if lang_code in ("ru", "be", "uk", "kk"):
                return "ru"
        # Check environment variable as fallback
        env_lang = os.environ.get("LANG", "")
        if "ru" in env_lang.lower():
            return "ru"
    except Exception:
        pass
    return "en"


CURRENT_LANGUAGE = _detect_system_language()

# ─────────────────────────────────────────────────────────────────────────────
# Core Settings
# ─────────────────────────────────────────────────────────────────────────────

TARGET_IP = os.environ.get("TARGET_IP", "1.1.1.1")
INTERVAL = float(os.environ.get("INTERVAL", "1"))
WINDOW_SIZE = 1800
LATENCY_WINDOW = 600

# ─────────────────────────────────────────────────────────────────────────────
# Alert Settings
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_SOUND_ALERTS = True
ALERT_COOLDOWN = 5
ALERT_ON_PACKET_LOSS = True
ALERT_ON_HIGH_LATENCY = True
HIGH_LATENCY_THRESHOLD = 100

# ─────────────────────────────────────────────────────────────────────────────
# Threshold Settings
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_THRESHOLD_ALERTS = True
PACKET_LOSS_THRESHOLD = 5.0
AVG_LATENCY_THRESHOLD = 100
CONSECUTIVE_LOSS_THRESHOLD = 5
JITTER_THRESHOLD = 30

# ─────────────────────────────────────────────────────────────────────────────
# IP Change Detection
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_IP_CHANGE_ALERT = True
IP_CHECK_INTERVAL = 15
IP_CHANGE_SOUND = True
LOG_IP_CHANGES = True

# ─────────────────────────────────────────────────────────────────────────────
# DNS Monitoring
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_DNS_MONITORING = True
DNS_TEST_DOMAIN = "cloudflare.com"
DNS_CHECK_INTERVAL = 10
DNS_SLOW_THRESHOLD = 100

# DNS record types to test (requires dnspython)
DNS_RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "NS"]

# DNS Benchmark tests (Cached/Uncached/DotCom)
ENABLE_DNS_BENCHMARK = True
DNS_BENCHMARK_DOTCOM_DOMAIN = "cloudflare.com"  # Domain for DotCom test
DNS_BENCHMARK_SERVERS = ["system"]  # "system" uses system resolver, or list IPs: ["1.1.1.1", "8.8.8.8"]
DNS_BENCHMARK_HISTORY_SIZE = 50  # Number of queries to keep for statistics

# ─────────────────────────────────────────────────────────────────────────────
# Traceroute Settings
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_AUTO_TRACEROUTE = False  # Disabled — traceroute only on manual trigger or route change
TRACEROUTE_TRIGGER_LOSSES = 3
TRACEROUTE_COOLDOWN = 300       # Min interval (seconds)
TRACEROUTE_MAX_HOPS = 15

# ─────────────────────────────────────────────────────────────────────────────
# MTU Monitoring
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_MTU_MONITORING = True
MTU_CHECK_INTERVAL = 30
ENABLE_PATH_MTU_DISCOVERY = True
PATH_MTU_CHECK_INTERVAL = 120
DEFAULT_MTU = 1500

# MTU issue detection hysteresis
MTU_ISSUE_CONSECUTIVE = 3  # how many consecutive failing checks to mark an MTU issue
MTU_CLEAR_CONSECUTIVE = 2  # how many consecutive OK checks to clear the MTU issue
MTU_DIFF_THRESHOLD = 50    # minimal difference between local and path MTU to consider an issue (bytes)

# ─────────────────────────────────────────────────────────────────────────────
# TTL Monitoring
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_TTL_MONITORING = True
TTL_CHECK_INTERVAL = 10

# ─────────────────────────────────────────────────────────────────────────────
# Hop Monitoring
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_HOP_MONITORING = True
HOP_PING_INTERVAL = 1          # seconds between hop ping cycles
HOP_PING_TIMEOUT = 0.5         # seconds per hop ping (500ms for fast response)
HOP_REDISCOVER_INTERVAL = 3600 # Once per hour only
HOP_LATENCY_GOOD = 50          # ms — green threshold
HOP_LATENCY_WARN = 100         # ms — yellow threshold (above = red)

# ─────────────────────────────────────────────────────────────────────────────
# Problem Analysis
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_PROBLEM_ANALYSIS = True
PROBLEM_ANALYSIS_INTERVAL = 60
PROBLEM_HISTORY_SIZE = 100
PREDICTION_WINDOW = 300
# Suppress repetitive logs for problems and route changes (seconds)
PROBLEM_LOG_SUPPRESSION_SECONDS = 6000
ROUTE_LOG_SUPPRESSION_SECONDS = 6000

# ─────────────────────────────────────────────────────────────────────────────
# Route Analysis
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_ROUTE_ANALYSIS = True
ROUTE_ANALYSIS_INTERVAL = 1800  # Check route every 30 min
ROUTE_HISTORY_SIZE = 10
HOP_TIMEOUT_THRESHOLD = 3000

# Route change detection settings
ROUTE_CHANGE_CONSECUTIVE = 2  # consecutive detections to consider route changed
ROUTE_CHANGE_HOP_DIFF = 2     # minimal number of changed hops to consider significant
ROUTE_IGNORE_FIRST_HOPS = 2   # ignore changes in first N hops (local network)
ROUTE_SAVE_ON_CHANGE_CONSECUTIVE = 2  # save traceroute after N consecutive changes

# ─────────────────────────────────────────────────────────────────────────────
# Visual Alerts
# ─────────────────────────────────────────────────────────────────────────────

SHOW_VISUAL_ALERTS = True
ALERT_DISPLAY_TIME = 10
ALERT_PANEL_LINES = 3
MAX_ACTIVE_ALERTS = 3

# ─────────────────────────────────────────────────────────────────────────────
# Resource Limits and Safety Settings
# ─────────────────────────────────────────────────────────────────────────────

# Prevent excessive resource usage and memory leaks
MAX_WORKER_THREADS = int(os.environ.get("MAX_WORKER_THREADS", "4"))  # Limit thread pool size
MAX_EXECUTOR_QUEUE_SIZE = int(os.environ.get("MAX_EXECUTOR_QUEUE_SIZE", "100"))  # Prevent task queue overflow
MAX_MEMORY_MB = int(os.environ.get("MAX_MEMORY_MB", "500"))  # Memory limit warning threshold
ENABLE_MEMORY_MONITORING = os.environ.get("ENABLE_MEMORY_MONITORING", "true").lower() in ("true", "1", "yes")

# Collection size limits to prevent memory leaks
MAX_ALERTS_HISTORY = int(os.environ.get("MAX_ALERTS_HISTORY", "100"))  # Max alerts in history
MAX_TRACEROUTE_FILES = int(os.environ.get("MAX_TRACEROUTE_FILES", "100"))  # Auto-cleanup old traceroutes
MAX_PROBLEM_HISTORY = int(os.environ.get("MAX_PROBLEM_HISTORY", "50"))  # Problem analyzer history limit
MAX_ROUTE_HISTORY = int(os.environ.get("MAX_ROUTE_HISTORY", "20"))  # Route changes history
MAX_DNS_BENCHMARK_HISTORY = int(os.environ.get("MAX_DNS_BENCHMARK_HISTORY", "100"))  # DNS benchmark results

# Rate limiting to prevent excessive operations
PING_BURST_LIMIT = int(os.environ.get("PING_BURST_LIMIT", "10"))  # Max concurrent pings
DNS_CHECK_COOLDOWN = int(os.environ.get("DNS_CHECK_COOLDOWN", "5"))  # Seconds between DNS checks
TRACEROUTE_MIN_INTERVAL = int(os.environ.get("TRACEROUTE_MIN_INTERVAL", "60"))  # Minimum seconds between traceroutes

# Graceful shutdown timeout
SHUTDOWN_TIMEOUT_SECONDS = int(os.environ.get("SHUTDOWN_TIMEOUT_SECONDS", "10"))
FORCE_KILL_TIMEOUT = int(os.environ.get("FORCE_KILL_TIMEOUT", "5"))

# ─────────────────────────────────────────────────────────────────────────────
# Single Instance
# ─────────────────────────────────────────────────────────────────────────────

# Enable single instance enforcement (prevents multiple copies running simultaneously)
ENABLE_SINGLE_INSTANCE = os.environ.get("ENABLE_SINGLE_INSTANCE", "true").lower() in ("true", "1", "yes")
# Check for stale lock files (remove lock if owning process is dead, requires psutil)
ENABLE_STALE_LOCK_CHECK = os.environ.get("ENABLE_STALE_LOCK_CHECK", "true").lower() in ("true", "1", "yes")

# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_METRICS = os.environ.get("ENABLE_METRICS", "true").lower() in ("true", "1", "yes")

# Version check settings
ENABLE_VERSION_CHECK = os.environ.get("ENABLE_VERSION_CHECK", "true").lower() in ("true", "1", "yes")
VERSION_CHECK_INTERVAL = int(os.environ.get("VERSION_CHECK_INTERVAL", "3600"))  # Check every hour (3600 seconds)

# Metrics server binding - SECURITY: defaults to localhost (127.0.0.1) for local-only access
# For Kubernetes/Docker: use internal network (e.g., "0.0.0.0" for pod network)
# Authentication via METRICS_AUTH_USER and METRICS_AUTH_PASS (Basic Auth)
METRICS_ADDR = os.environ.get("METRICS_ADDR", "127.0.0.1")
METRICS_PORT = int(os.environ.get("METRICS_PORT", "8000"))

# ─────────────────────────────────────────────────────────────────────────────
# Health Endpoint
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_HEALTH_ENDPOINT = os.environ.get("ENABLE_HEALTH_ENDPOINT", "true").lower() in ("true", "1", "yes")
# Health server binding - SECURITY: defaults to localhost (127.0.0.1) for local-only access
# For Kubernetes/Docker: use internal network (e.g., "0.0.0.0" for pod network)
# WARNING: Authentication is REQUIRED for non-localhost bindings (see below)
# Set HEALTH_ALLOW_NO_AUTH=1 to bypass auth requirement (NOT recommended for production)
HEALTH_ADDR = os.environ.get("HEALTH_ADDR", "127.0.0.1")
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8001"))

# Authentication methods (at least one required for non-localhost):
# 1. Basic Auth: Set both variables
HEALTH_AUTH_USER = os.environ.get("HEALTH_AUTH_USER", "")
HEALTH_AUTH_PASS = os.environ.get("HEALTH_AUTH_PASS", "")
# 2. Token Auth: Set this variable (simpler for load balancers/Prometheus)
HEALTH_TOKEN = os.environ.get("HEALTH_TOKEN", "")
HEALTH_TOKEN_HEADER = os.environ.get("HEALTH_TOKEN_HEADER", "X-Health-Token")

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

LOG_DIR = os.path.expanduser("~/.pinger")
LOG_FILE = os.path.join(LOG_DIR, "ping_monitor.log")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# If True, truncate (clear) log file at startup
LOG_TRUNCATE_ON_START = os.environ.get("LOG_TRUNCATE_ON_START", "true").lower() in ("true", "1", "yes")
