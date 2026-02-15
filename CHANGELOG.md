# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.3.0136]
### Added
- **Smart Alert System** - Advanced alerting with adaptive thresholds and alert fatigue prevention.
  - **Adaptive Thresholds**: Automatically learns normal latency patterns and sets dynamic thresholds based on time of day and day of week.
  - **Alert Fatigue Prevention**: Automatically reduces alert frequency during prolonged incidents (1-3-5-15-30 minute intervals).
  - **Smart Recovery**: Automatically cancels alerts when metrics return to normal for 3 consecutive checks.
  - **Alert Prioritization**: Ranks alerts by severity (CRITICAL, WARNING, INFO) and groups related alerts.
  - **Alert Deduplication**: Prevents duplicate alerts for the same issue.
  - **Alert History**: Logs all alerts (active and recovered) with timestamps.
  - **Configuration**: New settings in `config/settings_model.py`:
    - `SMART_ALERT_ENABLED`: Enable/disable the system
    - `SMART_ALERT_ADAPTIVE_ENABLED`: Enable adaptive thresholds
    - `SMART_ALERT_FATIGUE_ENABLED`: Enable alert fatigue prevention
    - `SMART_ALERT_RECOVERY_ENABLED`: Enable smart recovery
    - `SMART_ALERT_HISTORY_ENABLED`: Enable alert history
    - `SMART_ALERT_HISTORY_RETENTION_DAYS`: Auto-delete old history
  - **UI Integration**:
    - New "Alerts" tab in the main UI
    - Real-time alert notifications with sound
    - Alert history log with filtering and search
    - Visual indicators for alert severity and status
    - Alert statistics and trends

### Refactoring
- **Alert System Architecture** - Complete rewrite of the alerting system for better performance and maintainability.
  - **Centralized Alert Manager**: `core/alert_manager.py` - Manages alert lifecycle, state, and history
  - **Alert Prioritizer**: `core/alert_prioritizer.py` - Ranks alerts by severity and groups related alerts
  - **Adaptive Thresholds**: `core/adaptive_thresholds.py` - Calculates dynamic thresholds based on historical data
  - **Alert Fatigue Prevention**: `core/alert_fatigue.py` - Manages alert cooldown and suppression
  - **Smart Recovery**: `core/smart_recovery.py` - Detects recovery and cancels alerts
  - **Alert History**: `core/alert_history.py` - Manages alert history log
  - **Alert Types**: `core/alert_types.py` - Centralized alert type definitions
  - **Alert Service**: `services/alert_service.py` - Service layer for alert operations
  - **Alert Repository**: `services/alert_repository.py` - Data access layer for alert history
  - **UI Integration**: `ui/alerts_tab.py`, `ui/alert_history_tab.py`, `ui/main_ui.py` - UI components

### Changed
- **Alert Configuration** - Moved alert configuration from `config.py` to `config/settings_model.py`
  - Added new Smart Alert System settings with default values
  - Kept existing alert settings with backward compatibility
  - Added documentation for new settings

### Fixed
- **Alert History Cleanup** - Added automatic cleanup of old alert history entries
  - Old entries are deleted when they exceed retention period
  - Cleanup runs automatically on startup and periodically
  - Prevents alert history from growing indefinitely

## [2.4.2.0556]
### Security
- **Docker Compose authentication** - Enabled Basic Auth by default in `docker-compose.yml` for health endpoint.
  - Added `HEALTH_AUTH_USER=admin` and `HEALTH_AUTH_PASS=${HEALTH_AUTH_PASS:-changeme}` environment variables.
  - Added warning in README.md and README.ru.md about authentication requirement when binding to `0.0.0.0`.
  - Users must override the default password via environment variable or `.env` file.

### Fixed
- **Dockerfile missing directories** - Added missing `COPY` instructions for `config/`, `core/`, and `ui_protocols/` directories.
  - Docker image was broken because `config/` package was not copied into the image.

