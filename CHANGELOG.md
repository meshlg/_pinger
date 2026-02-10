# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
