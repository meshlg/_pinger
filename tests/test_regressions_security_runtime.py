from __future__ import annotations

import io
import sys
import threading
from pathlib import Path

from rich.console import Console

# Allow running this file directly: `python tests/test_regressions_security_runtime.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.adaptive_thresholds import AdaptiveThresholds
from config import t
from infrastructure.health import HealthHandler, RateLimiter
from monitor import Monitor
from problem_analyzer import ProblemAnalyzer
from services.ip_service import IPService
from stats_repository import StatsRepository
from ui import MonitorUI


def test_rate_limiter_check_request_does_not_deadlock() -> None:
    limiter = RateLimiter(max_requests_per_minute=60)

    done = threading.Event()
    result: dict[str, tuple[bool, str]] = {}

    def _worker() -> None:
        result["value"] = limiter.check_request("203.0.113.10")
        done.set()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    assert done.wait(1.0), "RateLimiter.check_request deadlocked"
    assert result["value"][0] is True


def test_client_ip_ignores_xff_when_proxy_not_trusted(monkeypatch) -> None:
    monkeypatch.delenv("HEALTH_TRUSTED_PROXIES", raising=False)

    class DummyHandler:
        client_address = ("198.51.100.12", 12345)
        headers = {"X-Forwarded-For": "203.0.113.99"}

    assert HealthHandler._get_client_ip(DummyHandler()) == "198.51.100.12"


def test_client_ip_accepts_xff_for_trusted_proxy(monkeypatch) -> None:
    monkeypatch.setenv("HEALTH_TRUSTED_PROXIES", "198.51.100.0/24")

    class DummyHandler:
        client_address = ("198.51.100.12", 12345)
        headers = {"X-Forwarded-For": "203.0.113.99, 198.51.100.12"}

    assert HealthHandler._get_client_ip(DummyHandler()) == "203.0.113.99"


def test_ip_change_ignores_invalid_provider_values() -> None:
    service = IPService()

    assert service.check_ip_change("1.1.1.1", "N/A", None) is None
    assert service.check_ip_change("Error", "Error", None) is None
    assert service.get_previous_ip() == "1.1.1.1"

    change = service.check_ip_change("1.0.0.1", "N/A", None)
    assert change is not None
    assert change["old_ip"] == "1.1.1.1"
    assert change["new_ip"] == "1.0.0.1"


def test_avg_latency_baseline_warms_up_early() -> None:
    stats_repo = StatsRepository()
    for latency in (10.0, 20.0, 30.0, 40.0, 50.0):
        stats_repo.update_after_ping(True, latency)

    thresholds = AdaptiveThresholds(stats_repo=stats_repo)
    baseline = thresholds.get_baseline("avg_latency")

    assert baseline is not None
    assert baseline.sample_count >= 5


def test_packet_loss_baseline_warms_up_early() -> None:
    stats_repo = StatsRepository()
    for ok in (True, False, True, False, True):
        stats_repo.update_after_ping(ok, 20.0 if ok else None)

    thresholds = AdaptiveThresholds(stats_repo=stats_repo)
    baseline = thresholds.get_baseline("packet_loss")

    assert baseline is not None
    assert baseline.sample_count >= 3


def test_problem_analyzer_reports_outage_as_isp_and_risk() -> None:
    stats_repo = StatsRepository()
    for _ in range(5):
        stats_repo.update_after_ping(False, None)
    stats_repo.update_threshold_state("connection_lost", True)

    analyzer = ProblemAnalyzer(stats_repo=stats_repo)
    problem_type = analyzer.analyze_current_problem()
    prediction = analyzer.predict_problems(problem_type)

    assert problem_type == t("problem_isp")
    assert prediction == t("prediction_risk")


def test_ui_analysis_panel_masks_stale_route_and_mtu_on_disconnect() -> None:
    stats_repo = StatsRepository()
    stats_repo.update_problem_analysis(t("problem_none"), t("prediction_stable"), "...")
    stats_repo.update_route(
        hops=[
            {"hop": 1, "ip": "192.168.0.1", "avg_latency": 1.2},
            {"hop": 2, "ip": "10.204.84.187", "avg_latency": 6.5},
        ],
        problematic_hop=None,
        route_changed=False,
        diff_count=0,
    )
    stats_repo.update_mtu(1500, 765, t("mtu_low"))
    stats_repo.update_ttl(52, 12)
    stats_repo.update_threshold_state("connection_lost", True)
    snap = stats_repo.get_snapshot()

    class DummyProvider:
        def get_stats_snapshot(self):
            return snap

    console = Console(record=True, width=120, file=io.StringIO())
    ui = MonitorUI(console, DummyProvider())
    panel = ui._render_analysis_panel(snap, width=100, tier="standard", h_tier="standard")

    console.print(panel)
    rendered = console.export_text()

    assert t("status_disconnected") in rendered
    assert t("problem_isp") in rendered
    assert t("prediction_risk") in rendered
    assert t("route_stable") not in rendered
    assert "1500/765" not in rendered


def test_ui_hop_panel_hides_stale_hops_on_disconnect() -> None:
    stats_repo = StatsRepository()
    stats_repo.update_hop_monitor([{"hop": 1, "ip": "192.168.0.1"}], discovering=False)
    stats_repo.update_threshold_state("connection_lost", True)
    snap = stats_repo.get_snapshot()

    class DummyProvider:
        def get_stats_snapshot(self):
            return snap

    console = Console(record=True, width=120, file=io.StringIO())
    ui = MonitorUI(console, DummyProvider())
    panel = ui._render_hop_panel(snap, width=100, tier="standard", h_tier="standard")

    console.print(panel)
    rendered = console.export_text()

    assert t("status_disconnected") in rendered
    assert "192.168.0.1" not in rendered


def test_monitor_refresh_problem_analysis_updates_snapshot_immediately() -> None:
    stats_repo = StatsRepository()
    for _ in range(5):
        stats_repo.update_after_ping(False, None)
    stats_repo.update_threshold_state("connection_lost", True)

    analyzer = ProblemAnalyzer(stats_repo=stats_repo)

    class DummyMonitor:
        def __init__(self):
            self.stats_repo = stats_repo
            self.problem_analyzer = analyzer

    dummy = DummyMonitor()
    Monitor._refresh_problem_analysis(dummy)

    snap = stats_repo.get_snapshot()
    assert snap["current_problem_type"] == t("problem_isp")
    assert snap["problem_prediction"] == t("prediction_risk")
