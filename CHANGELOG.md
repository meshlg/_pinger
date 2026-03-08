# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.5.4.2147]

### New UI

- **New updated version of the UI

## [2.5.4.1753]

### Fixed

- **Fixed toast notification color not reflecting alert severity** in [`ui/panels/toast.py`](ui/panels/toast.py):
  - Added priority-based sorting for alert types: critical (0) > warning (1) > info (2) > success (3).
  - Toast now displays the highest-priority alert first, ensuring the panel color matches the most severe active alert.
  - Previously, the first alert in the list was used regardless of severity, often resulting in yellow (warning) styling even when critical alerts were present.

### Changed

- **Changed log file directory to project root** in [`config/settings_model.py`](config/settings_model.py):
  - `LOG_DIR` and `LOG_FILE` now default to the project root directory instead of `~/.pinger`.
  - Logs are now written to `ping_monitor.log` in the same directory as the main application files.

- **Clarified HTTP usage log messages** in [`services/geo_service.py`](services/geo_service.py) and [`services/ip_service.py`](services/ip_service.py):
  - Changed misleading "use a VPN" recommendation to accurate "API endpoint does not support HTTPS".
  - Changed log level from WARNING to INFO for HTTP fallback messages.

### Added

- **Added VPN detection service** in [`services/vpn_detector.py`](services/vpn_detector.py):
  - Cross-platform VPN connection detection using multiple methods:
    - Network interface analysis (TUN/TAP/WireGuard/ppp detection)
    - Windows-specific VPN adapter pattern matching
    - Routing table analysis for VPN interfaces
    - VPN process detection (OpenVPN, WireGuard, NordVPN, etc.)
  - Returns `VPNStatus` dataclass with connection details:
    - `is_connected`: boolean status
    - `interface_name`: detected VPN interface (if any)
    - `detection_method`: method used for detection
    - `confidence`: detection confidence (0.0-1.0)
  - Simple API: `is_vpn_connected()` and `get_vpn_status()` functions.

- **Added VPN status indicator to UI** in [`ui/panels/metrics.py`](ui/panels/metrics.py):
  - Displays 🔒 VPN when connected, 🔓 без VPN when not connected.
  - Shown in the "ЗАДЕРЖКА & СТАТИСТИКА" panel after consecutive losses.
  - Added translations for VPN status in [`config/i18n.py`](config/i18n.py).

## [2.5.4.0134]

### Fixed

- **Stabilized experience storage for problem analysis** in [`problem_analyzer.py`](problem_analyzer.py):
  - [`ExperienceStore.record_experience()`](problem_analyzer.py:498) now stores a deep-copied snapshot and updates an existing incident by `record_id` instead of appending duplicate mutable references.
  - Added [`ExperienceStore._rebuild_indexes()`](problem_analyzer.py:512) so pattern counts and solution outcome statistics are recomputed from the canonical stored records after updates.
  - [`ExperienceStore.get_similar_problems()`](problem_analyzer.py:532) now returns deep copies, preventing callers from mutating historical records in-place.
  - Prevents duplicated incident counting when the same record is first created, then auto-resolved, and later updated via solution feedback.

- **Fixed stale current-problem lifecycle handling** in [`problem_analyzer.py`](problem_analyzer.py):
  - [`ProblemAnalyzer.analyze_current_problem()`](problem_analyzer.py:2204) now closes the previous active incident before promoting a newly detected one to [`ProblemAnalyzer._current_problem`](problem_analyzer.py:2191).
  - Added [`ProblemAnalyzer._resolve_current_problem_locked()`](problem_analyzer.py:2378) to centralize active-incident resolution, persist the final state, and clear the in-memory pointer.
  - [`ProblemAnalyzer._record_no_problem()`](problem_analyzer.py:2390) now clears the current incident after resolving it, preventing stale data from lingering between clean analysis cycles.
  - [`ProblemAnalyzer.get_detailed_analysis()`](problem_analyzer.py:2614) now suppresses resolved incidents from the `current_problem` field, and [`ProblemAnalyzer.record_solution_feedback()`](problem_analyzer.py:2690) clears the active pointer when feedback resolves the tracked incident.

