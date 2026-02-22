"""
Application configuration settings.

All configuration variables are defined here and can be overridden via environment variables.
"""

import locale
import os
from .settings_model import Settings

# Initialize settings
settings = Settings()

# ─────────────────────────────────────────────────────────────────────────────
# Version
# ─────────────────────────────────────────────────────────────────────────────

VERSION = settings.VERSION

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

TARGET_IP = settings.TARGET_IP
INTERVAL = settings.INTERVAL
WINDOW_SIZE = settings.WINDOW_SIZE
LATENCY_WINDOW = settings.LATENCY_WINDOW

# ─────────────────────────────────────────────────────────────────────────────
# Alert Settings
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_SOUND_ALERTS = settings.ENABLE_SOUND_ALERTS
ALERT_COOLDOWN = settings.ALERT_COOLDOWN
ALERT_ON_PACKET_LOSS = settings.ALERT_ON_PACKET_LOSS
ALERT_ON_HIGH_LATENCY = settings.ALERT_ON_HIGH_LATENCY
HIGH_LATENCY_THRESHOLD = settings.HIGH_LATENCY_THRESHOLD
ENABLE_QUIET_HOURS = settings.ENABLE_QUIET_HOURS
QUIET_HOURS_START = settings.QUIET_HOURS_START
QUIET_HOURS_END = settings.QUIET_HOURS_END

# ─────────────────────────────────────────────────────────────────────────────
# Threshold Settings
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_THRESHOLD_ALERTS = settings.ENABLE_THRESHOLD_ALERTS
PACKET_LOSS_THRESHOLD = settings.PACKET_LOSS_THRESHOLD
AVG_LATENCY_THRESHOLD = settings.AVG_LATENCY_THRESHOLD
CONSECUTIVE_LOSS_THRESHOLD = settings.CONSECUTIVE_LOSS_THRESHOLD
JITTER_THRESHOLD = settings.JITTER_THRESHOLD

# ─────────────────────────────────────────────────────────────────────────────
# Smart Alert System
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_SMART_ALERTS = settings.ENABLE_SMART_ALERTS
ENABLE_ALERT_DEDUPLICATION = settings.ENABLE_ALERT_DEDUPLICATION
ALERT_DEDUP_WINDOW_SECONDS = settings.ALERT_DEDUP_WINDOW_SECONDS
ALERT_SIMILARITY_THRESHOLD = settings.ALERT_SIMILARITY_THRESHOLD
ENABLE_ALERT_GROUPING = settings.ENABLE_ALERT_GROUPING
ALERT_GROUP_WINDOW_SECONDS = settings.ALERT_GROUP_WINDOW_SECONDS
ALERT_GROUP_MAX_SIZE = settings.ALERT_GROUP_MAX_SIZE
ENABLE_DYNAMIC_PRIORITY = settings.ENABLE_DYNAMIC_PRIORITY
PRIORITY_BUSINESS_IMPACT_WEIGHT = settings.PRIORITY_BUSINESS_IMPACT_WEIGHT
PRIORITY_USER_IMPACT_WEIGHT = settings.PRIORITY_USER_IMPACT_WEIGHT
PRIORITY_SERVICE_CRITICALITY_WEIGHT = settings.PRIORITY_SERVICE_CRITICALITY_WEIGHT
PRIORITY_TIME_WEIGHT = settings.PRIORITY_TIME_WEIGHT
ALERT_ESCALATION_TIME_MINUTES = settings.ALERT_ESCALATION_TIME_MINUTES
ENABLE_ADAPTIVE_THRESHOLDS = settings.ENABLE_ADAPTIVE_THRESHOLDS
ADAPTIVE_BASELINE_WINDOW_HOURS = settings.ADAPTIVE_BASELINE_WINDOW_HOURS
ADAPTIVE_UPDATE_INTERVAL_MINUTES = settings.ADAPTIVE_UPDATE_INTERVAL_MINUTES
ADAPTIVE_ANOMALY_SIGMA = settings.ADAPTIVE_ANOMALY_SIGMA
ENABLE_NOISE_REDUCTION = settings.ENABLE_NOISE_REDUCTION
ALERT_RATE_LIMIT_PER_MINUTE = settings.ALERT_RATE_LIMIT_PER_MINUTE
ALERT_BURST_LIMIT = settings.ALERT_BURST_LIMIT
ALERT_HISTORY_SIZE = settings.ALERT_HISTORY_SIZE
ALERT_HISTORY_RETENTION_HOURS = settings.ALERT_HISTORY_RETENTION_HOURS

