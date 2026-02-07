<div align="center">

# Pinger

**Real-time network monitoring in your terminal**

[![PyPI](https://img.shields.io/pypi/v/network-pinger?color=blue&label=PyPI)](https://pypi.org/project/network-pinger/)
[![Python](https://img.shields.io/pypi/pyversions/network-pinger)](https://python.org)
[![License](https://img.shields.io/github/license/meshlg/_pinger)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)]()

Async network monitoring tool with Rich-based terminal dashboard, smart alerts, DNS benchmarks, hop-by-hop health tracking, and automatic problem diagnosis.

![Pinger Interface](assets/screenshot.jpg)

</div>

---

## Highlights

|  |  |  |
|:---:|:---:|:---:|
| **Ping & Latency** | **DNS Benchmark** | **Hop Health** |
| Sparkline charts, jitter, loss trends | Cached / Uncached / DotCom tests | Per-hop latency & loss in real time |
| **Smart Alerts** | **Problem Analysis** | **Route Tracking** |
| Sound + visual, threshold hysteresis | ISP / local / DNS / MTU auto-diagnosis | Change detection, auto traceroute |

---

## Quick Start

```bash
pipx install network-pinger
pinger
```

> **Requires:** Python 3.10+ and system `ping` / `traceroute` (`tracert` on Windows).

Press `Ctrl+C` for graceful shutdown.

### Upgrading

```bash
pipx upgrade network-pinger
```

The app checks for new versions on startup and shows a notification if an update is available:

![Update Notification](assets/update.jpg)

### Alternative Install

```bash
pip install network-pinger
# or from source
pip install -r requirements.txt && python pinger.py
```

---

## Features

### Ping Monitoring
Real-time latency tracking with current / best / average / peak / median / jitter metrics. Sparkline charts and Unicode progress bars give you an instant visual overview. Packet loss detection with consecutive loss counter.

### DNS Monitoring & Benchmark
Monitors multiple record types simultaneously (A, AAAA, CNAME, MX, TXT, NS). Built-in benchmark suite:

| Test | What it measures |
|---|---|
| **Cached** | DNS response from cache (repeat query) |
| **Uncached** | Full recursive resolution (random domain) |
| **DotCom** | Response time for a popular .com domain |

Statistics: min / avg / max / sigma / reliability. Color-coded: green (fast), yellow (slow), red (failed). Supports multiple DNS servers for comparison:

```python
DNS_BENCHMARK_SERVERS = ["system", "1.1.1.1", "8.8.8.8"]
```

### Smart Alerts
Sound and visual notifications with configurable thresholds for packet loss, latency, jitter, and connection loss. Threshold hysteresis prevents alert flickering. Cooldown system avoids spam.

### Problem Analysis & Prediction
Automatic classification of network issues: **ISP**, **local network**, **DNS**, or **MTU**. Pattern detection identifies recurring problems. Predictive engine estimates when issues may return.

### Hop Health Monitoring
Automatic hop discovery via traceroute. Periodic parallel ping of every intermediate hop. Full table with min / avg / last latency and loss per hop, color-coded by severity.

### Route Analysis
Traceroute-based hop comparison over time. Detects route changes with configurable sensitivity. Auto-saves traceroute results to `traceroutes/` on connection problems.

### Network Metrics
- **Public IP** — change detection with geo info (city, ISP, AS)
- **MTU / Path MTU** — discovery, fragmentation detection
- **TTL** — monitoring and hop count estimation

### Observability
- **Prometheus** — `/metrics` endpoint on port `8000`
- **Health** — `/health` and `/ready` endpoints on port `8001`
- **Docker & Helm** — production-ready deployment

### Localization
Automatically detected from system locale. Supports **Russian** and **English**.

```python
# Override in config.py if needed
CURRENT_LANGUAGE = "en"  # or "ru"
```

---

## Interface

The dashboard consists of a **header**, **status bar**, **multi-panel body**, and **footer**:

```
┌────────────── Network Monitor → 8.8.8.8  v2.1.7 ✓  10:35:21 ──────────────┐
╔══ ● CONNECTED  │  Ping: 12.3ms  │  Loss: 0.0%  │  Uptime: 2h 15m ════════╗
┌─ LATENCY ─────────────────┐  ┌─ STATISTICS ──────────────┐
│ Current  12 ms   Best 8 ms│  │ Sent    5400    ██████████ │
│ Average  14 ms   Peak 45ms│  │ OK      5398    99.96%     │
│ Median   13 ms   Jitter 3 │  │ Lost       2    ░░░░░░░░░░ │
│ ▁▂▃▂▃▅▃▂▁▂▃▂▃▅▃▂▁▂▃▂▃▅▃▂ │  │ Consecutive: 0  Max: 1     │
└───────────────────────────┘  └────────────────────────────┘
┌─ ANALYSIS ────────────────┐  ┌─ MONITORING ──────────────┐
│ ─── Problems ──────────── │  │ ─── DNS ──────────────── │
│ Type: No problems         │  │ A✓ AAAA✓ MX✓ TXT✓ NS✓   │
│ Prediction: Stable        │  │ C:12  U:45  D:25 │ avg:27│
│ ─── Route ─────────────── │  │ ─── Network ──────────── │
│ Status: Stable (6 hops)   │  │ TTL: 117  MTU: 1500 OK   │
│ Changes: 0                │  │ ─── Notifications ────── │
└───────────────────────────┘  │ No active alerts.         │
                               └────────────────────────────┘
┌─ HOP HEALTH ──────────────────────────────────────────────────┐
│  #   Min       Avg       Last      Loss    Host               │
│  1   1 ms      1 ms      1 ms      0.0%    192.168.1.1        │
│  2   14 ms     14 ms     13 ms     0.0%    10.0.0.1           │
│  3   15 ms     14 ms     14 ms     0.0%    hostname [1.2.3.4] │
└───────────────────────────────────────────────────────────────┘
```

| Panel | Description |
|---|---|
| **Status bar** | Connection state (CONNECTED / DEGRADED / DISCONNECTED), key metrics |
| **Latency** | Current / best / avg / peak / median / jitter + sparkline chart |
| **Statistics** | Packet counters, success rate with progress bars |
| **Analysis** | Problem type & prediction + route status |
| **Monitoring** | DNS records, benchmark, TTL/MTU, notifications |
| **Hop Health** | Per-hop latency & loss table, color-coded |

---

## Configuration

All settings are in `config.py`. Here are the key options:

<details>
<summary><b>Core</b></summary>

```python
TARGET_IP = "8.8.8.8"          # Ping target
INTERVAL = 1                    # Ping interval (seconds)
WINDOW_SIZE = 1800              # Stats window (30 min)
LATENCY_WINDOW = 600            # Latency history (10 min)
```
</details>

<details>
<summary><b>Thresholds & Alerts</b></summary>

```python
PACKET_LOSS_THRESHOLD = 5.0     # Packet loss warning (%)
AVG_LATENCY_THRESHOLD = 100     # Average latency warning (ms)
JITTER_THRESHOLD = 30           # Jitter warning (ms)
CONSECUTIVE_LOSS_THRESHOLD = 5  # Consecutive lost packets

ENABLE_SOUND_ALERTS = True
ALERT_COOLDOWN = 5              # Min interval between sounds (seconds)
```
</details>

<details>
<summary><b>DNS Monitoring</b></summary>

```python
ENABLE_DNS_MONITORING = True
DNS_TEST_DOMAIN = "cloudflare.com"
DNS_CHECK_INTERVAL = 10
DNS_SLOW_THRESHOLD = 100        # "Slow" threshold (ms)
DNS_RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "NS"]

ENABLE_DNS_BENCHMARK = True
DNS_BENCHMARK_SERVERS = ["system"]  # or ["1.1.1.1", "8.8.8.8"]
```
</details>

<details>
<summary><b>IP / MTU / TTL</b></summary>

```python
ENABLE_IP_CHANGE_ALERT = True
IP_CHECK_INTERVAL = 15

ENABLE_MTU_MONITORING = True
MTU_CHECK_INTERVAL = 30
```
</details>

<details>
<summary><b>Traceroute & Hop Monitoring</b></summary>

```python
ENABLE_AUTO_TRACEROUTE = True
TRACEROUTE_TRIGGER_LOSSES = 3
TRACEROUTE_COOLDOWN = 60
TRACEROUTE_MAX_HOPS = 15

ENABLE_HOP_MONITORING = True
HOP_PING_INTERVAL = 1
HOP_PING_TIMEOUT = 0.5
HOP_LATENCY_GOOD = 50          # Green (ms)
HOP_LATENCY_WARN = 100         # Yellow (ms), above = red
```
</details>

<details>
<summary><b>Analysis</b></summary>

```python
ENABLE_PROBLEM_ANALYSIS = True
PROBLEM_ANALYSIS_INTERVAL = 60

ENABLE_ROUTE_ANALYSIS = True
ROUTE_ANALYSIS_INTERVAL = 300
ROUTE_CHANGE_CONSECUTIVE = 2
```
</details>

<details>
<summary><b>Logging & Metrics</b></summary>

```python
LOG_FILE = "~/.pinger/ping_monitor.log"
LOG_LEVEL = "INFO"
LOG_TRUNCATE_ON_START = True

ENABLE_METRICS = True           # Prometheus on :8000
ENABLE_HEALTH_ENDPOINT = True   # Health on :8001
```
</details>

---

## Deployment

### Docker

```bash
docker compose up -d
```

| Service | Port | Description |
|---|---|---|
| `pinger` | `8000` | Prometheus metrics |
| `pinger` | `8001` | Health (`/health`, `/ready`) |
| `prometheus` | `9090` | Prometheus UI |

### Kubernetes (Helm)

```bash
helm install pinger ./charts/pinger -f charts/pinger/values.yaml
```

See [`charts/pinger/README.md`](charts/pinger/README.md) for details.

---

## For Developers

```bash
pip install poetry
git clone https://github.com/meshlg/_pinger.git
cd _pinger && poetry install
poetry run pinger
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for building, publishing, and contribution guidelines.

---

<div align="center">

**[MIT License](LICENSE)** · Made with Rich

</div>
