<div align="center">

# Pinger

**Asynchronous network monitoring with real-time terminal interface**

[🇷🇺 Русский](README.ru.md) · [🇬🇧 English](README.md)

<p align="center">
  <a href="https://pypi.org/project/network-pinger/"><img src="https://img.shields.io/pypi/v/network-pinger?color=blue&label=PyPI" alt="PyPI"></a>
  <a href="python.org"><img src="https://img.shields.io/pypi/pyversions/network-pinger" alt="Python Versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/meshlg/_pinger" alt="License"></a>
  <a href=""><img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey" alt="Platforms"></a>
  <br>
  <a href="https://github.com/meshlg/_pinger/stargazers"><img src="https://img.shields.io/github/stars/meshlg/_pinger?style=social" alt="GitHub Stars"></a>
  <a href="https://github.com/meshlg/_pinger/network"><img src="https://img.shields.io/github/forks/meshlg/_pinger?style=social" alt="GitHub Forks"></a>
  <a href="https://github.com/meshlg/_pinger/issues"><img src="https://img.shields.io/github/issues/meshlg/_pinger" alt="GitHub Issues"></a>
  <a href="https://pypi.org/project/network-pinger/"><img src="https://img.shields.io/pypi/dm/network-pinger" alt="PyPI Downloads"></a>
</p>

<p><em>Asynchronous network monitoring tool with Rich-based terminal interface, smart alerts, DNS benchmarks, hop health tracking, and automatic problem diagnosis.</em></p>

<p>
  <a href="#quick-start"><kbd>✴︎ Quick Start</kbd></a>
  <a href="#features"><kbd>▣ Features</kbd></a>
  <a href="#configuration"><kbd>⚒︎ Configuration</kbd></a>
  <a href="#deployment"><kbd>⚓︎ Deployment</kbd></a>
</p>

<div align="center">
  <sub>Real-time metrics · Smart alerts · DNS analytics · Prometheus-ready</sub>
</div>

![Pinger Interface](assets/screenshot.jpg)

</div>

> **Works everywhere:** Windows, Linux, and macOS with system `ping` and `traceroute` (`tracert` on Windows) commands.

---

## About

**Pinger** is a professional real-time network connection monitoring tool designed for system administrators, DevOps engineers, and enthusiasts who value network reliability and transparency.

### Key Benefits

| Benefit | Description |
|---------|-------------|
| **Real-time monitoring** | Visualization of latency, packet loss, jitter, and p95 metrics with updates every second |
| **Intuitive terminal interface** | Beautiful UI based on Rich library with color-coded statuses and progress bars |
| **Flexible configuration** | All settings via environment variables — easy to adapt to any requirements |
| **Multi-level diagnostics** | Automatic problem source detection (ISP/local network/DNS/MTU) based on patterns |
| **Prometheus integration** | Native metrics support for monitoring and alerting |
| **Docker/Kubernetes ready** | Helm chart and docker-compose for quick container deployment |
| **Localization** | Russian and English language support with automatic detection |
| **Security** | Mandatory authentication for public health endpoints |

### Who is this for

- **System administrators** — monitoring network infrastructure status
- **DevOps engineers** — integration with monitoring systems (Prometheus, Grafana)
- **Developers** — debugging network problems and routing analysis
- **Enthusiasts** — visualizing home connection quality

---

## Quick Start

> [!IMPORTANT]
> Python 3.10+ is required, as well as system `ping` and `traceroute` (`tracert` on Windows) commands.

### Installation via pipx (recommended)

```bash
pipx install network-pinger
pinger
```

Press `Ctrl+C` to stop gracefully.

```bash
pipx upgrade network-pinger
```

### Installation via pip

```bash
python -m pip install --upgrade network-pinger
pinger
```

### Installation from source

```bash
git clone https://github.com/meshlg/_pinger.git
cd _pinger
pip install -r requirements.txt
python pinger.py
```

---

## Features

Six real-time panels track your connection status — from edge latency to route analysis.

### ✴︎ Ping Monitoring

- Real-time metrics: current / best / average / peak / median / jitter / p95
- Dual sparkline charts and Unicode progress bars for drift visualization
- Packet loss detection with consecutive loss counter and p95 latency metric

### ✧ DNS Monitoring and Benchmarking

- Parallel monitoring of A, AAAA, CNAME, MX, TXT, and NS records
- Built-in test suite for benchmarking:

| Test | What it measures |
|------|------------------|
| **Cached** | DNS response from cache (repeat query) |
| **Uncached** | Full recursive resolution with random subdomain |
| **DotCom** | Response time of popular .com domain |

- Statistics: minimum / average / maximum / standard deviation / reliability
- Color badges: green (fast) / yellow (slow) / red (error)
- Comparison of multiple DNS resolvers in parallel

### ⚑ Smart Alerts