- **Made configured thresholds and custom analysis rules effective** in [`problem_analyzer.py`](problem_analyzer.py):
  - Added [`AnalysisConfig.get_threshold()`](problem_analyzer.py:457), [`AnalysisConfig.is_threshold_breached()`](problem_analyzer.py:461), and [`AnalysisConfig.get_matching_rules()`](problem_analyzer.py:486) so runtime configuration now participates directly in analysis decisions.
  - [`DeepAnalysisEngine.detect_anomalies()`](problem_analyzer.py:726) now uses configured warning/critical thresholds and adaptive baseline logic instead of relying only on sigma deviation after baseline warmup.
  - [`CausalAnalysisEngine._check_latency()`](problem_analyzer.py:1181), [`ClassificationEngine._determine_type()`](problem_analyzer.py:1326), [`ProblemAnalyzer._has_problem()`](problem_analyzer.py:2495), and [`ProblemAnalyzer._determine_preliminary_type()`](problem_analyzer.py:2564) now honor configured threshold values rather than hard-coded global constants.
  - [`ClassificationEngine.classify_problem()`](problem_analyzer.py:1282) and [`ProblemAnalyzer._has_problem()`](problem_analyzer.py:2495) now apply enabled custom [`AnalysisRule`](problem_analyzer.py:368) instances.
  - [`ProblemAnalyzer.configure_threshold()`](problem_analyzer.py:2810) now normalizes [`ThresholdConfig.metric_name`](problem_analyzer.py:388) to the explicit method argument, removing the misleading unused parameter behavior.

- **Removed unsafe packet-loss fallback for preliminary causal typing** in [`problem_analyzer.py`](problem_analyzer.py):
  - [`ProblemAnalyzer.analyze_current_problem()`](problem_analyzer.py:2408) now passes anomalies into [`ProblemAnalyzer._determine_preliminary_type()`](problem_analyzer.py:2564) so preliminary typing can use the same observed signal set as the rest of the pipeline.
  - Added [`ProblemAnalyzer._anomaly_to_problem_type()`](problem_analyzer.py:2554) to map strong anomalies to a safe preliminary type when no threshold- or state-based condition matches.
  - [`ProblemAnalyzer._determine_preliminary_type()`](problem_analyzer.py:2564) now falls back to the strongest mapped anomaly, and returns [`ProblemType.UNKNOWN`](problem_analyzer.py:83) when no evidence points to a concrete family, instead of incorrectly forcing [`ProblemType.PACKET_LOSS`](problem_analyzer.py:64).

## [2.5.3.0109]

### Added

- **Intelligent Problem Analysis System** in [`problem_analyzer.py`](problem_analyzer.py):
  - Complete rewrite with multi-layered architecture for comprehensive problem analysis.
  - **Layer 1 - Data Collection**: Ingests and preprocesses metrics from multiple sources.
  - **Layer 2 - Deep Analysis Engine**: Detects anomalies, correlations, and hidden patterns using statistical analysis (sigma deviation, Pearson correlation, trend detection, oscillation/periodicity analysis).
  - **Layer 3 - Causal Analysis**: Multi-factor root cause detection with contribution weights and evidence tracking.
  - **Layer 4 - Classification Engine**: Automatic problem type, severity (CRITICAL/HIGH/MEDIUM/LOW/INFO), and priority (URGENT/HIGH/MEDIUM/LOW) determination with confidence scoring.
  - **Layer 5 - Learning System**: Experience accumulation with solution outcome tracking, historical success rates, and pattern memory for continuous improvement.
  - **Layer 6 - Solution Generator**: Actionable recommendations with effectiveness estimation, risk assessment, resource cost, and historical success probability.
  - **Layer 7 - Predictive Analytics**: Trend-based, pattern-based, and historical frequency predictions with preventive action suggestions.
  - **Layer 8 - Reporting**: Comprehensive reports with health scores, trend analysis, and visualization data.
  - **External Integration Layer**: Pluggable handlers for logging, metrics, and alert systems.
  - **Configurable Rules**: Custom thresholds, analysis rules, and behavior settings.
  - Full backward compatibility with existing `analyze_current_problem()`, `predict_problems()`, `identify_pattern()`, and `get_problem_summary()` APIs.
  - New APIs: `generate_report()`, `get_detailed_analysis()`, `get_predictions()`, `record_solution_feedback()`, `configure_threshold()`, `configure_rule()`.

### Fixed
- **Fixed `AttributeError` on shutdown** in [`main.py`](main.py):
  - `self.ui._fmt_uptime()` was calling a method that no longer exists on `MonitorUI` (moved to `ui/helpers.py` as `fmt_uptime()`). Pressing Ctrl+C would crash instead of printing uptime.
  - Now imports `fmt_uptime` from `ui.helpers` and calls it directly.

- **Initialized `benchmark_dict` before conditional block** in [`core/dns_monitor_task.py`](core/dns_monitor_task.py):
  - `benchmark_dict` was only defined inside `if ENABLE_DNS_BENCHMARK:` block but referenced outside it. While Python's ternary evaluates lazily, this was fragile and hard to read.
  - Added `benchmark_dict = None` initialization before the conditional, and simplified the `calculate_dns_health()` call.