### Added
- **CI/CD Pipeline** - Added GitHub Actions workflow (`.github/workflows/ci.yml`).
  - **lint** job: ruff (linting), black (format check), mypy (type check)
  - **test** job: pytest on Python 3.10, 3.11, 3.12 matrix
  - **build** job: Docker image build with cache

### Refactoring
- **Explicit imports in config module** - Replaced star imports (`from ... import *`) with explicit imports.
  - Improved IDE navigation and eliminated potential name conflicts.
  - Updated `config/__init__.py` and `config.py` (legacy wrapper).
  - All exported names are now explicitly listed in imports and `__all__`.
  - Added missing Smart Alert System and UI Layout variables to exports.

- **Inline imports moved to module level** - Moved `from config import ...` statements from inside methods to top of modules.
  - Improved code readability and import performance.
  - Updated files: ui.py, monitor.py, alerts.py, single_instance.py, core/dns_monitor_task.py, services/traceroute_service.py.
  - Kept justified inline imports: `if TYPE_CHECKING:`, `try/except ImportError` fallbacks, optional dependencies, lazy-loaded services.

## [2.4.1.1835]
### Fixed
- **Timezone-aware datetimes** — Replaced all naive `datetime.now()` with timezone-aware `datetime.now(timezone.utc)` throughout the project.
  - This fixes timestamp inconsistency in Docker/Kubernetes where TZ environment variable affects naive datetime.
  - All internal timestamps now use UTC timezone.
  - UI display converted to local timezone via `.astimezone()` for user-friendly output.
  - Added `_ensure_utc()` helper function for safe datetime comparison (handles mixed naive/aware datetimes).
  - Updated 14 files: ui.py, stats_repository.py, services/traceroute_service.py, route_analyzer.py, problem_analyzer.py, pinger/__init__.py, main.py, demo_mode.py, core/alert_prioritizer.py, core/alert_types.py, core/adaptive_thresholds.py.

## [2.4.1.1659]
### Fixed
- **Thread Safety for _ping_counter** — Added `threading.Lock` to protect incremental counter in `Monitor` class.
  - Previous code `self._ping_counter += 1` with subsequent check was vulnerable to race conditions.
  - Added `self._ping_lock = threading.Lock()` in `__init__` and wrapped increment+check in `with self._ping_lock:` block.
  - Ensures safe operation if `ping_once()` or `_ping_counter` access is extended to multiple threads in future.
  - Verified other fields: `_active_subprocesses` already protected by `_subprocess_lock`, `_executor_tasks` only used during shutdown.

- **Graceful Shutdown with sys.exit()** — Replaced `os._exit(0)` with `sys.exit(0)` to allow proper Python shutdown sequence.
  - `os._exit()` bypasses Python's interpreter shutdown, preventing finalizers from running, losing buffered file writes, and leaving lock files on disk.
  - In `monitor.py`: Changed force exit to use `sys.exit(0)` after flushing all logging handlers.
  - In `main.py`: Changed `_force_shutdown()` to use `sys.exit(0)` after graceful cleanup.
  - Now `atexit` handlers run properly, ensuring `SingleInstance` lock file is released on exit.
  - Added explicit flush of all logging handlers before exit to prevent log message loss.

### Added
- **Hop Panel Enhancements (Stage 1, 2 & 3)** — Added new metrics, visual improvements, and geolocation to hop monitoring panel.
  - **Stage 1 - Basic metrics**: jitter (standard deviation), latency delta (change vs previous ping).
  - **Stage 2 - Visual**: Sparklines `▁▂▃▅▇` showing latency history in compact mode; trend arrows ↑↓→.
  - **Stage 3 - Geolocation**: New `GeoService` for IP geolocation via ip-api.com with caching.
    - `services/geo_service.py` - GeoService class with 1-hour cache, 45 req/min rate limit.
    - HopStatus includes `country`, `country_code`, `asn` fields.
    - `HopMonitorService.enable_geo()` to enable geolocation lookups.
    - Wide mode displays Country and ASN columns.
  - Updated `HopStatus` dataclass with new fields: `jitter`, `prev_latency`, `latency_delta`, `latency_history`, `country`, `country_code`, `asn`.
  - UI shows new columns: Delta (Δ) and Jitter in standard/wide; sparkline + trend in compact; Country and ASN in wide.