# ─────────────────────────────────────────────────────────────────────────────
# IP Change Detection
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_IP_CHANGE_ALERT = settings.ENABLE_IP_CHANGE_ALERT
IP_CHECK_INTERVAL = settings.IP_CHECK_INTERVAL
IP_CHANGE_SOUND = settings.IP_CHANGE_SOUND
LOG_IP_CHANGES = settings.LOG_IP_CHANGES

# ─────────────────────────────────────────────────────────────────────────────
# DNS Monitoring
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_DNS_MONITORING = settings.ENABLE_DNS_MONITORING
DNS_TEST_DOMAIN = settings.DNS_TEST_DOMAIN
DNS_CHECK_INTERVAL = settings.DNS_CHECK_INTERVAL
DNS_SLOW_THRESHOLD = settings.DNS_SLOW_THRESHOLD
DNS_RECORD_TYPES = settings.DNS_RECORD_TYPES
ENABLE_DNS_BENCHMARK = settings.ENABLE_DNS_BENCHMARK
DNS_BENCHMARK_DOTCOM_DOMAIN = settings.DNS_BENCHMARK_DOTCOM_DOMAIN
DNS_BENCHMARK_SERVERS = settings.DNS_BENCHMARK_SERVERS
DNS_BENCHMARK_HISTORY_SIZE = settings.DNS_BENCHMARK_HISTORY_SIZE

# ─────────────────────────────────────────────────────────────────────────────
# Traceroute Settings
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_AUTO_TRACEROUTE = settings.ENABLE_AUTO_TRACEROUTE
TRACEROUTE_TRIGGER_LOSSES = settings.TRACEROUTE_TRIGGER_LOSSES
TRACEROUTE_COOLDOWN = settings.TRACEROUTE_COOLDOWN
TRACEROUTE_MAX_HOPS = settings.TRACEROUTE_MAX_HOPS

# ─────────────────────────────────────────────────────────────────────────────
# MTU Monitoring
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_MTU_MONITORING = settings.ENABLE_MTU_MONITORING
MTU_CHECK_INTERVAL = settings.MTU_CHECK_INTERVAL
ENABLE_PATH_MTU_DISCOVERY = settings.ENABLE_PATH_MTU_DISCOVERY
PATH_MTU_CHECK_INTERVAL = settings.PATH_MTU_CHECK_INTERVAL
DEFAULT_MTU = settings.DEFAULT_MTU
MTU_ISSUE_CONSECUTIVE = settings.MTU_ISSUE_CONSECUTIVE
MTU_CLEAR_CONSECUTIVE = settings.MTU_CLEAR_CONSECUTIVE
MTU_DIFF_THRESHOLD = settings.MTU_DIFF_THRESHOLD

# ─────────────────────────────────────────────────────────────────────────────
# TTL Monitoring
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_TTL_MONITORING = settings.ENABLE_TTL_MONITORING
TTL_CHECK_INTERVAL = settings.TTL_CHECK_INTERVAL

# ─────────────────────────────────────────────────────────────────────────────
# Hop Monitoring
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_HOP_MONITORING = settings.ENABLE_HOP_MONITORING
HOP_PING_INTERVAL = settings.HOP_PING_INTERVAL
HOP_PING_TIMEOUT = settings.HOP_PING_TIMEOUT
HOP_REDISCOVER_INTERVAL = settings.HOP_REDISCOVER_INTERVAL
HOP_LATENCY_GOOD = settings.HOP_LATENCY_GOOD
HOP_LATENCY_WARN = settings.HOP_LATENCY_WARN

# ─────────────────────────────────────────────────────────────────────────────
# Problem Analysis
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_PROBLEM_ANALYSIS = settings.ENABLE_PROBLEM_ANALYSIS
PROBLEM_ANALYSIS_INTERVAL = settings.PROBLEM_ANALYSIS_INTERVAL
PROBLEM_HISTORY_SIZE = settings.PROBLEM_HISTORY_SIZE
PREDICTION_WINDOW = settings.PREDICTION_WINDOW
PROBLEM_LOG_SUPPRESSION_SECONDS = settings.PROBLEM_LOG_SUPPRESSION_SECONDS
ROUTE_LOG_SUPPRESSION_SECONDS = settings.ROUTE_LOG_SUPPRESSION_SECONDS

PROBLEM_LOSS_THRESHOLD = settings.PROBLEM_LOSS_THRESHOLD
PROBLEM_LATENCY_THRESHOLD = settings.PROBLEM_LATENCY_THRESHOLD
PROBLEM_JITTER_THRESHOLD = settings.PROBLEM_JITTER_THRESHOLD
PROBLEM_CONSECUTIVE_LOSS_THRESHOLD = settings.PROBLEM_CONSECUTIVE_LOSS_THRESHOLD