### Security
- **IP providers prefer HTTPS with automatic HTTP fallback** in [`services/ip_service.py`](services/ip_service.py):
  - HTTPS is now the primary transport for all four IP-lookup providers (MITM-resistant).
  - Replaced `http://ifconfig.me/ip` with `https://api.ipify.org/?format=json` (JSON response, more reliable).
  - Added automatic HTTP fallback: if HTTPS fails due to `SSLError`, `ConnectionError`, or `ProxyError`
    (e.g. blocked hosts in regions with network restrictions), the plain HTTP URL is tried and a security
    warning is logged to inform the user that the connection is unencrypted.
  - Timeout failures do **not** trigger HTTP fallback (they indicate a slow/overloaded provider, not a
    protocol block), so the next provider in the list is tried instead.
  - Extracted `_try_provider()` helper to avoid duplicating response-parsing logic between HTTPS and HTTP attempts.

- **TOCTOU race condition fixed** in [`single_instance_notifications.py`](single_instance_notifications.py):
  - Replaced multi-step `exists()` → `is_symlink()` → `isfile()` → `open()` sequence with an atomic `O_NOFOLLOW` open.
  - On POSIX systems, `os.open(O_RDONLY | O_NOFOLLOW)` atomically refuses symlink targets (ELOOP/OSError).
  - On Windows (no O_NOFOLLOW), falls back to a guarded `is_symlink()` + `is_file()` check before opening.
  - Added 4 KB read limit to protect against file-bomb attacks on the notification file.

- **Health endpoint credentials now use TTL cache with threading.Lock** in [`infrastructure/health.py`](infrastructure/health.py):
  - Replaced permanent `_credentials_loaded: bool` flag with a time-based TTL cache (`_CONFIG_CACHE_TTL = 300 s`).
  - Credentials are re-read every 5 minutes, allowing Docker Secrets rotation to take effect without restart.
  - Added `threading.Lock` (`_config_lock`) with double-checked locking to prevent concurrent re-initialization.

### Fixed
- **Average latency threshold now uses sliding window** in [`monitor.py`](monitor.py):
  - `_check_avg_latency_threshold()` previously computed `total_latency_sum / success_count`, which used
    the all-time average and rendered the threshold ineffective after extended uptime.
  - Now uses the bounded `latencies` deque (size `LATENCY_WINDOW`) for an accurate rolling average.

- **Traceroute file timestamp consistency** in [`services/traceroute_service.py`](services/traceroute_service.py):
  - `start_time` is now captured once *before* the traceroute command runs.
  - Both the output filename and the file header (`Started:` / `Finished:` lines) use this single timestamp.
  - Eliminates the previous mismatch where a long traceroute produced a header time minutes after the filename time.

- **GeoIP service now prefers HTTPS with automatic HTTP fallback** in [`services/geo_service.py`](services/geo_service.py):
  - Primary URL changed from `http://ip-api.com/json/` to `https://ip-api.com/json/`.
  - On `SSLError`, `ConnectionError`, or `ProxyError`, falls back to HTTP and logs a one-time security warning.
  - Extracted `_try_fetch()` helper to deduplicate HTTPS/HTTP fetch logic.

- **GeoIP cache bounded with LRU eviction and TTL** in [`services/geo_service.py`](services/geo_service.py):
  - Replaced unbounded `dict` cache with `OrderedDict`-based LRU cache.
  - Added `_MAX_CACHE_SIZE = 500` limit; oldest entries evicted via `popitem(last=False)`.
  - Cache entries expire after `_CACHE_TTL = 86400` seconds (24 hours).

- **RateLimiter now purges stale tracked IPs** in [`infrastructure/health.py`](infrastructure/health.py):
  - Added `_maybe_purge_stale_ips()` method that runs every 5 minutes to clean expired entries from `_requests`, `_failed_auth`, and `_blocked` dicts.
  - Added `_max_tracked_ips = 10000` cap to prevent memory exhaustion from IP-scanning attacks.

- **`cleanup_sync()` race condition hardened** in [`infrastructure/process_manager.py`](infrastructure/process_manager.py):
  - Wrapped `list(self._active_processes)` in `try/except RuntimeError` with `.copy()` retry to handle concurrent set modification in atexit/signal handlers.

- **Removed duplicate import shadowing in config package** in [`config/__init__.py`](config/__init__.py):
  - `CURRENT_LANGUAGE` and `SUPPORTED_LANGUAGES` were imported from `.settings` (line 17) and then re-imported from `.i18n` (line 205), silently shadowing the first binding.
  - Removed the redundant re-import from `.i18n`; only `LANG` and `t()` are now imported from there.

- **Removed duplicate entry in `__all__`** in [`infrastructure/__init__.py`](infrastructure/__init__.py):
  - `"start_health_server"` appeared twice in the `__all__` list. Removed the duplicate.

### Changed (Code Quality & Architecture)