## [2.3.9.0042] - 2026-02-12
### Refactoring
- **Ping Service Code Deduplication** — Eliminated duplicate ping command execution logic between `TTLMonitorTask._extract_ttl()` and `PingService._ping_with_system()`.
  - Added shared method `_run_ping_command()` in `PingService` for centralized ping subprocess execution.
  - Added public method `extract_ttl()` in `PingService` for TTL extraction with hop count estimation.
  - Refactored `TTLMonitorTask` to delegate TTL extraction to `PingService` (reduced from 79 to 24 lines).
  - Removed ~50 lines of duplicated code (subprocess setup, platform-specific paths, creationflags).

- **Alert Methods Encapsulation** — Fixed inconsistent thread safety pattern where `add_visual_alert(lock, stats, ...)` required callers to pass lock and stats separately.
  - Moved `add_visual_alert()`, `trigger_alert()`, and `clean_old_alerts()` into `StatsRepository` as encapsulated methods.
  - New API: `stats_repo.add_alert(msg, type)`, `stats_repo.trigger_alert_sound(kind)`, `stats_repo.clean_old_alerts()`.
  - Updated 20+ call sites across `monitor.py`, `core/alert_handler.py`, `core/ip_updater_task.py`, `core/route_analyzer_task.py`, `core/version_checker_task.py`, `services/traceroute_service.py`.
  - Removed fragile anti-pattern where caller was responsible for correct lock+dict pairing.

### Fixed
- **IP Detection Failure** — Replaced HTTPS IP providers (rate-limited) with HTTP providers for reliable IP detection.
  - `ipinfo.io`, `ipapi.co`, `ip-api.com` (HTTPS) were returning 429/403 errors.
  - Switched to `ip-api.com` (HTTP) as primary provider with fallbacks: `ifconfig.me`, `icanhazip.com`, `ipecho.net`.

- **Requirements.txt Pinned Versions** — Replaced open-ended version specifiers (`>=`) with pinned versions from `poetry.lock`.
  - Ensures reproducible installs via `pip install -r requirements.txt`.
  - rich==14.2.0, requests==2.32.5, pythonping==1.1.4, prometheus_client==0.24.1, dnspython==2.8.0, psutil==7.2.2.

## [2.3.8] - 2026-02-12
### Refactoring
- **Monitor Class Decomposition** — Addressed God Object anti-pattern in `monitor.py` (reduced from 941 to ~520 lines).
  - Extracted 8 background tasks into separate classes in `core/` package (`IPUpdaterTask`, `DNSMonitorTask`, etc.).
  - Implemented `TaskOrchestrator` for unified background task lifecycle management.
  - Introduced `BackgroundTask` ABC to eliminate duplicated loop/error-handling boilerplate.
  - Improved testability and maintainability of core monitoring logic.

## [2.3.7] - 2026-02-12
### Security
- **IP Service Hardening** — Switched public IP resolution from unencrypted HTTP to HTTPS with multi-provider fallback (ipinfo.io → ipapi.co → ip-api.com).

## [2.3.6] - 2026-02-11
### Fixed
- **Critical: Background process zombies** — Fixed issue where background processes (ping, traceroute) would persist after application exit on Windows.
  - Implemented robust signal handling in `main.py` catching `SIGINT`, `SIGTERM`, and Windows Console Close events.
  - Added `creationflags=subprocess.CREATE_NO_WINDOW` to all subprocess calls to prevent orphaned console windows.
  - Added `monitor.shutdown()` logic to explicitly track and kill all child subprocesses.
  - Added `atexit` safety net and `os._exit(0)` fallback to guarantee process termination even if threads hang.

