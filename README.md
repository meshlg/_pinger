<div align="center">

# Pinger

**Real-time network monitoring in your terminal**

<p align="center">
  <a href="https://pypi.org/project/network-pinger/"><img src="https://img.shields.io/pypi/v/network-pinger?color=blue&label=PyPI" alt="PyPI"></a>
  <a href="https://python.org"><img src="https://img.shields.io/pypi/pyversions/network-pinger" alt="Python Versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/meshlg/_pinger" alt="License"></a>
  <a href=""><img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey" alt="Platforms"></a>
  <br>
  <a href="https://github.com/meshlg/_pinger/stargazers"><img src="https://img.shields.io/github/stars/meshlg/_pinger?style=social" alt="GitHub Stars"></a>
  <a href="https://github.com/meshlg/_pinger/network"><img src="https://img.shields.io/github/forks/meshlg/_pinger?style=social" alt="GitHub Forks"></a>
  <a href="https://github.com/meshlg/_pinger/issues"><img src="https://img.shields.io/github/issues/meshlg/_pinger" alt="GitHub Issues"></a>
  <a href="https://pypi.org/project/network-pinger/"><img src="https://img.shields.io/pypi/dm/network-pinger" alt="PyPI Downloads"></a>
</p>

<p><em>Async network monitoring tool with Rich-based terminal dashboard, smart alerts, DNS benchmarks, hop-by-hop health tracking, and automatic problem diagnosis.</em></p>

<p>
  <a href="#quick-start"><kbd>✴︎ Quick Start</kbd></a>
  <a href="#features"><kbd>▣ Feature Tour</kbd></a>
  <a href="#configuration"><kbd>⚒︎ Configure</kbd></a>
</p>

<div align="center">
  <sub>Live metrics · Smart alerts · DNS insights · Prometheus-ready observability</sub>
</div>

![Pinger Interface](assets/screenshot.jpg)

</div>

> **Works everywhere:** Windows, Linux, and macOS with system `ping` + `traceroute` (`tracert` on Windows).

---

## Highlights

<div align="center">
<table>
  <tr>
    <td><strong>✴︎ Ping & Latency</strong><br><small>Dual sparklines, jitter tracking, loss trends, and p95 insight.</small></td>
    <td><strong>✧ DNS Benchmark</strong><br><small>Cached / Uncached / DotCom tests with side-by-side providers.</small></td>
    <td><strong>⌁ Hop Health</strong><br><small>Traceroute-aware per-hop latency & loss heatmap.</small></td>
  </tr>
  <tr>
    <td><strong>⚑ Smart Alerts</strong><br><small>Sound + visual notifications with hysteresis & cooldowns.</small></td>
    <td><strong>✪ Problem Analysis</strong><br><small>Auto-diagnosis of ISP vs local vs DNS vs MTU issues.</small></td>
    <td><strong>☲ Route Tracking</strong><br><small>Change detection and auto traceroute when paths shift.</small></td>
  </tr>
</table>
</div>

---

## Quick Start

> [!IMPORTANT]
> Python 3.10+ required plus system `ping` and `traceroute` (`tracert` on Windows).

<details open>
<summary><b>✴︎ pipx (recommended)</b></summary>

```bash
pipx install network-pinger
pinger
```

Press `Ctrl+C` for graceful shutdown.

```bash
pipx upgrade network-pinger
```

</details>

<details>
<summary><b>▣ pip</b></summary>

```bash
python -m pip install --upgrade network-pinger
pinger
```

</details>

<details>
<summary><b>⚒︎ From source</b></summary>

```bash
git clone https://github.com/meshlg/_pinger.git
cd _pinger
pip install -r requirements.txt
python pinger.py
```

</details>

> [!TIP]
> The app checks for new releases on startup and surfaces a Rich notification when an update is available.

![Update Notification](assets/update.jpg)

---

## Features

Six live panels keep the pulse of your link—from edge latency to observability endpoints.

### ✴︎ Ping Monitoring
- Real-time current / best / average / peak / median / jitter metrics.
- Dual sparklines + Unicode progress bars for at-a-glance drift detection.
- Packet-loss detection with consecutive loss counter and p95 latency insight.

### ✧ DNS Monitoring & Benchmark
- Parallel monitoring of A, AAAA, CNAME, MX, TXT, and NS records.
- Built-in benchmark suite:

| Test | What it measures |
|---|---|
| **Cached** | DNS response from resolver cache (repeat query). |
| **Uncached** | Full recursive resolution using a random hostname. |
| **DotCom** | Response time for a popular .com domain. |

- Statistics: min / avg / max / σ / reliability with green (fast) / yellow (slow) / red (failed) badges.
- Compare multiple providers side-by-side:

```python
DNS_BENCHMARK_SERVERS = ["system", "1.1.1.1", "8.8.8.8"]
```

### ⚑ Smart Alerts
- Audio + visual alerts for latency, jitter, packet loss, and disconnects.
- Threshold hysteresis stops flicker; cooldown timers prevent alert spam.
- Alert feed keeps timestamps so you can correlate issues later.

### ✪ Problem Analysis & Prediction
- Auto-tags outages as ISP / local / DNS / MTU failures using signal patterns.
- Looks for repeating incidents and forecasts when they may return.
- Route context plus loss/jitter trends clarify root causes quickly.

### ⌁ Hop Health Monitoring
- Discovers hops via traceroute, then pings each hop in parallel.
- Table shows min / avg / last latency and per-hop loss with severity colors.
- Great for spotting where congestion or shaping occurs along the path.

### ☲ Route Analysis
- Detects route changes with configurable sensitivity + cooldowns.
- Auto-saves traceroute snapshots into `traceroutes/` when trouble hits.
- Helps prove upstream routing shifts when filing ISP tickets.