# ─────────────────────────────────────────────────────────────────────────────
# Route Analysis
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_ROUTE_ANALYSIS = settings.ENABLE_ROUTE_ANALYSIS
ROUTE_ANALYSIS_INTERVAL = settings.ROUTE_ANALYSIS_INTERVAL
ROUTE_HISTORY_SIZE = settings.ROUTE_HISTORY_SIZE
HOP_TIMEOUT_THRESHOLD = settings.HOP_TIMEOUT_THRESHOLD
ROUTE_CHANGE_CONSECUTIVE = settings.ROUTE_CHANGE_CONSECUTIVE
ROUTE_CHANGE_HOP_DIFF = settings.ROUTE_CHANGE_HOP_DIFF
ROUTE_IGNORE_FIRST_HOPS = settings.ROUTE_IGNORE_FIRST_HOPS
ROUTE_SAVE_ON_CHANGE_CONSECUTIVE = settings.ROUTE_SAVE_ON_CHANGE_CONSECUTIVE

# ─────────────────────────────────────────────────────────────────────────────
# Visual Alerts
# ─────────────────────────────────────────────────────────────────────────────

SHOW_VISUAL_ALERTS = settings.SHOW_VISUAL_ALERTS
ALERT_DISPLAY_TIME = settings.ALERT_DISPLAY_TIME
ALERT_PANEL_LINES = settings.ALERT_PANEL_LINES
MAX_ACTIVE_ALERTS = settings.MAX_ACTIVE_ALERTS

# ─────────────────────────────────────────────────────────────────────────────
# Resource Limits and Safety Settings
# ─────────────────────────────────────────────────────────────────────────────

MAX_WORKER_THREADS = settings.MAX_WORKER_THREADS
MAX_EXECUTOR_QUEUE_SIZE = settings.MAX_EXECUTOR_QUEUE_SIZE
MAX_MEMORY_MB = settings.MAX_MEMORY_MB
ENABLE_MEMORY_MONITORING = settings.ENABLE_MEMORY_MONITORING
MAX_ALERTS_HISTORY = settings.MAX_ALERTS_HISTORY
MAX_TRACEROUTE_FILES = settings.MAX_TRACEROUTE_FILES
MAX_PROBLEM_HISTORY = settings.MAX_PROBLEM_HISTORY
MAX_ROUTE_HISTORY = settings.MAX_ROUTE_HISTORY
MAX_DNS_BENCHMARK_HISTORY = settings.MAX_DNS_BENCHMARK_HISTORY
PING_BURST_LIMIT = settings.PING_BURST_LIMIT
DNS_CHECK_COOLDOWN = settings.DNS_CHECK_COOLDOWN
TRACEROUTE_MIN_INTERVAL = settings.TRACEROUTE_MIN_INTERVAL
SHUTDOWN_TIMEOUT_SECONDS = settings.SHUTDOWN_TIMEOUT_SECONDS
FORCE_KILL_TIMEOUT = settings.FORCE_KILL_TIMEOUT

# ─────────────────────────────────────────────────────────────────────────────
# Single Instance
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_SINGLE_INSTANCE = settings.ENABLE_SINGLE_INSTANCE
ENABLE_STALE_LOCK_CHECK = settings.ENABLE_STALE_LOCK_CHECK

# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_METRICS = settings.ENABLE_METRICS
ENABLE_VERSION_CHECK = settings.ENABLE_VERSION_CHECK
VERSION_CHECK_INTERVAL = settings.VERSION_CHECK_INTERVAL
METRICS_ADDR = settings.METRICS_ADDR
METRICS_PORT = settings.METRICS_PORT

# ─────────────────────────────────────────────────────────────────────────────
# Health Endpoint
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_HEALTH_ENDPOINT = settings.ENABLE_HEALTH_ENDPOINT
HEALTH_ADDR = settings.HEALTH_ADDR
HEALTH_PORT = settings.HEALTH_PORT
HEALTH_AUTH_USER = settings.HEALTH_AUTH_USER
HEALTH_AUTH_PASS = settings.HEALTH_AUTH_PASS
HEALTH_TOKEN = settings.HEALTH_TOKEN
HEALTH_TOKEN_HEADER = settings.HEALTH_TOKEN_HEADER

# ─────────────────────────────────────────────────────────────────────────────
# UI Layout
# ─────────────────────────────────────────────────────────────────────────────

UI_COMPACT_THRESHOLD = settings.UI_COMPACT_THRESHOLD
UI_WIDE_THRESHOLD = settings.UI_WIDE_THRESHOLD
UI_THEME = settings.UI_THEME

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

LOG_DIR = settings.LOG_DIR
LOG_FILE = settings.LOG_FILE
LOG_LEVEL = settings.LOG_LEVEL
LOG_TRUNCATE_ON_START = settings.LOG_TRUNCATE_ON_START