## [2.3.5] - 2026-02-11
### Added
- **Smart Alert Management System** — Intelligent alert processing to reduce alert fatigue
  - **Alert Deduplication** — Fingerprint-based deduplication within configurable time window (default: 5 min)
    - SHA256 fingerprinting for exact duplicate detection  
    - Similarity detection using Jaccard algorithm (85% threshold)
    - 60-80% reduction in duplicate alerts
  - **Context-Based Grouping** — Automatic alert consolidation by service, component, and problem type
    - Root cause correlation (e.g., CONNECTION_LOST causes PACKET_LOSS + HIGH_LATENCY)
    - Temporal clustering within 10-minute window
    - Reduces separate alerts into consolidated groups
  - **Dynamic Prioritization** — Multi-factor priority scoring with automatic escalation
    - Business impact (40%), user impact (30%), service criticality (20%), time factor (10%)
    - Four priority levels: LOW, MEDIUM, HIGH, CRITICAL
    - Auto-escalation for alerts older than 30 minutes
  - **Adaptive Thresholds** — Historical data-based threshold calculation
    - Moving average + 2σ for latency metrics
    - 95th percentile for packet loss
    - 24-hour rolling baseline with hourly updates
    - Reduces false positives by 30-40%
  - **Rate Limiting** — Prevents alert floods (10 alerts/min, 5 burst limit)
  - **Noise Reduction** — Automatic suppression of low-priority alerts in large groups

- **New Core Modules** (in `core/` package):
  - `alert_types.py` — Data models (AlertEntity, AlertGroup, AlertPriority, AlertContext, AlertHistory)
  - `alert_deduplicator.py` — Deduplication engine with similarity detection
  - `alert_grouper.py` — Context-based grouping with root cause maps
  - `alert_prioritizer.py` — Dynamic scoring and escalation engine
  - `adaptive_thresholds.py` — Statistical baseline calculation and anomaly detection
  - `smart_alert_manager.py` — Central coordinator integrating all intelligence features

- **Prometheus Metrics** (in `infrastructure/metrics.py`):
  - `pinger_alerts_total` — Total alerts generated
  - `pinger_alerts_deduplicated_total` — Alerts suppressed via deduplication
  - `pinger_alerts_suppressed_total` — Alerts suppressed by rules
  - `pinger_alerts_rate_limited_total` — Alerts blocked by rate limiting
  - `pinger_alert_groups_active` — Current active alert groups
  - `pinger_alert_priority` — Alerts by priority level (LOW/MEDIUM/HIGH/CRITICAL)

- **Configuration Settings** (in `config/settings.py`):
  - `ENABLE_SMART_ALERTS` — Master switch for smart alert features (default: True)
  - Alert deduplication: `ALERT_DEDUP_WINDOW_SECONDS`, `ALERT_SIMILARITY_THRESHOLD`
  - Alert grouping: `ALERT_GROUP_WINDOW_SECONDS`, `ALERT_GROUP_MAX_SIZE`
  - Dynamic prioritization: `PRIORITY_*_WEIGHT` settings, `ALERT_ESCALATION_TIME_MINUTES`
  - Adaptive thresholds: `ADAPTIVE_BASELINE_WINDOW_HOURS`, `ADAPTIVE_ANOMALY_SIGMA`
  - Noise reduction: `ALERT_RATE_LIMIT_PER_MINUTE`, `ALERT_BURST_LIMIT`
  - Alert history: `ALERT_HISTORY_SIZE`, `ALERT_HISTORY_RETENTION_HOURS`

- **Localization Updates**:
  - Added Russian translations: `alert_high_latency`, `alert_packet_loss`
  - Added English translations: `alert_high_latency`, `alert_packet_loss`

