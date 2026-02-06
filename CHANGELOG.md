# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
