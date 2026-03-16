"""Metrics panel renderer."""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.theme import ACCENT, ACCENT_DIM, BG_PANEL, GREEN, HeightTier, LayoutTier, RED, TEXT_DIM, WHITE, YELLOW
from ui.helpers import fmt_bytes, mini_gauge, progress_bar, section_header, sparkline

try:
    from config import t
except ImportError:
    from ...config import t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


def _value_or_dash(value: float | None, color: str = WHITE, suffix: str = "") -> str:
    if value is None:
        return f"[{TEXT_DIM}]-[/{TEXT_DIM}]"
    return f"[{color}]{value:.1f}[/{color}]{suffix}"


def _traffic_markup(sent_bytes: int | None, recv_bytes: int | None) -> str:
    """Render compact bidirectional traffic summary."""
    up = fmt_bytes(sent_bytes)
    down = fmt_bytes(recv_bytes)
    return (
        f"[{WHITE}]{t('traffic_up')} {up}[/{WHITE}] "
        f"[{TEXT_DIM}]{t('traffic_down')} {down}[/{TEXT_DIM}]"
    )


def render_metrics_panel(snap: StatsSnapshot, width: int, tier: LayoutTier, h_tier: HeightTier) -> Panel:
    """Render a premium latency and reliability panel."""
    latencies = snap["latencies"]
    jitter_hist = snap.get("jitter_history", [])
    avg = (snap["total_latency_sum"] / snap["success"]) if snap["success"] > 0 else None
    med = statistics.median(latencies) if latencies else None
    jit = snap.get("jitter", 0.0) or None
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else (max(latencies) if latencies else None)
    current = snap["last_latency_ms"]

    current_markup = (
        f"[bold {WHITE}]{current}[/bold {WHITE}] [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]"
        if current != t("na")
        else f"[{TEXT_DIM}]{t('waiting')}[/{TEXT_DIM}]"
    )
    best_markup = _value_or_dash(None if snap["min_latency"] == float("inf") else snap["min_latency"], GREEN, f" [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]")
    avg_markup = _value_or_dash(avg, YELLOW, f" [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]")
    med_markup = _value_or_dash(med, WHITE, f" [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]")
    p95_markup = _value_or_dash(p95, WHITE, f" [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]")
    jitter_markup = _value_or_dash(jit, WHITE, f" [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]")

    success_rate = (snap["success"] / snap["total"] * 100) if snap["total"] else 0.0
    total_loss = (snap["failure"] / snap["total"] * 100) if snap["total"] else 0.0
    recent = snap["recent_results"]
    loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0
    sr_color = GREEN if success_rate >= 98 else (YELLOW if success_rate >= 92 else RED)
    loss_color = GREEN if loss30 < 1 else (YELLOW if loss30 < 5 else RED)

    items: list[Table | Text] = []
    inner_w = max(20, width - 4)

    items.append(Text.from_markup(
        f"  [{TEXT_DIM}]{t('ui_live_latency')}[/{TEXT_DIM}] {current_markup}  "
        f"[{TEXT_DIM}]{t('ui_stability')}[/{TEXT_DIM}] [bold {sr_color}]{success_rate:.1f}%[/bold {sr_color}]"
    ))

    if tier != "compact" and h_tier != "minimal":
        items.append(Text.from_markup(
            f"  [{TEXT_DIM}]{t('ui_trend')}[/{TEXT_DIM}] {sparkline(list(latencies), width=max(12, width - 20))}"
        ))
        if h_tier in ("standard", "full"):
            items.append(Text.from_markup(
                f"  [{TEXT_DIM}]{t('ui_jitter_trail')}[/{TEXT_DIM}] {sparkline(list(jitter_hist), width=max(12, width - 26)) if jitter_hist else f'[{TEXT_DIM}]-[/{TEXT_DIM}]'}"
            ))

    items.append(Text(""))
    items.append(section_header(t("lat"), inner_w))

    profile = Table(show_header=False, box=None, padding=(0, 1), width=width)
    profile.add_column("k1", style=TEXT_DIM, width=max(9, width // 6), no_wrap=True)
    profile.add_column("v1", width=max(10, width // 5), no_wrap=True)
    profile.add_column("k2", style=TEXT_DIM, width=max(9, width // 6), no_wrap=True)
    profile.add_column("v2", width=max(10, width // 5), no_wrap=True)
    profile.add_row(f"{t('average')}:", avg_markup, f"{t('median')}:", med_markup)
    profile.add_row(f"{t('best')}:", best_markup, f"{t('p95')}:", p95_markup)
    profile.add_row(f"{t('jitter')}:", jitter_markup, f"{t('current')}:", current_markup)
    items.append(profile)

    items.append(Text(""))
    items.append(section_header(t("stats"), inner_w))

    stats = Table(show_header=False, box=None, padding=(0, 1), width=width)
    stats.add_column("k1", style=TEXT_DIM, width=max(9, width // 6), no_wrap=True)
    stats.add_column("v1", width=max(10, width // 5), no_wrap=True)
    stats.add_column("k2", style=TEXT_DIM, width=max(9, width // 6), no_wrap=True)
    stats.add_column("v2", width=max(10, width // 5), no_wrap=True)
    stats.add_row(f"{t('sent')}:", f"[{WHITE}]{snap['total']}[/{WHITE}]", f"{t('ok_count')}:", f"[{GREEN}]{snap['success']}[/{GREEN}]")
    stats.add_row(f"{t('lost')}:", f"[{RED}]{snap['failure']}[/{RED}]", f"{t('losses')}:", f"[{loss_color}]{total_loss:.1f}%[/{loss_color}]")
    stats.add_row(f"{t('loss_30m')}:", f"[{loss_color}]{loss30:.1f}%[/{loss_color}]", f"{t('success_rate')}:", f"[{sr_color}]{success_rate:.1f}%[/{sr_color}]")
    items.append(stats)

    if h_tier in ("standard", "full"):
        gauge_w = max(10, width - 24)
        items.append(Text(""))
        items.append(Text.from_markup(
            f"  [{TEXT_DIM}]{t('success_rate')}[/{TEXT_DIM}] {mini_gauge(success_rate, width=gauge_w, color=sr_color)}"
        ))
        items.append(Text.from_markup(
            f"  [{TEXT_DIM}]{t('loss_30m')}[/{TEXT_DIM}] [{loss_color}]{loss30:.1f}%[/{loss_color}] "
            f"{progress_bar(loss30, width=gauge_w, color=loss_color)}"
        ))

    cons = snap["consecutive_losses"]
    if snap["threshold_states"]["connection_lost"]:
        cons_markup = f"[bold {RED}]{cons}[/bold {RED}]"
    elif cons > 0:
        cons_markup = f"[{YELLOW}]{cons}[/{YELLOW}]"
    else:
        cons_markup = f"[{GREEN}]{cons}[/{GREEN}]"

    items.append(Text(""))
    items.append(Text.from_markup(
        f"  [{TEXT_DIM}]{t('consecutive')}[/{TEXT_DIM}] {cons_markup}  "
        f"[{TEXT_DIM}]{t('max_label')}[/{TEXT_DIM}] [{RED}]{snap['max_consecutive_losses']}[/{RED}]"
    ))

    items.append(Text(""))
    items.append(section_header(t("traffic"), inner_w))
    traffic = Table(show_header=False, box=None, padding=(0, 1), width=width)
    traffic.add_column("k", style=TEXT_DIM, width=max(11, width // 5), no_wrap=True)
    traffic.add_column("v", width=max(10, width - max(11, width // 5) - 3), no_wrap=True)
    traffic.add_row(f"{t('traffic_app')}:", _traffic_markup(snap.get("app_bytes_sent"), snap.get("app_bytes_recv")))
    traffic.add_row(f"{t('traffic_system')}:", _traffic_markup(snap.get("system_bytes_sent"), snap.get("system_bytes_recv")))
    items.append(traffic)

    return Panel(
        Group(*items),
        title=f"[bold {ACCENT}]{t('lat')}[/bold {ACCENT}]",
        title_align="left",
        border_style=ACCENT_DIM,
        box=box.ROUNDED,
        width=width,
        style=f"on {BG_PANEL}",
        padding=(0, 1),
    )