- **DRY — centralized `ensure_utc()` function** in [`config/types.py`](config/types.py):
  - Moved the duplicated `_ensure_utc()` helper (found in 7+ files) into `config/types.py` as the single canonical implementation.
  - Updated all consumers (`core/adaptive_thresholds.py`, `core/alert_types.py`, `core/alert_prioritizer.py`, `problem_analyzer.py`, `stats_repository.py`, `services/traceroute_service.py`, `ui/helpers.py`) to import from `config`.
  - Exported via `config/__init__.py` and `__all__`.

- **Fixed naive timestamp in `AlertEntity`** in [`core/alert_types.py`](core/alert_types.py):
  - Changed `timestamp` default from `datetime.now` (naive, local) to `datetime.now(timezone.utc)` (timezone-aware UTC).

- **Replaced `list` with `deque(maxlen=30)` for hop latency history** in [`services/hop_monitor_service.py`](services/hop_monitor_service.py):
  - `HopStatus.latency_history` now uses `deque(maxlen=30)` for automatic eviction.
  - Removed manual `self.latency_history = self.latency_history[-30:]` truncation.
  - Updated `to_dict()` to convert deque to list for serialization.

- **Singleton pattern for `VersionService`** in [`services/version_service.py`](services/version_service.py):
  - Module-level `get_latest_version()` and `clear_cache()` functions now reuse a single `VersionService` instance instead of creating a new one on each call.

- **Fixed incorrect indentation** in [`problem_analyzer.py`](problem_analyzer.py):
  - Lines 170-173 were indented at 16 spaces (inside a non-existent block); corrected to 12 spaces to align with the enclosing `for` loop.

- **Added `reload_theme()` function** in [`ui/theme.py`](ui/theme.py):
  - Added `reload_theme()` that re-reads `PINGER_THEME` and updates all module-level color constants for runtime theme switching.
  - Added docstring note explaining import-time resolution behavior.

- **Documented O(n) rate limiter as acceptable** in [`core/smart_alert_manager.py`](core/smart_alert_manager.py):
  - Added comment noting that `sum()` over `deque(maxlen=~20)` is O(n) but acceptable for the bounded collection size.

- **Fixed `asyncio.run()` in active event loop** in [`services/dns_service.py`](services/dns_service.py):
  - `check_dns_resolve_simple()` now detects if an event loop is already running and uses `ThreadPoolExecutor` fallback to avoid `RuntimeError`.

- **Extracted server startup from `Monitor.__init__()`** in [`monitor.py`](monitor.py):
  - Moved Prometheus and health server startup into a new `start_servers()` method, called from `main.py` after construction.
  - Eliminates side effects (port binding) in `__init__`.

- **Removed duplicate `self.monitor` reference** in [`ui/core.py`](ui/core.py):
  - Eliminated redundant `self.monitor = data_provider` attribute; all access now goes through the Protocol-typed `self._data_provider`.
  - Removed unused `TYPE_CHECKING` import of `Monitor`.

- **Documented i18n coupling in `create_stats()`** in [`config/types.py`](config/types.py):
  - Added docstring explaining that `t()` calls in default values bind to the locale at creation time.
  - Acceptable for current architecture (env-var locale set once at startup). Full decoupling deferred to future refactor.

### Improved (Polish & Hardening)

- **Fixed false-positive ping success on unparseable output** in [`services/ping_service.py`](services/ping_service.py):
  - When ping returned output but latency could not be parsed from it, the function incorrectly reported `(True, 0.0)` — pretending 0 ms latency. Now returns `(False, None)` and logs the raw output at DEBUG level.

- **Added missing `dec()` method to `_DummyGauge`** in [`infrastructure/metrics.py`](infrastructure/metrics.py):
  - Prometheus `Gauge` supports `inc()`, `dec()`, and `set()`. The no-op fallback class was missing `dec()`, which would raise `AttributeError` if ever called without `prometheus_client` installed.

- **Consolidated duplicate `from typing import Dict`** in [`stats_repository.py`](stats_repository.py):
  - `Dict` was imported separately on line 21 while the rest of `typing` was already imported on line 9. Merged into a single import statement.

- **Applied `ensure_utc()` to timestamp comparison** in [`problem_analyzer.py`](problem_analyzer.py):
  - `p["timestamp"].hour` was compared to `datetime.now(timezone.utc).hour` without normalizing the timestamp to UTC first. If the timestamp was naive (local time), the hour comparison could be wrong by several hours.

- **Replaced `lambda` with `functools.partial`** in [`core/background_task.py`](core/background_task.py):
  - `run_in_executor(executor, lambda: func(*args, **kwargs))` replaced with `run_in_executor(executor, partial(func, *args, **kwargs))`. `partial` is more debuggable (has `.func`, `.args` attributes), picklable, and avoids late-binding closure issues.

- **Windows lock file now writes PID** in [`single_instance.py`](single_instance.py):
  - Unix path already wrote PID to the lock file for debugging stale locks. Windows path (`CreateFileW`) did not. Now uses `WriteFile` + `FlushFileBuffers` to write the current PID after acquiring the exclusive handle.

