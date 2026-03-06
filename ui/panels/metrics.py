"""Metrics panel renderer (Latency + Stats)."""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.theme import (
    ACCENT,
    ACCENT_DIM,
    BG_PANEL,
    GREEN,
    HeightTier,
    LayoutTier,
    RED,
    TEXT_DIM,
    WHITE,
    YELLOW,
)
from ui.helpers import mini_gauge, progress_bar, section_header, sparkline

try:
    from config import t
except ImportError:
    from ...config import t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


def render_metrics_panel(
    snap: StatsSnapshot, width: int, tier: LayoutTier, h_tier: HeightTier
) -> Panel:
    """Render the combined latency + stats panel."""
    latencies = snap["latencies"]
    jitter_hist = snap.get("jitter_history", [])
    avg = (snap["total_latency_sum"] / snap["success"]) if snap["success"] > 0 else 0.0
    med = statistics.median(latencies) if latencies else 0.0
    jit = snap.get("jitter", 0.0)
    p95 = (
        statistics.quantiles(latencies, n=20)[18]
        if len(latencies) >= 20
        else (max(latencies) if latencies else 0.0)
    )

    current = snap["last_latency_ms"]
    cur_txt = (
        f"[bold {WHITE}]{current}[/bold {WHITE}] {t('ms')}"
        if current != t("na")
        else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
    )
    best = (
        f"[{GREEN}]{snap['min_latency']:.1f}[/{GREEN}]"
        if snap["min_latency"] != float("inf")
        else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
    )
    peak = (
        f"[{RED}]{snap['max_latency']:.1f}[/{RED}]"
        if snap["max_latency"] > 0
        else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
    )
    med_txt = (
        f"[{WHITE}]{med:.1f}[/{WHITE}]"
        if latencies
        else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
    )
    avg_txt = (
        f"[{YELLOW}]{avg:.1f}[/{YELLOW}]"
        if snap["success"] > 0
        else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
    )
    p95_txt = (
        f"[{WHITE}]{p95:.1f}[/{WHITE}]"
        if latencies
        else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
    )

    if snap["threshold_states"].get("high_avg_latency") and snap["success"]:
        avg_txt = f"[bold {RED}]{avg:.1f} (!)[/bold {RED}]"

    jit_txt = (
        f"[{WHITE}]{jit:.1f}[/{WHITE}]"
        if jit > 0
        else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
    )
    if snap["threshold_states"].get("high_jitter"):
        jit_txt = f"[bold {RED}]{jit:.1f} (!)[/bold {RED}]"

    inner_w = max(20, width - 4)
    items: list[Table | Text] = []

    # ── Latency section ──
    items.append(section_header(t("lat"), inner_w))

    if tier == "compact":
        # Compact inline: all key metrics on minimal lines
        items.append(Text.from_markup(
            f"  [{TEXT_DIM}]Cur:[/{TEXT_DIM}]{cur_txt}  "
            f"[{TEXT_DIM}]Avg:[/{TEXT_DIM}]{avg_txt}  "
            f"[{TEXT_DIM}]Best:[/{TEXT_DIM}]{best}  "
            f"[{TEXT_DIM}]Med:[/{TEXT_DIM}]{med_txt}  "
            f"[{TEXT_DIM}]P95:[/{TEXT_DIM}]{p95_txt}  "
            f"[{TEXT_DIM}]Jit:[/{TEXT_DIM}]{jit_txt}"
        ))
    else:
        tbl = Table(show_header=False, box=None, padding=(0, 1), width=width)
        col_w = max(8, (width - 6) // 4)
        tbl.add_column("k1", style=TEXT_DIM, width=col_w, no_wrap=True)
        tbl.add_column("v1", width=col_w, no_wrap=True)
        tbl.add_column("k2", style=TEXT_DIM, width=col_w, no_wrap=True)
        tbl.add_column("v2", width=col_w, no_wrap=True)
        tbl.add_row(f"{t('current')}:", cur_txt, f"{t('average')}:", f"{avg_txt} {t('ms')}")
        tbl.add_row(f"{t('best')}:", f"{best} {t('ms')}", f"{t('median')}:", f"{med_txt} {t('ms')}")
        tbl.add_row(f"{t('p95')}:", f"{p95_txt} {t('ms')}", f"{t('jitter')}:", f"{jit_txt} {t('ms')}")
        items.append(tbl)

    # Sparklines: single-row for standard/wide, compact for compact, hidden for minimal
    if h_tier in ("short", "standard", "full") and tier != "compact":
        # Calculate available width for the sparkline characters:
        # subtract panel padding (4), indent (2), label, arrow " ›" and gap (2)
        lat_label = t("latency_chart")
        jit_label = t("jitter")
        label_overhead = len(lat_label) + 5  # "  label ›  "
        spark_w = max(10, width - 4 - label_overhead)

        items.append(Text(""))

        # Single-row latency sparkline
        if latencies:
            items.append(Text.from_markup(
                f"  [{TEXT_DIM}]{lat_label} ›[/{TEXT_DIM}] "
                f"{sparkline(list(latencies), width=spark_w)}"
            ))
        else:
            items.append(Text.from_markup(
                f"  [{TEXT_DIM}]{lat_label} ›[/{TEXT_DIM}] [{TEXT_DIM}]{t('no_data')}[/{TEXT_DIM}]"
            ))

        # Single-row jitter sparkline
        jit_overhead = len(jit_label) + 5
        jit_spark_w = max(10, width - 4 - jit_overhead)
        if jitter_hist:
            items.append(Text.from_markup(
                f"  [{TEXT_DIM}]{jit_label} ›[/{TEXT_DIM}] "
                f"{sparkline(list(jitter_hist), width=jit_spark_w)}"
            ))
        else:
            items.append(Text.from_markup(
                f"  [{TEXT_DIM}]{jit_label} ›[/{TEXT_DIM}] [{TEXT_DIM}]{t('no_data')}[/{TEXT_DIM}]"
            ))
    elif tier == "compact" and h_tier in ("short", "standard", "full"):
        # Compact sparklines on one line: "L:▁▂▃ J:▁▂"
        spark_w = max(8, (width - 16) // 2)
        lat_sp = sparkline(list(latencies), width=spark_w) if latencies else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
        jit_sp = sparkline(list(jitter_hist), width=spark_w) if jitter_hist else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
        items.append(Text.from_markup(
            f"  [{TEXT_DIM}]L:[/{TEXT_DIM}]{lat_sp} [{TEXT_DIM}]J:[/{TEXT_DIM}]{jit_sp}"
        ))

    # ── Stats section ──
    items.append(section_header(t("stats"), inner_w))
    success_rate = (snap["success"] / snap["total"] * 100) if snap["total"] else 0.0
    loss_total = (snap["failure"] / snap["total"] * 100) if snap["total"] else 0.0
    recent = snap["recent_results"]
    loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0

    stbl = Table(show_header=False, box=None, padding=(0, 1), width=width)
    col_w = max(8, (width - 6) // 4)
    stbl.add_column("k1", style=TEXT_DIM, width=col_w, no_wrap=True)
    stbl.add_column("v1", width=col_w, no_wrap=True)
    stbl.add_column("k2", style=TEXT_DIM, width=col_w, no_wrap=True)
    stbl.add_column("v2", width=col_w, no_wrap=True)
    stbl.add_row(
        f"{t('sent')}:", f"[{WHITE}]{snap['total']}[/{WHITE}]",
        f"{t('lost')}:", f"[{RED}]{snap['failure']}[/{RED}]",
    )
    stbl.add_row(
        f"{t('ok_count')}:", f"[{GREEN}]{snap['success']}[/{GREEN}]",
        f"{t('losses')}:", f"[{TEXT_DIM}]{loss_total:.1f}%[/{TEXT_DIM}]",
    )
    items.append(stbl)

    # Progress bars / mini gauges
    if h_tier in ("full", "standard") and tier != "compact":
        bar_w = max(10, width - 24)
        sr_color = GREEN if success_rate > 95 else (YELLOW if success_rate > 80 else RED)
        l30_color = GREEN if loss30 < 1 else (YELLOW if loss30 < 5 else RED)
        loss30_txt_bar = f"[{l30_color}]{loss30:.1f}%[/{l30_color}]"
        if snap["threshold_states"]["high_packet_loss"]:
            loss30_txt_bar += f" [{RED}](!)[/{RED}]"

        items.append(Text(""))
        # Mini gauge for success rate
        items.append(Text.from_markup(
            f"  [{TEXT_DIM}]{t('success_rate')}:[/{TEXT_DIM}] {mini_gauge(success_rate, width=bar_w, color=sr_color)}"
        ))
        items.append(Text(""))
        items.append(Text.from_markup(f"  [{TEXT_DIM}]{t('loss_30m')}:[/{TEXT_DIM}] {loss30_txt_bar}"))
        items.append(Text.from_markup(f"  {progress_bar(loss30, width=bar_w, color=l30_color)}"))
    elif tier == "compact" and h_tier in ("short", "standard", "full"):
        # Compact inline gauges
        sr_color = GREEN if success_rate > 95 else (YELLOW if success_rate > 80 else RED)
        items.append(Text.from_markup(
            f"  [{TEXT_DIM}]{t('success_rate')}:[/{TEXT_DIM}] {mini_gauge(success_rate, width=max(6, width - 20), color=sr_color)}"
        ))

    # Consecutive losses (always shown)
    cons = snap["consecutive_losses"]
    if snap["threshold_states"]["connection_lost"]:
        cons_txt = f"[bold {RED}]{cons} (!!!)[/bold {RED}]"
    elif cons > 0:
        cons_txt = f"[{YELLOW}]{cons}[/{YELLOW}]"
    else:
        cons_txt = f"[{GREEN}]{cons}[/{GREEN}]"
    max_cons_txt = f"[{RED}]{snap['max_consecutive_losses']}[/{RED}]"

    items.append(Text(""))
    items.append(Text.from_markup(
        f"  [{TEXT_DIM}]{t('consecutive')}:[/{TEXT_DIM}] {cons_txt}"
        f"    [{TEXT_DIM}]{t('max_label')}:[/{TEXT_DIM}] {max_cons_txt}"
    ))

    return Panel(
        Group(*items),
        title=f"[bold {ACCENT}]{t('lat')} & {t('stats')}[/bold {ACCENT}]",
        title_align="left",
        border_style=ACCENT_DIM,
        box=box.ROUNDED,
        width=width,
        style=f"on {BG_PANEL}",
        padding=(0, 1),
    )