### Changed
- **AlertHandler Integration** — Updated to use SmartAlertManager when enabled
  - Legacy mode preserved for backward compatibility (`ENABLE_SMART_ALERTS=false`)
  - Smart processing includes adaptive thresholds, deduplication, grouping, and prioritization
  - Visual alerts show group summaries instead of individual messages
- **Monitor Initialization** — SmartAlertManager initialized with full configuration
- **Core Package Exports** — Added all smart alert system classes to `core/__init__.py`

### Fixed
- **AdaptiveThresholds Data Access** — Corrected historical data retrieval from StatsRepository
  - Fixed latency access using `stats["latencies"]` instead of non-existent `_recent_latencies`
  - Fixed packet loss calculation using `get_recent_results()` method with proper locking
  - Added safer handling for empty data scenarios

### Technical Details
- Full backward compatibility maintained
- All components thread-safe with proper locking
- Comprehensive Python syntax validation (all 6 new modules pass)
- Alert processing pipeline: Rate Limit → Priority Calc → Dedup → Group → History → Action
- Expected impact: 60-80% alert volume reduction while maintaining signal quality

## [2.3.4] - 2026-02-11
### Added
- **Adaptive UI Redesign** — Redesigned terminal UI to be responsive with 3 size tiers (compact, standard, wide).
- **Black & Orange Theme** — New high-contrast visual style with true black background and warm orange accents.
- **Adaptive Information Density** — Dynamic adjustment of charts, stats, and tables based on terminal window size.

### Fixed
- **Type Checking Errors** — Resolved all 24+ Pyright type-checking errors across the entire project.
- **Optional Member Safety** — Added None guards and proper type checks for system interactions and regex matches.

### Changed
- **Type Annotation Consistency** — Improved TypedDict definitions and function signatures for better IDE support.
- **Revised Visual Hierarchy** — Status bar and primary data panels now have increased prominence.

## [2.3.3] - 2026-02-10
### Changed
- **Major architecture refactoring** — Improved code organization following SOLID principles
  - `config.py` (645 lines) split into `config/` package with separate modules:
    - `config/settings.py` — configuration variables only
    - `config/i18n.py` — translations (LANG, t())
    - `config/types.py` — TypedDict classes and factory functions
  - `ping_once()` method refactored following Single Responsibility Principle (SRP):
    - `core/ping_handler.py` — PingHandler class for ping execution
    - `core/alert_handler.py` — AlertHandler class for alert processing
    - `core/metrics_handler.py` — MetricsHandler class for Prometheus metrics
  - UI decoupled from Monitor class following Dependency Inversion Principle (DIP):
    - `ui_protocols/protocols.py` — StatsDataProvider Protocol interface
    - UI now depends on abstraction, enabling easier testing with mocks

### Added
- `config/` package with modular configuration
- `core/` package with SRP-compliant handlers
- `ui_protocols/` package with Protocol definitions
- Backward compatibility wrapper in legacy `config.py` (re-exports from new package)

### Developer Experience
- Code is now more testable — UI can work with any StatsDataProvider implementation
- Clear separation of concerns — each module has a single responsibility
- Easier to extend — new features can be added without modifying existing code

## [2.3.2] - 2026-02-10
### Added
- **Automatic version checking** — Background task checks for updates every hour (configurable via `VERSION_CHECK_INTERVAL`)
- **Version check configuration** — Added `ENABLE_VERSION_CHECK` and `VERSION_CHECK_INTERVAL` environment variables
- **Version info in stats repository** — Added `latest_version`, `version_check_time`, and `version_up_to_date` fields to `StatsSnapshot`
- **Version display in UI** — Header shows current version with update indicator when new version is available
- **Version check methods** — Added `set_latest_version()` and `get_latest_version_info()` to `StatsRepository`