- Audio + visual alerts for latency, jitter, packet loss, and connection drops
- Hysteresis to prevent flickering — alerts trigger only on state changes
- Cooldown timers to prevent alert spam
- Alert feed with timestamps for problem correlation

### ✪ Problem Analysis and Prediction

- Automatic problem classification: ISP / local network / DNS / MTU
- Detection of recurring incidents and prediction of their return
- Route context plus loss/jitter trends for quick root cause identification

### ⌁ Hop Health Monitoring

- Hop discovery via traceroute, then parallel ping of each hop
- Table with minimum / average / last latency and loss for each hop
- Color coding: green (good) / yellow (slow) / red (unreachable)
- Perfect for identifying congestion or shaping on specific path segments

### ☲ Route Analysis

- Route change detection with configurable sensitivity and cooldown timers
- Automatic traceroute snapshot saving to `traceroutes/` directory on problems
- Helps prove routing changes when contacting ISP support

### ⌂ Network Metrics

- **Public IP** — change tracking with geolocation and AS information
- **MTU / Path MTU** — detection and packet fragmentation
- **TTL** — hop count estimation and anomaly detection

### ▤ Observability

- **`/metrics`** — Prometheus endpoint on port 8000 for metrics collection
- **`/health`** and **`/ready`** — health probes on port 8001 for Kubernetes/Docker
- Docker + Helm manifests for container deployment

### ☷ Localization

- Automatic system locale detection with **Russian** and **English** language support
- Language override in `config.py`:

```python
# config.py
CURRENT_LANGUAGE = "en"  # or "ru"
```

---

## Interface

> [!NOTE]
> Each panel updates in real-time. Match the screenshot above with this map for quick orientation.

### 1. Header and Status Bar

- Target IP, version with update indicator, connection lamp (● Connected / ▲ Degraded / ✕ Disconnected), and uptime
- Current ping, 30-minute loss, uptime, and public IP

### 2. Latency Panel

- Current / best / average / peak / median / jitter / p95 metric
- Dual sparkline charts for latency and jitter with last value tracking

### 3. Statistics Panel

- Packet counters: sent / successful / lost
- Success percentage and 30-minute loss
- Progress bars and mini trends panel (30m loss, jitter trend, hop count)

### 4. Analysis Panel

- Problem classifier (ISP / local network / DNS / MTU / unknown)
- Forecast (stable / risk of problems)
- Problem pattern
- Route stability (changed / stable) and last change time

### 5. Monitoring Panel

- DNS record health (A, AAAA, CNAME, MX, TXT, NS)
- Benchmarking tiles (Cached / Uncached / DotCom) with statistics
- MTU / Path MTU / TTL status and fragmentation
- Active alerts feed

### 6. Hop Health Panel

- Per-hop table with minimum / average / last latency and loss
- Color coding for instant quality assessment of each hop

---

## Configuration

All settings are in [`config.py`](config.py) with default values and comments.

> [!TIP]
> Copy `config.py` next to the binary file or use environment variables to keep custom settings under version control.

### ⚙︎ Basic Settings

```python
TARGET_IP = "8.8.8.8"          # Target IP for ping
INTERVAL = 1                    # Ping interval (seconds)
WINDOW_SIZE = 1800              # Statistics window (30 min)
LATENCY_WINDOW = 600            # Latency history (10 min)
```

### ⚑ Thresholds and Alerts

```python
PACKET_LOSS_THRESHOLD = 5.0     # Packet loss threshold (%)
AVG_LATENCY_THRESHOLD = 100     # Average latency threshold (ms)
JITTER_THRESHOLD = 30           # Jitter threshold (ms)
CONSECUTIVE_LOSS_THRESHOLD = 5   # Consecutive loss threshold

ENABLE_SOUND_ALERTS = True
ALERT_COOLDOWN = 5              # Minimum interval between sounds (seconds)
```

### ✧ DNS Monitoring

```python
ENABLE_DNS_MONITORING = True
DNS_TEST_DOMAIN = "cloudflare.com"
DNS_CHECK_INTERVAL = 10
DNS_SLOW_THRESHOLD = 100        # "Slow" response threshold (ms)
DNS_RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "NS"]

ENABLE_DNS_BENCHMARK = True
DNS_BENCHMARK_SERVERS = ["system"]  # or ["1.1.1.1", "8.8.8.8"]
```

### ⌂ IP / MTU / TTL

```python
ENABLE_IP_CHANGE_ALERT = True
IP_CHECK_INTERVAL = 15

ENABLE_MTU_MONITORING = True
MTU_CHECK_INTERVAL = 30
```

### ⌁ Traceroute and Hop Monitoring

```python
ENABLE_AUTO_TRACEROUTE = False   # Manual launch or on route change
TRACEROUTE_TRIGGER_LOSSES = 3
TRACEROUTE_COOLDOWN = 300
TRACEROUTE_MAX_HOPS = 15

ENABLE_HOP_MONITORING = True
HOP_PING_INTERVAL = 1
HOP_PING_TIMEOUT = 0.5
HOP_LATENCY_GOOD = 50          # Green (ms)
HOP_LATENCY_WARN = 100         # Yellow (ms), above = red
```