### ⌂ Network Metrics
- **Public IP** change detection with geo/IP-AS lookups.
- **MTU / Path MTU** discovery plus fragmentation detection.
- **TTL** monitoring for hop-count estimation and anomaly detection.

### ▤ Observability
- `/metrics` Prometheus endpoint on port `8000` for scraping.
- `/health` + `/ready` endpoints on port `8001` for probes.
- Docker + Helm manifests cover local labs through full clusters.

### ☷ Localization
- Auto-detects system locale with **Russian** and **English** packs ready.
- Override anytime in `config.py`:

```python
# config.py
CURRENT_LANGUAGE = "en"  # or "ru"
```

---

## Interface Tour

> [!NOTE]
> Every panel refreshes live; pair the screenshot above with this map to orient yourself quickly.

1. **Header & Status Bar** — Target IP, version badge + updater, connection lamp (● Connected / ▲ Degraded / ✕ Disconnected), and session uptime.
2. **Latency Panel** — Current / best / avg / peak / median latency, jitter, p95, and dual sparklines tracking the last minutes of activity.
3. **Statistics Panel** — Packet counters (sent / ok / lost), Unicode success bars, and a mini-trends strip (loss 30 m, jitter trend, hop count).
4. **Analysis Panel** — Problem classifier result, prediction badge, and route stability indicator with change counters.
5. **Monitoring Panel** — DNS record health, benchmark tiles, TTL / MTU / fragmentation state, and live alert feed.
6. **Hop Health Panel** — Per-hop min / avg / last latency + loss, color-coded (green / yellow / red) for instant hotspot spotting.

| Panel | Signals you watch |
|---|---|
| **Status bar** | Connection state, target, uptime, current KPIs |
| **Latency** | Distribution metrics, jitter, sparklines |
| **Statistics** | Packet counts, success %, trends |
| **Analysis** | Root-cause classification, prediction, route state |
| **Monitoring** | DNS, benchmark, network stats, notifications |
| **Hop Health** | Hop-by-hop latency & loss matrix |

---

## Configuration

All knobs live in [`config.py`](config.py)—versioned defaults with inline comments.

> [!TIP]
> Copy `config.py` next to your binary or set env vars to keep custom tweaks under version control.

<details>
<summary><b>⚙︎ Core</b></summary>

```python
TARGET_IP = "8.8.8.8"          # Ping target
INTERVAL = 1                    # Ping interval (seconds)
WINDOW_SIZE = 1800              # Stats window (30 min)
LATENCY_WINDOW = 600            # Latency history (10 min)
```
</details>

<details>
<summary><b>⚑ Thresholds & Alerts</b></summary>

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
<summary><b>✧ DNS Monitoring</b></summary>

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
<summary><b>⌂ IP / MTU / TTL</b></summary>

```python
ENABLE_IP_CHANGE_ALERT = True
IP_CHECK_INTERVAL = 15

ENABLE_MTU_MONITORING = True
MTU_CHECK_INTERVAL = 30
```
</details>

<details>
<summary><b>⌁ Traceroute & Hop Monitoring</b></summary>

```python
ENABLE_AUTO_TRACEROUTE = False   # Manual trigger or on route change
TRACEROUTE_TRIGGER_LOSSES = 3
TRACEROUTE_COOLDOWN = 300
TRACEROUTE_MAX_HOPS = 15

ENABLE_HOP_MONITORING = True
HOP_PING_INTERVAL = 1
HOP_PING_TIMEOUT = 0.5
HOP_LATENCY_GOOD = 50          # Green (ms)
HOP_LATENCY_WARN = 100         # Yellow (ms), above = red
```
</details>

<details>
<summary><b>✪ Analysis</b></summary>

```python
ENABLE_PROBLEM_ANALYSIS = True
PROBLEM_ANALYSIS_INTERVAL = 60

ENABLE_ROUTE_ANALYSIS = True
ROUTE_ANALYSIS_INTERVAL = 1800
ROUTE_CHANGE_CONSECUTIVE = 2
```
</details>

<details>
<summary><b>▤ Logging & Metrics</b></summary>

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

<div align="center">
<table>
  <tr>
    <td><strong>⚓︎ Docker Compose</strong></td>
    <td><strong>♘ Kubernetes (Helm)</strong></td>
  </tr>
  <tr>
    <td>Local lab setup with baked-in Prometheus + health ports.</td>
    <td>Cluster-ready chart with values overrides for prod.</td>
  </tr>
</table>
</div>

### ⚓︎ Docker Compose

```bash
docker compose up -d
```

| Service | Port | Description |
|---|---|---|
| `pinger` | `8000` | Prometheus metrics (`/metrics`). |
| `pinger` | `8001` | Health probes (`/health`, `/ready`). |
| `prometheus` | `9090` | Prometheus UI. |

### ♘ Kubernetes (Helm)

```bash
helm install pinger ./charts/pinger -f charts/pinger/values.yaml
```

Need tweaks? See [`charts/pinger/README.md`](charts/pinger/README.md) for image tags, secrets, and upgrade notes.

---

## For Developers

```bash
pip install poetry
git clone https://github.com/meshlg/_pinger.git
cd _pinger
poetry install
poetry run pinger
```

1. Use Poetry for isolated envs and locked deps.
2. Run `poetry run pytest` before opening a PR.
3. Follow [CONTRIBUTING.md](CONTRIBUTING.md) for release + tagging (remember to push git tags for update notifications).

---

<div align="center">

**[MIT License](LICENSE)** · 2026 © meshlg  
✉︎ [Join the Discord](https://discordapp.com/users/268440099828662274) · ⚑ [Report an issue](https://github.com/meshlg/_pinger/issues/new/choose) · ☆ [Star the repo](https://github.com/meshlg/_pinger)

</div>
