#!/usr/bin/env python3
"""
Demo mode script for creating screenshots without exposing real data.

Displays realistic fake data for documentation and promotional materials.

Safe for screenshots - all data is fake!
"""

import sys
import time
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

# Add project to path FIRST
sys.path.insert(0, ".")

# IMPORTANT: config/__init__.py loads i18n, which captures CURRENT_LANGUAGE value
# So we must also patch the i18n module's copy
import config.i18n
config.i18n.CURRENT_LANGUAGE = "en"

# Monkeypatch t() to force English (robust against variable capture)
# This ensures that even if t() was already created with "ru", we replace it
# with a version that strictly uses the English dictionary.
_original_LANG = config.i18n.LANG

def _forced_en_t(key: str) -> str:
    """Force English translation."""
    return _original_LANG.get("en", {}).get(key, key)

config.i18n.t = _forced_en_t
config.t = _forced_en_t

# Now import everything else
from rich.console import Console
from rich.live import Live

from config import t
from ui import MonitorUI
from ui_protocols.protocols import StatsDataProvider


class FakeDNSBenchmark:
    """Fake DNS benchmark data."""

    def get_stats(self) -> dict:
        return {
            "cached": {
                "success": True,
                "response_time_ms": 8.2,
                "status": t("ok"),
                "avg_ms": 8.5,
                "std_dev": 1.2,
                "queries": 127,
            },
            "uncached": {
                "success": True,
                "response_time_ms": 42.1,
                "status": t("ok"),
                "avg_ms": 40.8,
                "std_dev": 3.5,
                "queries": 127,
            },
            "dotcom": {
                "success": True,
                "response_time_ms": 18.2,
                "status": t("ok"),
                "avg_ms": 17.9,
                "std_dev": 2.1,
                "queries": 127,
            },
        }