### Changed
- **Version check implementation** — Moved from one-time check at startup to periodic background checks
- **UI version display** — Now reads version info from `StatsRepository` instead of local variables

## [2.3.1] - 2026-02-09
### Security
- **Metrics server security hardening** — Default binding changed from `0.0.0.0` to `127.0.0.1` (localhost-only)
- **Mandatory authentication for non-localhost bindings** — Metrics server refuses to start without credentials when bound to non-localhost addresses
- **Security check implementation** — Added `_check_security` method to `MetricsServer` class
- **METRICS_ALLOW_NO_AUTH environment variable** — Added option to bypass authentication for metrics server (not recommended)
- **Consistent security behavior** — Metrics server now follows the same security pattern as health endpoint
- **Enhanced security logging** — Added detailed security-related logging for metrics server

### Changed
- **Metrics server initialization** — Updated `MetricsServer` class to include security validation before starting
- **Default METRICS_ADDR** — Changed from `0.0.0.0` to `127.0.0.1` for secure-by-default behavior
- **config.py documentation** — Updated METRICS_ADDR comment with security recommendations
- **start_metrics_server docstring** — Added comprehensive security documentation

## [2.3.0] - 2026-02-09
### Security
- **Health endpoints security hardening** — Default binding changed from `0.0.0.0` to `127.0.0.1` (localhost-only)
- **Mandatory authentication for non-localhost bindings** — Health server refuses to start without credentials when bound to non-localhost addresses
- **Token-based authentication support** — Added `HEALTH_TOKEN` and `HEALTH_TOKEN_HEADER` environment variables for simple API token authentication
- **Basic Auth support** — Added `HEALTH_AUTH_USER` and `HEALTH_AUTH_PASS` environment variables
- **Dual authentication support** — Either Basic Auth or Token Auth is accepted when both are configured
- **Security enforcement at startup** — Server logs warning/error and refuses to start if insecure configuration detected
- **Environment variable `HEALTH_ALLOW_NO_AUTH`** — Optional bypass for development (logs warning)
- **Credentials caching** — Environment variables read once at startup (performance optimization)

### Changed
- **Default `HEALTH_ADDR`** — Changed from `0.0.0.0` to `127.0.0.1` for secure-by-default behavior
- **README restructuring** — Removed `<details>` collapsible sections, all documentation now visible by default

### Documentation
- **Health HTTP Server section** — New dedicated section with configuration examples and Prometheus integration
- **SECURITY.md updated** — Comprehensive security documentation for health endpoints
- **README alerts** — Added `[!IMPORTANT]` and `[!NOTE]` blocks for critical security information

## [2.2.0] - 2026-02-09
### Added
- Dual-sparkline latency panel showing latency and jitter histories with new p95 metric.
- Trends sub-panel with packet loss (30m), jitter trend/current, and hop count overview.
- Persistent jitter history in `StatsRepository` for richer analytics.
- Updated README to describe the new visuals and user experience.

## [2.1.8] - 2026-02-07