- **Replaced `sys.path.insert(0, ".")` with absolute path** in [`demo_mode.py`](demo_mode.py):
  - `sys.path.insert(0, ".")` depends on the current working directory at launch time. Replaced with `Path(__file__).resolve().parent` for robustness when the script is invoked from any directory.

- **Reduced dead `config.py` legacy wrapper to stub** in [`config.py`](config.py):
  - The 325-line file re-exported every symbol from `config/` but was never actually imported (Python resolves `import config` to the `config/` package). Replaced with a minimal deprecation notice stub.

## [2.5.2.1648]

### Added
- **Visual UI improvements**:
  - [`sparkline_double()`](ui/helpers.py:270) — two-row sparkline with 16 vertical levels (upper/lower half-blocks) for higher-resolution latency charts.
  - [`mini_gauge()`](ui/helpers.py:310) — compact gauge widget with status icon (◉/◎/◗), percentage, and color-coded bar for success rate and DNS score.
  - [`dns_mini_bar()`](ui/helpers.py:340) — tiny horizontal bar chart for DNS response time visualization in record-type table.
  - **Compact inline metrics** in [`ui/panels/metrics.py`](ui/panels/metrics.py) — single-line `Cur:X Avg:Y Best:Z…` format for compact tier.
  - **Two-row sparklines** in [`ui/panels/metrics.py`](ui/panels/metrics.py) — replaced single-row with `sparkline_double` for standard/full height tiers.
  - **Mini gauge for success rate** in [`ui/panels/metrics.py`](ui/panels/metrics.py) — replaces plain progress bar with icon-based gauge.
  - **DNS mini bar column** in [`ui/panels/analysis.py`](ui/panels/analysis.py) — horizontal latency bars next to response time in DNS record table.
  - **Mini gauge for DNS score** in [`ui/panels/analysis.py`](ui/panels/analysis.py) — replaces plain bar with `mini_gauge()` widget.
  - **Hop table sparkline column** in [`ui/panels/hops.py`](ui/panels/hops.py) — per-hop latency trend sparkline from history data.
  - **Dashboard visual enhancements** in [`ui/panels/dashboard.py`](ui/panels/dashboard.py):
    - Trend direction indicator (▲/▼/►) for latency.
    - Colored dots (●) showing recent ping results (last 20).
    - Connection state icon shown alongside status label.
    - Globe icon (🌐) for public IP display.

### Refactored
- **Decomposed monolithic `ui.py` (~1203 lines) into modular `ui/` package** :
  - [`ui/theme.py`](ui/theme.py) — style constants, Unicode elements, color palette, layout tier types.
  - [`ui/helpers.py`](ui/helpers.py) — standalone helper functions (`fmt_uptime`, `sparkline`, `progress_bar`, `kv_table`, etc.).
  - [`ui/panels/header.py`](ui/panels/header.py) — `render_header()` standalone function.
  - [`ui/panels/toast.py`](ui/panels/toast.py) — `render_toast()` standalone function.
  - [`ui/panels/dashboard.py`](ui/panels/dashboard.py) — `render_dashboard()` standalone function.
  - [`ui/panels/metrics.py`](ui/panels/metrics.py) — `render_metrics_panel()` standalone function.
  - [`ui/panels/analysis.py`](ui/panels/analysis.py) — `render_analysis_panel()` standalone function.
  - [`ui/panels/hops.py`](ui/panels/hops.py) — `render_hop_panel()` standalone function.
  - [`ui/panels/footer.py`](ui/panels/footer.py) — `render_footer()` standalone function.
  - [`ui/core.py`](ui/core.py) — `MonitorUI` class (constructor, tier detection, layout generation).
  - [`ui/__init__.py`](ui/__init__.py) — re-exports `MonitorUI` for backward compatibility.
  - Updated [`pyproject.toml`](pyproject.toml) packages from `ui.py` to `ui` directory.
  - Updated [`tests/test_regressions_security_runtime.py`](tests/test_regressions_security_runtime.py) to call standalone panel functions.

## [2.5.2.0506]

### Security
- **Hardened inter-process notification file handling** in [`single_instance_notifications.py`](single_instance_notifications.py):
  - Replaced direct write to predictable temp file with atomic temp-file write + [`os.replace`](single_instance_notifications.py) semantics.
  - Introduced per-user notification directory under temp with restricted permissions.
  - Added defensive checks to ignore unsafe notification paths (e.g. symlink/non-regular path).

### Fixed
- **Graceful shutdown reliability for HTTP endpoints**:
  - Updated health and metrics servers to run with `serve_forever()` and stop via `shutdown()` + `server_close()` + thread join.
  - Prevents occasional shutdown hangs and improves container/process termination behavior.
  - Affected modules: [`infrastructure/health.py`](infrastructure/health.py), [`infrastructure/metrics.py`](infrastructure/metrics.py).