class FakeStatsProvider(StatsDataProvider):
    """Provides fake stats for demo mode implementing StatsDataProvider protocol."""

    def __init__(self, scenario: str = "normal"):
        """
        Initialize with a scenario.

        Scenarios:
        - normal: Good connection, no issues
        - degraded: High latency, some packet loss
        - problems: Connection issues, route changes
        - alerts: Multiple active alerts
        """
        self.scenario = scenario
        self.start_time = datetime.now(timezone.utc) - timedelta(hours=2, minutes=34, seconds=12)
        self.dns_benchmark = FakeDNSBenchmark()
        self._lock = threading.Lock()

        # Generate STATIC data once — no randomness, no flickering
        if scenario == "degraded":
            self._setup_degraded()
        elif scenario == "problems":
            self._setup_problems()
        elif scenario == "alerts":
            self._setup_alerts()
        else:
            self._setup_normal()

    # ── Scenario setups ──────────────────────────────────────────────────────

    def _setup_normal(self):
        """Normal operation — good connection."""
        self._latencies = deque([12.5, 12.3, 12.8, 11.9, 13.1] * 120, maxlen=600)
        self._recent_results = deque([True] * 1750 + [False] * 50, maxlen=1800)
        self._jitter_history = deque([1.2, 1.1, 1.4, 1.0, 1.3] * 20, maxlen=100)
        self._packet_loss_30m = 2.8
        self._consecutive_losses = 0
        self._max_consecutive_losses = 2
        self._active_alerts: list[dict] = []
        self._problem_type = "none"
        self._route_changed = False
        self._threshold_connection_lost = False
        self._threshold_high_latency = False
        self._threshold_high_jitter = False
        self._threshold_high_loss = False

    def _setup_degraded(self):
        """Degraded performance — high latency."""
        self._latencies = deque([45.8, 42.1, 50.3, 47.2, 43.9, 52.1] * 100, maxlen=600)
        self._recent_results = deque([True] * 1600 + [False] * 200, maxlen=1800)
        self._jitter_history = deque([8.5, 7.8, 9.2, 8.1, 10.3] * 20, maxlen=100)
        self._packet_loss_30m = 11.2
        self._consecutive_losses = 2
        self._max_consecutive_losses = 5
        self._active_alerts = [
            {"message": t("alert_high_avg_latency").format(val=52.3), "type": "warning", "time": datetime.now(timezone.utc) - timedelta(minutes=5)},
            {"message": t("alert_high_jitter").format(val=12.1), "type": "warning", "time": datetime.now(timezone.utc) - timedelta(minutes=3)},
        ]
        self._problem_type = "isp"
        self._route_changed = False
        self._threshold_connection_lost = False
        self._threshold_high_latency = True
        self._threshold_high_jitter = True
        self._threshold_high_loss = True

    def _setup_problems(self):
        """Connection problems — packet loss, route changes."""
        pattern = [25.0, 22.3, 28.1, 24.5, 0, 26.8, 23.2, 27.5, 21.9, 0]
        self._latencies = deque(pattern * 60, maxlen=600)
        self._recent_results = deque([True if i % 8 != 0 else False for i in range(1800)], maxlen=1800)
        self._jitter_history = deque([15.0, 12.5, 18.3, 14.1, 19.8] * 20, maxlen=100)
        self._packet_loss_30m = 18.7
        self._consecutive_losses = 4
        self._max_consecutive_losses = 8
        self._active_alerts = [
            {"message": t("alert_connection_lost").format(n=4), "type": "critical", "time": datetime.now(timezone.utc) - timedelta(seconds=30)},
            {"message": t("alert_high_loss").format(val=18.7), "type": "warning", "time": datetime.now(timezone.utc) - timedelta(minutes=2)},
        ]
        self._problem_type = "isp"
        self._route_changed = True
        self._threshold_connection_lost = True
        self._threshold_high_latency = True
        self._threshold_high_jitter = True
        self._threshold_high_loss = True

    def _setup_alerts(self):
        """Multiple active alerts."""
        self._latencies = deque([32.0, 30.5, 34.2, 31.8, 35.5, 29.3] * 100, maxlen=600)
        self._recent_results = deque([True] * 1620 + [False] * 180, maxlen=1800)
        self._jitter_history = deque([6.5, 5.8, 7.2, 6.1, 7.8] * 20, maxlen=100)
        self._packet_loss_30m = 9.8
        self._consecutive_losses = 1
        self._max_consecutive_losses = 4
        self._active_alerts = [
            {"message": "IP: 203.0.113.45 -> 203.0.113.78", "type": "info", "time": datetime.now(timezone.utc) - timedelta(minutes=15)},
            {"message": t("alert_high_loss").format(val=9.8), "type": "warning", "time": datetime.now(timezone.utc) - timedelta(minutes=8)},
            {"message": t("alert_high_jitter").format(val=9.2), "type": "warning", "time": datetime.now(timezone.utc) - timedelta(minutes=4)},
            {"message": "MTU: 1500 -> 1492", "type": "warning", "time": datetime.now(timezone.utc) - timedelta(minutes=2)},
        ]
        self._problem_type = "local"
        self._route_changed = False
        self._threshold_connection_lost = False
        self._threshold_high_latency = False
        self._threshold_high_jitter = True
        self._threshold_high_loss = True

    # ── Hop data ─────────────────────────────────────────────────────────────

    def _get_hops(self) -> list:
        """Return consistent hop data for all scenarios."""
        hops = [
            {"hop": 1, "hostname": "gateway.local", "ip": "192.168.1.1",
             "min_latency": 1.2, "avg_latency": 1.5, "last_latency": 1.4,
             "loss_pct": 0.0, "last_ok": True, "total_pings": 50},
            {"hop": 2, "hostname": "isp-gw-1.example.net", "ip": "10.20.30.1",
             "min_latency": 8.5, "avg_latency": 9.2, "last_latency": 8.9,
             "loss_pct": 0.5, "last_ok": True, "total_pings": 50},
            {"hop": 3, "hostname": "core-rtr.example.net", "ip": "10.20.30.5",
             "min_latency": 10.2, "avg_latency": 11.1, "last_latency": 10.8,
             "loss_pct": 1.2, "last_ok": True, "total_pings": 50},
            {"hop": 4, "hostname": "ix-peer.example.net", "ip": "203.0.113.10",
             "min_latency": 15.5, "avg_latency": 16.8, "last_latency": 16.2,
             "loss_pct": 0.0, "last_ok": True, "total_pings": 50},
            {"hop": 5, "hostname": "edge-cf.example.net", "ip": "104.16.132.229",
             "min_latency": 11.8, "avg_latency": 12.5, "last_latency": 12.2,
             "loss_pct": 0.0, "last_ok": True, "total_pings": 50},
        ]
        if self.scenario == "problems":
            hops[2]["loss_pct"] = 15.2
            hops[2]["avg_latency"] = 128.5
            hops[2]["last_latency"] = 145.3
            hops[2]["last_ok"] = True
        return hops

    # ── Protocol compliance ──────────────────────────────────────────────────

    @property
    def stats_lock(self):
        """Lock for thread-safe access (protocol compliance)."""
        return self._lock

    @property
    def recent_results(self):
        """Recent ping results (protocol compliance)."""
        return self._recent_results

    def cleanup_alerts(self) -> None:
        """Clean up old visual alerts (protocol compliance)."""
        pass

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def get_stats_snapshot(self) -> Dict[str, Any]:
        """
        Return fake stats snapshot matching StatsSnapshot TypedDict exactly.

        Field list mirrors stats_repository.StatsSnapshot (lines 20-73)
        and stats_repository.StatsRepository.get_snapshot() (lines 105-166).
        """
        # Pre-compute derived values
        valid_latencies = [lat for lat in self._latencies if lat > 0]
        if valid_latencies:
            min_lat = min(valid_latencies)
            max_lat = max(valid_latencies)
            sum_lat = sum(valid_latencies)
        else:
            min_lat = float("inf")
            max_lat = 0.0
            sum_lat = 0.0

        current_lat = self._latencies[-1] if self._latencies else 0
        jitter = self._jitter_history[-1] if self._jitter_history else 0.0

        total_sent = len(self._recent_results)
        total_success = sum(1 for r in self._recent_results if r)
        total_fail = total_sent - total_success

        last_latency_ms = f"{current_lat:.1f}" if current_lat > 0 else t("na")

        return {
            # ── Counters ──
            "total": total_sent,
            "success": total_success,
            "failure": total_fail,

            # ── Last ping ──
            "last_status": t("status_ok") if current_lat > 0 else t("status_timeout"),
            "last_latency_ms": last_latency_ms,

            # ── Latency ──
            "min_latency": min_lat,
            "max_latency": max_lat,
            "total_latency_sum": sum_lat,
            "latencies": list(self._latencies),
            "jitter_history": list(self._jitter_history),

            # ── Losses ──
            "consecutive_losses": self._consecutive_losses,
            "max_consecutive_losses": self._max_consecutive_losses,

            # ── IP / geo ──
            "public_ip": "203.0.113.78",
            "country": "United States",
            "country_code": "US",

            # ── Times ──
            "start_time": self.start_time,
            "last_problem_time": (
                datetime.now(timezone.utc) - timedelta(minutes=12)
                if self._problem_type != "none" else None
            ),

            # ── IP change ──
            "previous_ip": "203.0.113.45" if self.scenario == "alerts" else None,
            "ip_change_time": (
                datetime.now(timezone.utc) - timedelta(minutes=15)
                if self.scenario == "alerts" else None
            ),

            # ── Thresholds (4 bools, matches ThresholdStates exactly) ──
            "threshold_states": {
                "high_packet_loss": self._threshold_high_loss,
                "high_avg_latency": self._threshold_high_latency,
                "connection_lost": self._threshold_connection_lost,
                "high_jitter": self._threshold_high_jitter,
            },

            # ── DNS ──
            "dns_resolve_time": 15.3,
            "dns_status": t("ok"),
            "dns_results": {},
            "dns_benchmark": self.dns_benchmark.get_stats(),

            # ── Traceroute ──
            "last_traceroute_time": (
                datetime.now(timezone.utc) - timedelta(seconds=45)
                if self.scenario == "problems" else None
            ),
            "traceroute_running": self.scenario == "problems",

            # ── Jitter ──
            "jitter": jitter,

            # ── MTU ──
            "local_mtu": 1500,
            "path_mtu": 1500 if self.scenario != "alerts" else 1492,
            "mtu_status": t("mtu_ok") if self.scenario != "alerts" else t("mtu_low"),
            "mtu_consecutive_issues": 0 if self.scenario != "alerts" else 3,
            "mtu_consecutive_ok": 50 if self.scenario != "alerts" else 0,
            "mtu_last_status_change": (
                datetime.now(timezone.utc) - timedelta(minutes=2)
                if self.scenario == "alerts" else None
            ),

            # ── TTL ──
            "last_ttl": 57,
            "ttl_hops": 7,

            # ── Problem analysis ──
            "current_problem_type": t(f"problem_{self._problem_type}"),
            "problem_prediction": (
                t("prediction_risk") if self._problem_type != "none"
                else t("prediction_stable")
            ),
            "problem_pattern": (
                "..." if self._problem_type == "none" else "periodic loss"
            ),

            # ── Route ──
            "route_hops": self._get_hops(),
            "route_problematic_hop": 3 if self.scenario == "problems" else None,
            "route_changed": self._route_changed,
            "route_consecutive_changes": 1 if self._route_changed else 0,
            "route_consecutive_ok": 0 if self._route_changed else 45,
            "route_last_change_time": (
                datetime.now(timezone.utc) - timedelta(hours=3, minutes=22)
                if self._route_changed else None
            ),
            "route_last_diff_count": 2 if self._route_changed else 0,

            # ── Alerts ──
            "active_alerts": list(self._active_alerts),
            "recent_results": list(self._recent_results),

            # ── Hop monitor ──
            "hop_monitor_hops": self._get_hops(),
            "hop_monitor_discovering": False,

            # ── Version ──
            "latest_version": None,
            "version_check_time": datetime.now(timezone.utc) - timedelta(minutes=15),
            "version_up_to_date": True,
        }