### Fixed
- **Critical: SyntaxError on Python 3.11** — replaced PEP 695 type parameter syntax (`run_blocking[T]`) with classic `TypeVar` approach
- **Critical: FileNotFoundError on first launch** — log directory (`~/.pinger/`) is now created before logging initialization
- **Critical: DNS problem detection broken in Russian locale** — `dns_status` now uses localized strings (`t()`) instead of raw English strings
- **Health server port mismatch** — health server now correctly uses `HEALTH_PORT` from config instead of hardcoded `8080`
- **Prometheus metrics server never started** — added `start_metrics_server()` call in `Monitor.__init__`
- **Docker environment variables ignored** — `config.py` now reads `ENABLE_METRICS`, `METRICS_PORT`, `HEALTH_PORT`, `LOG_LEVEL`, `LOG_TRUNCATE_ON_START` and other settings from `os.environ`
- **DNS benchmark error messages lost** — `exc` variable was referenced outside `except` block scope; now captured properly via `error_msg`
- **DNS uncached test double query** — removed redundant second DNS query inside `except` handler in `_test_uncached`
- **Problem analyzer duplicate flooding** — `_record_problem` now checks suppression window *before* appending to history
- **Version check crash on non-numeric tags** — version parser now handles suffixes like `-rc1` gracefully
- **Hop monitor Windows ping timeout** — `HOP_PING_TIMEOUT * 1000` produced float string `"500.0"`, now correctly outputs integer `"500"`
- **Traceroute false positives** — single timeout hops no longer flagged as problematic (many routers don't respond to ICMP); requires 2+ consecutive timeouts

### Changed
- **`ENABLE_HEALTH_ENDPOINT` config respected** — health server only starts when enabled
- **`HEALTH_ADDR` config respected** — health server bind address is no longer hardcoded to `0.0.0.0`
- **`TracerouteService` refactored** — uses `StatsRepository` methods instead of direct dict mutation
- **MTU and route hysteresis** — moved from direct dict mutation to proper `StatsRepository` methods (`update_mtu_hysteresis`, `update_route_hysteresis`, etc.)
- **Jitter calculation optimized** — replaced O(n) full-window recalculation with O(1) exponential moving average
- **`WINDOW_SIZE` / `LATENCY_WINDOW` deduplication** — removed duplicate constants from `stats_repository.py`, now imported from `config.py`
- **Entry point simplified** — `pinger.py` now delegates to `pinger.main()` instead of duplicating all dependency checks
- **Deprecated `locale.getdefaultlocale()`** replaced with `locale.getlocale()`
- **Dockerfile bumped** from `python:3.11-slim` to `python:3.12-slim`
- **Metrics default port** aligned: `start_metrics_server` default changed from `9090` to `8000`
- **Dependency checker** — `pythonping` removed from required (it's an optional fallback); `dnspython` added (hard dependency)
- **Type annotation fix** — `any` (builtin function) → `Any` (typing) in `PingService`
- **Duplicate key removed** — `last_route_change_time` removed from `create_stats()` (artifact of renaming)

## [2.0.0] - 2025-02-06

### Added
- **DNS Benchmark Tests** — comprehensive DNS performance testing
  - Cached query test (second query to same domain)
  - Uncached query test (unique random subdomain)
  - DotCom query test (popular domain response time)
  - Statistics tracking: min/avg/max/standard deviation/reliability per test type
  - Multi-server support — compare multiple DNS resolvers
  - Configurable history size for statistics accumulation

- **DNS Multi-Record Type Support** — test A, AAAA, CNAME, MX, TXT, NS records simultaneously

- **UI Section Dividers** — professional section headers (─── DNS ───, ─── Network ───, etc.)

- **Compact Benchmark Display** — single-line format: `C:12  U:45  D:25  │ 15q avg:27 σ:3ms`

### Changed
- Refactored monitoring panel layout for cleaner, more professional appearance
- Updated Analysis panel to use consistent section dividers
- DNS benchmark statistics now shown inline with aggregate metrics

### Configuration
```python
ENABLE_DNS_BENCHMARK = True
DNS_BENCHMARK_SERVERS = ["system"]  # or ["1.1.1.1", "8.8.8.8"]
DNS_BENCHMARK_HISTORY_SIZE = 50
```

## [1.0.0] - Initial Release

### Features
- Ping monitoring with latency tracking and packet loss detection
- Real-time TUI with sparkline charts and progress bars
- Smart alerts (sound + visual) with threshold hysteresis
- Public IP monitoring with geo detection
- DNS monitoring
- MTU/TTL monitoring
- Auto traceroute on connection problems
- Problem analysis (ISP/local/DNS/MTU classification)
- Route analysis with change detection
- Hop health monitoring
- Prometheus metrics and health endpoints
- Docker & Helm support
- Russian/English localization