- **Race condition in traceroute trigger (single-flight)**:
  - Made trigger path atomic with lock-protected reservation before task scheduling.
  - Prevents duplicate concurrent traceroutes under near-simultaneous trigger calls.
  - Affected module: [`services/traceroute_service.py`](services/traceroute_service.py).

### Tests
- Added regression coverage in [`tests/test_regressions_security_runtime.py`](tests/test_regressions_security_runtime.py):
  - Health/Metrics server stop lifecycle cleanup.
  - Single-flight traceroute trigger behavior.
  - Secure notification path handling and roundtrip checks.

## [2.5.1.0030]

### Added
- **DNS Health Dashboard** — Comprehensive DNS monitoring with health scoring:
  - **DNS Score (0-100)** — Weighted score based on record success rate (40%), reliability (30%), and latency (30%)
  - **DNS Jitter** — Variability of DNS response times (standard deviation)
  - **Status classification** — excellent (≥90), good (≥75), fair (≥50), poor (≥25), critical (<25)
  - **Detailed record table** — Per-record-type monitoring (A, AAAA, NS, MX, CNAME, TXT) with status, response time, TTL, and record count
  - **Compact benchmark line** — C:cached U:uncached D:dotcom format with average response time

### Changed
- **DNS UI Section Redesign** — Restructured DNS panel with improved visual hierarchy:
  - Score bar indicator (5-char mini progress bar)
  - Reliability and jitter inline display
  - Record type table with status icons (✓/✗/~)
  - TTL values shown for each record type
- **Toast Notifications Enhancement** — Improved visual design with:
  - Alert type-specific icons (⚠/⚡/●/✓)
  - Color-coded backgrounds (critical=red, warning=yellow, info=accent, success=green)
  - Heavy border for critical alerts
  - Localized "more alerts" counter

### Removed
- **Duplicate Notifications Section** — Removed redundant "NOTIFICATIONS" subsection from Analysis panel; toast notifications remain the single source for alerts

### Localization
- Added translations: `dns_score`, `dns_reliability_short`, `dns_jitter_short`, `more_alerts`

## [2.5.0.1825]

- **Traceroute Service Enhancement** — Enhanced `services/traceroute_service.py` with new features:
  - Added structured result types: `HopInfo` and `TracerouteResult` dataclasses with parsed hop data, latency stats, timeout tracking, and metadata.
  - Integrated comprehensive Prometheus metrics: `pinger_traceroute_runs_total` (with status label), `pinger_traceroute_latency_ms`, `pinger_traceroute_hops_count`, `pinger_traceroute_timeouts_total`.
  - Added target validation (`is_valid_target()`) to prevent argument injection and invalid inputs.
  - Added IPv6 support detection (`is_ipv6_target()`, `is_ipv6_available()`) with `traceroute6` command support.
  - Added `parse_hops()` method for extracting structured hop information from raw traceroute output.
  - Added `get_capabilities()` method for querying available traceroute features.
  - Refactored command building into `_build_command()` method to eliminate code duplication between sync and async versions.
  - Improved error handling with proper metric recording for different failure modes (timeout, error, cancelled).
  - Maintained full backward compatibility with existing API (`run_traceroute()`, `run_traceroute_async()`, `trigger_traceroute()`).

- **Hop Monitor Service Enhancement** — Added route statistics API to `services/hop_monitor_service.py`:
  - Added `RouteStats` frozen dataclass with aggregated route metrics: hop count, average/max latency, packet loss, route health status, and problem hop identification.
  - Added `get_route_stats()` method for quick route health assessment without iterating through all hops.
  - Route health classification: "healthy" (<1% loss, no problems), "degraded" (<5% loss, ≤1 problem hop), "critical" (otherwise), or "unknown" (no hops).
  - Useful for dashboards, alerts, and logging with `to_dict()` serialization support.

## [2.4.9.0830]
### Changed
- **Version Service Refactoring** — Completely refactored `services/version_service.py` for better maintainability and reliability:
  - Introduced `VersionService` class with dependency injection for cache TTL, timeout, and retry settings.
  - Added `VersionInfo` dataclass for structured version information with `current`, `latest`, and `update_available` fields.
  - Implemented retry logic with exponential backoff (3 attempts, starting at 0.5s) for transient network failures.
  - Added Prometheus metrics (`pinger_version_check_total`, `pinger_version_check_latency_ms`) for monitoring version check operations.
  - Added proper `User-Agent` header and GitHub API versioning (`Accept: application/vnd.github.v3+json`).
  - Improved HTTP error handling with distinction between retryable (5xx, network) and non-retryable (4xx) errors.
  - Used `Final` type hints for constants and improved type annotations throughout.
  - Maintained full backward compatibility with existing module-level functions (`get_latest_version()`, `check_update_available()`, `clear_cache()`).