# ── Runner ───────────────────────────────────────────────────────────────────

def run_demo(scenario: str = "normal", refresh_rate: float = 1.0):
    """Run demo mode with fake data."""
    console = Console()
    provider = FakeStatsProvider(scenario)
    ui = MonitorUI(console, provider)

    console.print("\n[bold cyan]=== DEMO MODE ===[/bold cyan]")
    console.print(f"Scenario: [yellow]{scenario}[/yellow]")
    console.print("Press Ctrl+C to exit\n")

    try:
        with Live(console=console, refresh_per_second=1 / refresh_rate) as live:
            while True:
                layout = ui.generate_layout()
                live.update(layout)
                time.sleep(refresh_rate)
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo stopped.[/yellow]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Pinger in demo mode with fake data")
    parser.add_argument(
        "--scenario", "-s",
        choices=["normal", "degraded", "problems", "alerts"],
        default="normal",
        help="Demo scenario to display (default: normal)",
    )
    parser.add_argument(
        "--refresh", "-r",
        type=float,
        default=1.0,
        help="UI refresh rate in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    print("""
==============================================================
             PINGER - DEMO MODE
==============================================================

Safe for screenshots - all data is fake!

Scenarios:
  normal    - Good connection, no issues
  degraded  - High latency, some packet loss
  problems  - Connection issues, route changes
  alerts    - Multiple active alerts

Usage:
  python demo_mode.py --scenario normal
  python demo_mode.py --scenario degraded
  python demo_mode.py -s problems -r 0.5

Press Ctrl+C to exit
""")

    run_demo(scenario=args.scenario, refresh_rate=args.refresh)
