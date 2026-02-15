import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application configuration settings using Pydantic Settings.
    Reads from environment variables and provides type safety and validation.
    """
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Version
    # ─────────────────────────────────────────────────────────────────────────────
    VERSION: str = "2.4.3.0136"
    # Also update:
    # - charts/pinger/Chart.yaml (appVersion)
    # - pyproject.toml (version)

    # ─────────────────────────────────────────────────────────────────────────────
    # Language Detection
    # ─────────────────────────────────────────────────────────────────────────────
    # Note: CURRENT_LANGUAGE logic remains in settings.py or logic for now as it involves complex detection
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Core Settings
    # ─────────────────────────────────────────────────────────────────────────────
    TARGET_IP: str = Field(default="1.1.1.1", description="Target IP address to ping")
    INTERVAL: float = Field(default=1.0, ge=0.1, description="Ping interval in seconds")
    WINDOW_SIZE: int = Field(default=1800, gt=0)
    LATENCY_WINDOW: int = Field(default=600, gt=0)

    # ─────────────────────────────────────────────────────────────────────────────
    # Alert Settings
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_SOUND_ALERTS: bool = True
    ALERT_COOLDOWN: int = Field(default=5, ge=0)
    ALERT_ON_PACKET_LOSS: bool = True
    ALERT_ON_HIGH_LATENCY: bool = True
    HIGH_LATENCY_THRESHOLD: float = Field(default=100.0, gt=0)

    # ─────────────────────────────────────────────────────────────────────────────
    # Threshold Settings
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_THRESHOLD_ALERTS: bool = True
    PACKET_LOSS_THRESHOLD: float = Field(default=5.0, ge=0.0, le=100.0)
    AVG_LATENCY_THRESHOLD: float = Field(default=100.0, gt=0)
    CONSECUTIVE_LOSS_THRESHOLD: int = Field(default=5, ge=1)
    JITTER_THRESHOLD: float = Field(default=30.0, ge=0)

    # ─────────────────────────────────────────────────────────────────────────────
    # Smart Alert System
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_SMART_ALERTS: bool = True
    
    # Alert Deduplication
    ENABLE_ALERT_DEDUPLICATION: bool = True
    ALERT_DEDUP_WINDOW_SECONDS: int = Field(default=300, ge=0)
    ALERT_SIMILARITY_THRESHOLD: float = Field(default=0.85, ge=0.0, le=1.0)
    
    # Alert Grouping
    ENABLE_ALERT_GROUPING: bool = True
    ALERT_GROUP_WINDOW_SECONDS: int = Field(default=600, ge=0)
    ALERT_GROUP_MAX_SIZE: int = Field(default=20, ge=1)
    
    # Dynamic Prioritization
    ENABLE_DYNAMIC_PRIORITY: bool = True
    PRIORITY_BUSINESS_IMPACT_WEIGHT: float = Field(default=0.4, ge=0.0, le=1.0)
    PRIORITY_USER_IMPACT_WEIGHT: float = Field(default=0.3, ge=0.0, le=1.0)
    PRIORITY_SERVICE_CRITICALITY_WEIGHT: float = Field(default=0.2, ge=0.0, le=1.0)
    PRIORITY_TIME_WEIGHT: float = Field(default=0.1, ge=0.0, le=1.0)
    ALERT_ESCALATION_TIME_MINUTES: int = Field(default=30, ge=0)
    
    # Adaptive Thresholds
    ENABLE_ADAPTIVE_THRESHOLDS: bool = True
    ADAPTIVE_BASELINE_WINDOW_HOURS: int = Field(default=24, ge=1)
    ADAPTIVE_UPDATE_INTERVAL_MINUTES: int = Field(default=60, ge=1)
    ADAPTIVE_ANOMALY_SIGMA: float = Field(default=2.0, gt=0)
    
    # Noise Reduction
    ENABLE_NOISE_REDUCTION: bool = True
    ALERT_RATE_LIMIT_PER_MINUTE: int = Field(default=10, ge=1)
    ALERT_BURST_LIMIT: int = Field(default=5, ge=1)
    
    # Alert History
    ALERT_HISTORY_SIZE: int = Field(default=500, ge=1)
    ALERT_HISTORY_RETENTION_HOURS: int = Field(default=48, ge=1)

    # ─────────────────────────────────────────────────────────────────────────────
    # IP Change Detection
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_IP_CHANGE_ALERT: bool = True
    IP_CHECK_INTERVAL: int = Field(default=15, ge=1)
    IP_CHANGE_SOUND: bool = True
    LOG_IP_CHANGES: bool = True

    # ─────────────────────────────────────────────────────────────────────────────
    # DNS Monitoring
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_DNS_MONITORING: bool = True
    DNS_TEST_DOMAIN: str = "cloudflare.com"
    DNS_CHECK_INTERVAL: int = Field(default=10, ge=1)
    DNS_SLOW_THRESHOLD: float = Field(default=100.0, gt=0)
    DNS_RECORD_TYPES: List[str] = ["A", "AAAA", "CNAME", "MX", "TXT", "NS"]
    
    # DNS Benchmark
    ENABLE_DNS_BENCHMARK: bool = True
    DNS_BENCHMARK_DOTCOM_DOMAIN: str = "cloudflare.com"
    DNS_BENCHMARK_SERVERS: List[str] = ["system"]
    DNS_BENCHMARK_HISTORY_SIZE: int = Field(default=50, ge=1)

    # ─────────────────────────────────────────────────────────────────────────────
    # Traceroute Settings
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_AUTO_TRACEROUTE: bool = False
    TRACEROUTE_TRIGGER_LOSSES: int = Field(default=3, ge=1)
    TRACEROUTE_COOLDOWN: int = Field(default=300, ge=0)
    TRACEROUTE_MAX_HOPS: int = Field(default=15, ge=1)

    # ─────────────────────────────────────────────────────────────────────────────
    # MTU Monitoring
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_MTU_MONITORING: bool = True
    MTU_CHECK_INTERVAL: int = Field(default=30, ge=1)
    ENABLE_PATH_MTU_DISCOVERY: bool = True
    PATH_MTU_CHECK_INTERVAL: int = Field(default=120, ge=1)
    DEFAULT_MTU: int = Field(default=1500, gt=0)
    MTU_ISSUE_CONSECUTIVE: int = Field(default=3, ge=1)
    MTU_CLEAR_CONSECUTIVE: int = Field(default=2, ge=1)
    MTU_DIFF_THRESHOLD: int = Field(default=50, ge=0)

    # ─────────────────────────────────────────────────────────────────────────────
    # TTL Monitoring
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_TTL_MONITORING: bool = True
    TTL_CHECK_INTERVAL: int = Field(default=10, ge=1)

    # ─────────────────────────────────────────────────────────────────────────────
    # Hop Monitoring
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_HOP_MONITORING: bool = True
    HOP_PING_INTERVAL: float = Field(default=1.0, gt=0)
    HOP_PING_TIMEOUT: float = Field(default=0.5, gt=0)
    HOP_REDISCOVER_INTERVAL: int = Field(default=3600, ge=1)
    HOP_LATENCY_GOOD: float = Field(default=50.0, gt=0)
    HOP_LATENCY_WARN: float = Field(default=100.0, gt=0)

    # ─────────────────────────────────────────────────────────────────────────────
    # Problem Analysis
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_PROBLEM_ANALYSIS: bool = True
    PROBLEM_ANALYSIS_INTERVAL: int = Field(default=60, ge=1)
    PROBLEM_HISTORY_SIZE: int = Field(default=100, ge=1)
    PREDICTION_WINDOW: int = Field(default=300, ge=1)
    PROBLEM_LOG_SUPPRESSION_SECONDS: int = Field(default=6000, ge=0)
    ROUTE_LOG_SUPPRESSION_SECONDS: int = Field(default=6000, ge=0)

    # ─────────────────────────────────────────────────────────────────────────────
    # Route Analysis
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_ROUTE_ANALYSIS: bool = True
    ROUTE_ANALYSIS_INTERVAL: int = Field(default=1800, ge=1)
    ROUTE_HISTORY_SIZE: int = Field(default=10, ge=1)
    HOP_TIMEOUT_THRESHOLD: float = Field(default=3000.0, gt=0)
    ROUTE_CHANGE_CONSECUTIVE: int = Field(default=2, ge=1)
    ROUTE_CHANGE_HOP_DIFF: int = Field(default=2, ge=1)
    ROUTE_IGNORE_FIRST_HOPS: int = Field(default=2, ge=0)
    ROUTE_SAVE_ON_CHANGE_CONSECUTIVE: int = Field(default=2, ge=1)

    # ─────────────────────────────────────────────────────────────────────────────
    # Visual Alerts
    # ─────────────────────────────────────────────────────────────────────────────
    SHOW_VISUAL_ALERTS: bool = True
    ALERT_DISPLAY_TIME: int = Field(default=10, ge=0)
    ALERT_PANEL_LINES: int = Field(default=3, ge=1)
    MAX_ACTIVE_ALERTS: int = Field(default=3, ge=1)

    # ─────────────────────────────────────────────────────────────────────────────
    # Resource Limits
    # ─────────────────────────────────────────────────────────────────────────────
    MAX_WORKER_THREADS: int = Field(default=4, ge=1)
    MAX_EXECUTOR_QUEUE_SIZE: int = Field(default=100, ge=1)
    MAX_MEMORY_MB: int = Field(default=500, ge=10)
    ENABLE_MEMORY_MONITORING: bool = True
    
    MAX_ALERTS_HISTORY: int = Field(default=100, ge=1)
    MAX_TRACEROUTE_FILES: int = Field(default=100, ge=1)
    MAX_PROBLEM_HISTORY: int = Field(default=50, ge=1)
    MAX_ROUTE_HISTORY: int = Field(default=20, ge=1)
    MAX_DNS_BENCHMARK_HISTORY: int = Field(default=100, ge=1)
    
    PING_BURST_LIMIT: int = Field(default=10, ge=1)
    DNS_CHECK_COOLDOWN: int = Field(default=5, ge=0)
    TRACEROUTE_MIN_INTERVAL: int = Field(default=60, ge=0)
    
    SHUTDOWN_TIMEOUT_SECONDS: int = Field(default=10, ge=0)
    FORCE_KILL_TIMEOUT: int = Field(default=5, ge=0)

    # ─────────────────────────────────────────────────────────────────────────────
    # Single Instance
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_SINGLE_INSTANCE: bool = True
    ENABLE_STALE_LOCK_CHECK: bool = True

    # ─────────────────────────────────────────────────────────────────────────────
    # Metrics
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_METRICS: bool = True
    ENABLE_VERSION_CHECK: bool = True
    VERSION_CHECK_INTERVAL: int = Field(default=3600, ge=1)
    METRICS_ADDR: str = "127.0.0.1"
    METRICS_PORT: int = Field(default=8000, ge=1, le=65535)

    # ─────────────────────────────────────────────────────────────────────────────
    # Health Endpoint
    # ─────────────────────────────────────────────────────────────────────────────
    ENABLE_HEALTH_ENDPOINT: bool = True
    HEALTH_ADDR: str = "127.0.0.1"
    HEALTH_PORT: int = Field(default=8001, ge=1, le=65535)
    HEALTH_AUTH_USER: Optional[str] = ""
    HEALTH_AUTH_PASS: Optional[str] = ""
    HEALTH_TOKEN: Optional[str] = ""
    HEALTH_TOKEN_HEADER: str = "X-Health-Token"

    # ─────────────────────────────────────────────────────────────────────────────
    # UI Layout
    # ─────────────────────────────────────────────────────────────────────────────
    UI_COMPACT_THRESHOLD: int = Field(default=110, ge=10)
    UI_WIDE_THRESHOLD: int = Field(default=170, ge=10)

    # ─────────────────────────────────────────────────────────────────────────────
    # Logging
    # ─────────────────────────────────────────────────────────────────────────────
    LOG_DIR: str = Field(default=os.path.expanduser("~/.pinger"))
    LOG_FILE: str = Field(default_factory=lambda: os.path.join(os.path.expanduser("~/.pinger"), "ping_monitor.log"))
    LOG_LEVEL: str = "INFO"
    LOG_TRUNCATE_ON_START: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