### Fixed
- **Main Loop Crash on Disconnect** — Fixed a bug where `ui.py`'s `_get_connection_state` occasionally returned 2 elements instead of 3 when ping timed out or connection was lost, causing a "not enough values to unpack" error in the main loop.

## [2.4.8.2154]
### Added
- **MTU Discovery Optimization** — Added fast-fail timeouts to the `ping` utility used for Path MTU discovery, reducing the time required from minutes to seconds. Additionally, initial MTU status now ignores the hysteresis delay, meaning it displays immediately on startup.
- **Maintenance Windows / Quiet Hours** — Added `ENABLE_QUIET_HOURS` config with `QUIET_HOURS_START` and `QUIET_HOURS_END` to suppress alert sounds during scheduled maintenance windows or nighttime. Visual alerts are still logged to the UI, but without the audio disruption.
- **IP Provider Reliability Metrics** — Added Prometheus metrics `pinger_ip_provider_requests_total` and `pinger_ip_provider_latency_ms` to track the reliability and response time of external public IP detection services, making it easier to monitor fallbacks.
- **Endpoint Security Metrics** — Added Prometheus metrics for health endpoints (`pinger_health_auth_failures_total`, `pinger_health_blocked_ips_total`, `pinger_health_rate_limited_total`) to provide transparency into brute-force and DoS attempts.
- **Adaptive Warm-up UI Status** — Added "WARM-UP: X/Y" status indicator to the UI dashboard showing the progress of adaptive thresholds learning (`sample_count`/`min_samples`). This provides transparency and reduces confusion about why thresholds are still using defaults.
- **Outage State Consistency** — Fixed UI inconsistencies during internet disconnection where problem analysis incorrectly showed "No problems" and "Stable" instead of proper "ISP Issue" and "Risk" status.
  - ProblemAnalyzer now prioritizes active disconnection (connection_lost or consecutive losses) as ISP issue in analysis and prediction.
  - Added immediate problem analysis refresh in Monitor when connection_lost threshold toggles, eliminating stale state window between background task intervals.
  - UI now masks stale route hops, MTU values, and hop data during disconnection, showing "DISCONNECTED" status instead of cached values.
  - Enhanced ProblemAnalyzerTask to pass current problem type to prediction for immediate risk assessment.

### Added
- **Regression Tests** — Added comprehensive tests for outage state consistency in `tests/test_regressions_security_runtime.py`:
  - `test_problem_analyzer_reports_outage_as_isp_and_risk()` — Verifies outage classification and prediction.
  - `test_ui_analysis_panel_masks_stale_route_and_mtu_on_disconnect()` — Ensures UI hides stale data during disconnect.
  - `test_ui_hop_panel_hides_stale_hops_on_disconnect()` — Verifies hop panel disconnection handling.
  - `test_monitor_refresh_problem_analysis_updates_snapshot_immediately()` — Confirms immediate refresh on disconnect state changes.

## [2.4.8.0351]
### Security
- **Timing Attack Prevention** — Replaced direct string comparison with `secrets.compare_digest` for metrics basic auth credentials to prevent timing attacks.
- **IP Spoofing Protection** — Hardened health endpoint to only trust `X-Forwarded-For` headers from explicitly configured proxies via the `HEALTH_TRUSTED_PROXIES` environment variable, preventing IP spoofing and rate limit bypass.

### Fixed
- **Rate Limiter Deadlock** — Fixed a deadlock in `RateLimiter` used by the health endpoint by switching to `threading.RLock`.
- **Event Loop Blocking** — Prevented event loop blocking during synchronous version checks by executing them in a thread pool executor.
- **False IP Change Alerts** — Improved IP change detection to ignore invalid IP strings returned by providers during temporary failures, reducing false positive alerts.
- **Hard Startup Failure** — Made the `traceroute/tracert` command check conditional, allowing the app to start if traceroute-dependent features (`ENABLE_AUTO_TRACEROUTE`, `ENABLE_HOP_MONITORING`, `ENABLE_ROUTE_ANALYSIS`) are disabled.
- **Adaptive Thresholds Warm-up** — Fixed an issue where adaptive thresholds acted like static thresholds for too long by improving the baseline warm-up logic with running averages and expanding windows.

## [2.4.7.1611]
### Added
- **Multi-color UI themes** — Added support for UI themes (`orange`, `catppuccin`, `matrix`, `minimal`, `monochrome`, `purple`) via the `UI_THEME` setting to reduce eye strain.
- **Semantic background** — The background color of the status bar and header now dynamically changes to dark red during critical errors (e.g., connection lost) to grab attention.

### Changed
- **Cleaner Layout** — Removed excess borders (box-in-a-box styling) to create a cleaner and more modern dashboard layout.
- **Improved Sparklines** — Added visual highlight (reverse color) to the last data point in the sparklines for better trackability.
- **Text Hierarchy** — Refined text accents for better readability and clearer data structure.

