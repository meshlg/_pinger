# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
