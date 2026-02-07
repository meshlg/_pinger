# Pinger — Network Monitor

Async network monitoring tool with real-time terminal UI, alerts, and connection quality analysis.

![Pinger Interface](assets/screenshot.jpg)

Supports **Russian** and **English** localization — switch via `CURRENT_LANGUAGE` in `config.py`.

## Features

- **Ping monitoring** — latency tracking, packet loss detection, jitter calculation
- **Real-time TUI** — Rich-based dashboard with sparkline charts, Unicode progress bars, color-coded status
- **Smart alerts** — sound + visual notifications with threshold hysteresis (packet loss, latency, jitter, connection lost)
- **Public IP monitoring** — change detection with geo info
- **DNS monitoring** — resolution speed checks with multiple record types (A, AAAA, CNAME, MX, TXT, NS), benchmark tests (Cached/Uncached/DotCom) with statistics (min/avg/max/σ)
- **MTU / TTL monitoring** — path MTU discovery, fragmentation detection
- **Auto traceroute** — triggered on connection problems, saved to `traceroutes/`
- **Problem analysis** — automatic ISP/local/DNS/MTU problem classification, pattern detection, prediction
- **Route analysis** — traceroute-based hop analysis, route change detection
- **Hop health monitoring** — automatic hop discovery via traceroute, periodic ping of each intermediate hop, full traceroute-style table with min/avg/last latency and loss per hop
- **Prometheus metrics** — `/metrics` endpoint for scraping
- **Health endpoint** — `/health` and `/ready` for Kubernetes probes
- **Docker & Helm** — ready for containerized deployment

## Requirements

- Python 3.10+
- Windows / Linux / macOS
- System commands: `ping`, `traceroute` (or `tracert` on Windows)

## Installation

### Quick Install (pipx — recommended for end users)

```bash
# Install pipx if you don't have it
pip install pipx
pipx ensurepath

# Install from PyPI (when published) or local directory
pipx install network-pinger
# or for local development:
pipx install .

# Run anywhere
pinger
```

### Upgrading (pipx)

```bash
# Check for updates and upgrade
pipx upgrade network-pinger
```

### Development Install (Poetry)

```bash
# Install Poetry if you don't have it
pip install poetry

# Clone and setup
git clone https://github.com/meshlg/_pinger.git
cd _pinger
poetry install

# Run in Poetry environment
poetry run pinger
# or activate shell
poetry shell
pinger
```

### Traditional Install (pip)

```bash
pip install -r requirements.txt
python pinger.py
```

### Dependencies

| Package | Purpose |
|---|---|
| `rich>=13.0.0` | Terminal UI (panels, tables, live display) |
| `requests>=2.25.0` | Public IP info via ip-api.com |
| `pythonping>=1.1.0` | Fallback ping when system `ping` is unavailable |
| `prometheus_client>=0.16.0` | Prometheus metrics export (optional) |
| `dnspython>=2.4.0` | Advanced DNS queries (multiple record types) |

### Building & Publishing (Poetry)

```bash
# Build distributable package (wheel + source)
poetry build

# Publish to PyPI (configure token first)
poetry publish
```

Press `Ctrl+C` for graceful shutdown.

## Configuration

All settings are in `config.py`:

### Core

```python
CURRENT_LANGUAGE = "ru"         # "ru" or "en"
TARGET_IP = "8.8.8.8"          # Ping target
INTERVAL = 1                    # Ping interval (seconds)
WINDOW_SIZE = 1800              # Stats window (30 min)
LATENCY_WINDOW = 600            # Latency history (10 min)
```

### Thresholds & Alerts

```python
PACKET_LOSS_THRESHOLD = 5.0     # Packet loss (%)
AVG_LATENCY_THRESHOLD = 100     # Average latency (ms)
JITTER_THRESHOLD = 30           # Jitter (ms)
CONSECUTIVE_LOSS_THRESHOLD = 5  # Consecutive lost packets

ENABLE_SOUND_ALERTS = True
ALERT_COOLDOWN = 5              # Min interval between sounds (seconds)
```

### IP Monitoring