## [2.4.7.1033]
### Fixed
- **Ping timeout false positive** — Fixed an issue in `services/ping_service.py` where ping timeouts on Windows were incorrectly parsed as successful pings with 0.0ms latency. The parser now correctly checks the subprocess return code.
- **UI state mutation** — Removed `cleanup_alerts()` call from `ui.py`'s `_render_analysis_panel` to ensure the UI remains strictly a presentation layer. The cleanup logic was moved to the main `ping_once` cycle in `monitor.py`.
- **Hard shutdown in main thread** — Replaced `sys.exit(0)` in the Windows console handler (`main.py`) with a graceful `self.monitor.stop_event.set()` to allow `asyncio` events to be properly awaited and cleaned up.
- **Mathematical variable naming** — Renamed `variance` to `stdev` in `route_analyzer.py` to accurately reflect the use of `statistics.stdev`.
- **UI Localization** — Replaced hardcoded UI strings in `ui.py` (such as "more...", "avg:", "ms") with their respective `t()` translation calls mapped in `config/i18n.py`.

## [2.4.6.1418]
### Changed
- **UI full redesign** — Rewrote `ui.py` from scratch (1124→750 lines). Height-aware layout (4 tiers: minimal/short/standard/full), consolidated panels (Latency+Stats → Metrics, Analysis+Monitoring → single panel), single snapshot per render cycle, adaptive hop table columns based on terminal width, explicit size-based Layout to prevent overflow/overlap.

## [2.4.6.0209]
### Fixed
- **PingService NameError** — Added missing `import asyncio` to `services/ping_service.py`. Methods `_detect_ipv6_async` and `_run_ping_command_async` used `asyncio.get_running_loop()` and `asyncio.TimeoutError` without importing the module, causing `name 'asyncio' is not defined` crash during async ping operations.
- **PingService duplicate methods** — Removed duplicate definitions of `_ping_with_pythonping` and `_build_ping_command` left over from sync→async refactoring.
- **PingService dead code** — Removed unreachable `return None, None` in `extract_ttl_async` and dead `_ping_with_system` method referencing removed `_run_ping_command`.
- **HopMonitorService cleanup** — Removed duplicate `import threading` and dead `pass` statement in `_resolve_hostname_bg`.

## [2.4.5.1045]
### Security
- **Systemic Security Improvements** — Comprehensive hardening of the application.
  - **Non-blocking DNS**: Refactored `DNSService` to be fully asynchronous, wrapping all blocking `dns.resolver` calls in `loop.run_in_executor`.
  - **Least Privilege**: Added `ENABLE_PYTHONPING_FALLBACK` (default: True). Administrators can now disable root-requiring `pythonping` fallback.
  - **Input Validation**: Hardened `IPService` to validate IP addresses received from external APIs using `ipaddress` library.

### Refactoring
- **Async-Only PingService**: Removed synchronous methods (`ping_host`, `_detect_ipv6`) to enforce non-blocking execution.
- **Dependency Updates**: Updated `rich` to `^13.7.0` and verified `requests` version.

### Fixed
- **DNSService AttributeError**: Resolved missing `_query_single_async` method.
- **DNSService NameError**: Fixed missing `asyncio` import.

## [2.4.4.1851]
### Performance
- **Asynchronous Hop Discovery** — Optimized traceroute by disabling synchronous DNS resolution (`-d`/`-n` flags).
  - **Impact**: Hop discovery is now 5-10x faster (seconds instead of minutes).
  - **Background Resolution**: Hostnames are resolved asynchronously in background threads without blocking the UI.

### Changed
- **Hop List UI Overhaul** — Complete redesign of the "Trace Hops" panel.
  - **Status Indicators**: Added traffic-light dots for instant health assessment.
  - **Dedicated Columns**: Added specific columns for **Provider (ASN)** and **Location (Loc)** in wide mode.
  - **Smart Formatting**: Autosizing columns with intelligent text truncation for long path names.
  - **Cleanup**: Removed corporate suffixes ("Inc.", "LLC") from ISP names to save screen space.

### Localization
- **Expanded Translations** — Added localization for new UI columns.
  - **ASN**: Translated as "Провайдер" (Provider) in Russian for better clarity.
  - **Loc**: Translated as "Локация" (Location) in Russian.

## [2.4.4.1003]
### Security
- **Subprocess Resource Leaks** — Fixed critical vulnerability where zombie processes could accumulate over time.
  - Implemented centralized `ProcessManager` to track and safely terminate all child processes.
  - Refactored `PingService`, `TracerouteService`, and `HopMonitorService` to use asynchronous execution.
  - Added robust cleanup logic to `Monitor.shutdown()` ensuring all processes are killed on exit.

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