### ✪ Analysis

```python
ENABLE_PROBLEM_ANALYSIS = True
PROBLEM_ANALYSIS_INTERVAL = 60

ENABLE_ROUTE_ANALYSIS = True
ROUTE_ANALYSIS_INTERVAL = 1800
ROUTE_CHANGE_CONSECUTIVE = 2
```

---

## Deployment

<div align="center">
<table>
  <tr>
    <td><strong>⚓︎ Docker Compose</strong></td>
    <td><strong>♘ Kubernetes (Helm)</strong></td>
  </tr>
  <tr>
    <td>Local lab with Prometheus and health ports.</td>
    <td>Cluster readiness with values overrides for production.</td>
  </tr>
</table>
</div>

### ⚓︎ Docker Compose

```bash
docker compose up -d
```

| Service | Port | Description |
|---------|------|-------------|
| `pinger` | `8000` | Prometheus metrics (`/metrics`). |
| `pinger` | `8001` | Health probes (`/health`, `/ready`). |
| `prometheus` | `9090` | Prometheus UI. |

### ♘ Kubernetes (Helm)

```bash
helm install pinger ./charts/pinger -f charts/pinger/values.yaml
```

Need customization? See [`charts/pinger/README.md`](charts/pinger/README.md) for image tags, secrets, and upgrade notes.

---

## FAQ

### ❓ How to diagnose connection problems?

Pinger automatically classifies problems in the analysis panel:

| Problem Type | Signs | What to do |
|--------------|-------|------------|
| **ISP** | High latency on hops 2-5, packet loss on route | Contact your ISP, show traceroute snapshots |
| **Local network** | Loss on first hop, router problems | Check cable, reboot router |
| **DNS** | Slow DNS queries but normal ping by IP | Change DNS server (1.1.1.1, 8.8.8.8) |
| **MTU** | Packet fragmentation, VPN problems | Reduce MTU on interface |

### ❓ Why does ping show packet loss but internet works?

This is normal for some ISPs:
- ICMP packets may have low priority
- Some routers limit ICMP traffic
- Check loss on hops — if only on one, this may be normal

### ❓ How to configure alerts?

```python
# config.py
ENABLE_SOUND_ALERTS = True
ALERT_COOLDOWN = 5              # Minimum interval between sounds (seconds)
PACKET_LOSS_THRESHOLD = 5.0     # Packet loss threshold (%)
AVG_LATENCY_THRESHOLD = 100     # Average latency threshold (ms)
JITTER_THRESHOLD = 30           # Jitter threshold (ms)
```

### ❓ How to integrate with Prometheus?

Pinger provides metrics on port 8000:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'pinger'
    static_configs:
      - targets: ['localhost:8000']
```

### ❓ How to use in Kubernetes?

```bash
helm install pinger ./charts/pinger -f charts/pinger/values.yaml
```

Health endpoints are available on port 8001:
- `/health` — health check
- `/ready` — readiness check

### ❓ How to change interface language?

```python
# config.py
CURRENT_LANGUAGE = "en"  # or "ru"
```

Language is detected automatically based on system locale.

### ❓ How to save monitoring results?

Pinger automatically saves traceroute snapshots on problems to `traceroutes/` directory. For persistent logging, use Prometheus.

### ❓ How to run in background?

```bash
# Linux/macOS
nohup pinger > pinger.log 2>&1 &

# Windows
start /B pinger > pinger.log 2>&1
```

### ❓ How to check health endpoints?

```bash
# Health check
curl http://localhost:8001/health

# Readiness check
curl http://localhost:8001/ready

# Prometheus metrics
curl http://localhost:8000/metrics
```

### ❓ How to configure authentication for health endpoints?

```bash
# Basic Auth
export HEALTH_AUTH_USER=admin
export HEALTH_AUTH_PASS=secret

# Token Auth
export HEALTH_TOKEN=your-secret-token
export HEALTH_TOKEN_HEADER=X-Health-Token
```

See [`SECURITY.md`](SECURITY.md) for more details.

---

## For Developers

```bash
pip install poetry
git clone https://github.com/meshlg/_pinger.git
cd _pinger
poetry install
poetry run pinger
```

1. Use Poetry for isolated environments and pinned dependencies.
2. Run `poetry run pytest` before opening a PR.
3. Follow [CONTRIBUTING.md](CONTRIBUTING.md) for releases and tagging (remember git tags for update notifications).

---

<div align="center">

**[MIT License](LICENSE)** · 2026 © meshlg  
✉︎ [Join Discord](https://discordapp.com/users/268440099828662274) · ⚑ [Report an issue](https://github.com/meshlg/_pinger/issues/new/choose) · ☆ [Star the repo](https://github.com/meshlg/_pinger/stargazers)

</div>