```python
ENABLE_IP_CHANGE_ALERT = True
IP_CHECK_INTERVAL = 15          # Seconds
```

### DNS Monitoring

```python
ENABLE_DNS_MONITORING = True
DNS_TEST_DOMAIN = "cloudflare.com"
DNS_CHECK_INTERVAL = 10
DNS_SLOW_THRESHOLD = 100        # "Slow" DNS threshold (ms)
DNS_RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "NS"]  # Record types to test

# DNS Benchmark tests (Cached/Uncached/DotCom)
ENABLE_DNS_BENCHMARK = True
DNS_BENCHMARK_DOTCOM_DOMAIN = "cloudflare.com"  # Domain for DotCom test
DNS_BENCHMARK_SERVERS = ["system"]  # "system" uses system resolver, or list IPs: ["1.1.1.1", "8.8.8.8"]
DNS_BENCHMARK_HISTORY_SIZE = 50  # Number of queries to keep for statistics
```

Monitors multiple DNS record types simultaneously using `dnspython`. Displays per-record-type status in the UI.

**DNS Benchmark Tests:**
- **Cached** — measures DNS response from cache (second query to same domain)
- **Uncached** — measures full recursive resolution time (unique random domain)
- **DotCom** — measures response time for popular .com domain

UI display (compact single-line with aggregate stats):
```
C:12  U:45  D:25  │ 15q avg:27 σ:3ms
```

Color-coded: green (fast), yellow (slow), red (failed). Statistics accumulate over time (min/avg/max/σ/reliability).

**Multi-Server Support:**
Configure multiple DNS servers to compare performance:
```python
DNS_BENCHMARK_SERVERS = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
```

### MTU Monitoring

```python
ENABLE_MTU_MONITORING = True
MTU_CHECK_INTERVAL = 30
MTU_ISSUE_CONSECUTIVE = 3       # Checks to confirm MTU issue
MTU_CLEAR_CONSECUTIVE = 2       # Checks to clear MTU issue
```

### Traceroute

```python
ENABLE_AUTO_TRACEROUTE = True
TRACEROUTE_TRIGGER_LOSSES = 3   # Trigger after N consecutive losses
TRACEROUTE_COOLDOWN = 60        # Min interval (seconds)
TRACEROUTE_MAX_HOPS = 15
```

### Problem & Route Analysis

```python
ENABLE_PROBLEM_ANALYSIS = True
PROBLEM_ANALYSIS_INTERVAL = 60

ENABLE_ROUTE_ANALYSIS = True
ROUTE_ANALYSIS_INTERVAL = 300
ROUTE_CHANGE_CONSECUTIVE = 2    # Detections to confirm change
```

### Hop Health Monitoring

```python
ENABLE_HOP_MONITORING = True
HOP_PING_INTERVAL = 1          # Seconds between ping cycles (all hops pinged in parallel)
HOP_PING_TIMEOUT = 0.5         # Timeout per hop ping (seconds) - 500ms recommended
HOP_REDISCOVER_INTERVAL = 600  # Seconds between automatic route re-discovery
HOP_LATENCY_GOOD = 50          # Green threshold (ms)
HOP_LATENCY_WARN = 100         # Yellow threshold (ms), above = red
```

### Logging

```python
LOG_FILE = "ping_monitor.log"
LOG_LEVEL = "INFO"
LOG_TRUNCATE_ON_START = True    # Clear log on each start
```

### Metrics & Health

```python
ENABLE_METRICS = True
METRICS_PORT = 8000

ENABLE_HEALTH_ENDPOINT = True
HEALTH_PORT = 8001
```

## Interface

The dashboard is split into a **header**, **status bar**, **3-row body**, and **footer**:

```
┌─────────────── Network Monitor → 8.8.8.8 │ 10:35:21 ───────────────┐
╔══ ● CONNECTED │ Ping: 12.3ms │ Loss: 0.0% │ Uptime: 2h 15m ══════╗
┌─ LATENCY ───────────────┐  ┌─ STATISTICS ─────────────┐
│ Current/Best/Avg/Peak  │  │ Sent/OK/Lost + bars      │
│ Sparkline chart ▁▂▃▅▃▂ │  │ ██████████████████░░ 99.9% │
└────────────────────────┘  └──────────────────────────┘
┌─ ANALYSIS ─────────────┐  ┌─ MONITORING ─────────────┐
│ ─── Problems ────────  │  │ ─── DNS ───────────────  │
│ Type/Prediction/Pattern│  │ A✓ AAAA✓ MX✓ TXT✓ NS✓   │
│ ─── Route ───────────  │  │ C:12  U:45  D:25  │ 15q  │
│ Status/Hops/Changes    │  │ ─── Network ─────────── │
└────────────────────────┘  │ TTL/MTU/Traceroute      │
                            │ ─── Notifications ───── │
                            │ No alerts.              │
                            └──────────────────────────┘
┌─ HOP HEALTH ───────────────────────────────────────────┐
│  #   Min       Avg       Last      Loss    Host              │
│  1   14 ms     14 ms     13 ms     0.0%    10.0.0.1          │
│  2   14 ms     14 ms     14 ms     0.0%    69.30.89.2        │
│  3   15 ms     14 ms     14 ms     0.0%    hostname [1.2.3.4]│
└───────────────────────────────────────────────────────┘
```

- **Status bar** — instant connection state (CONNECTED / DEGRADED / DISCONNECTED) with key metrics
- **Latency panel** — current/best/avg/peak/median/jitter + sparkline chart
- **Statistics panel** — packet counters + Unicode progress bars for success rate and 30-min loss
- **Analysis panel** — problem type, prediction, pattern + route analysis (with section dividers)
- **Monitoring panel** — DNS records, benchmark (C/U/D), network metrics, notifications (with section dividers)
- **Hop Health panel** — full-width traceroute-style table with color-coded latency per hop

## Docker

### Build & Run

```bash
docker compose up -d
```

### Services

| Service | Port | Description |
|---|---|---|
| `pinger` | 8000 | Prometheus metrics |
| `pinger` | 8001 | Health endpoints (`/health`, `/ready`) |
| `prometheus` | 9090 | Prometheus UI |

### Volumes

| Host path | Container path | Description |
|---|---|---|
| `./logs` | `/app/logs` | Log files |
| `./traceroutes` | `/app/traceroutes` | Traceroute output files |

## Kubernetes (Helm)

```bash
helm install pinger ./charts/pinger -f charts/pinger/values.yaml
```

See [`charts/pinger/README.md`](charts/pinger/README.md) for details.

## Project Structure

```
_pinger/
├── pinger.py                  # Entry point (dependency check + launch)
├── main.py                    # Async app runner (PingerApp)
├── config.py                  # Configuration, LANG dict, types
├── monitor.py                 # Main monitoring orchestrator
├── ui.py                      # Terminal UI (Rich)
├── alerts.py                  # Sound & visual alert system
├── stats_repository.py        # Thread-safe stats storage + snapshots
├── problem_analyzer.py        # Problem classification & prediction
├── route_analyzer.py          # Traceroute parsing & route analysis
├── requirements.txt           # Python dependencies
│
├── services/                  # Service layer
│   ├── ping_service.py        # System ping / pythonping fallback
│   ├── dns_service.py         # DNS resolution monitoring
│   ├── mtu_service.py         # MTU / Path MTU discovery
│   ├── ip_service.py          # Public IP + geo info
│   ├── traceroute_service.py  # Traceroute execution & file saving
│   └── hop_monitor_service.py # Hop discovery & per-hop ping monitoring
│
├── infrastructure/            # Infrastructure layer
│   ├── metrics.py             # Prometheus counters/gauges
│   └── health.py              # HTTP health server
│
├── pinger/                    # Bootstrap package
│   └── __init__.py            # Dependency checker
│
├── traceroutes/               # Traceroute output files (auto-created)
├── assets/                    # Screenshots and documentation images
├── charts/pinger/             # Helm chart
├── prometheus/                # Prometheus config
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Localization

The app supports full **Russian** and **English** localization. All user-facing strings use the `t("key")` function from `config.py`.

To switch language:

```python
# config.py
CURRENT_LANGUAGE = "en"  # or "ru"
```

## License

MIT
