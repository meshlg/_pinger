"""Hop health table panel renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.theme import ACCENT, ACCENT_DIM, BG, GREEN, HeightTier, LayoutTier, RED, TEXT_DIM, WHITE, YELLOW
from ui.helpers import lat_color, render_trend_arrow, sparkline

try:
    from config import HOP_LATENCY_GOOD, t
except ImportError:
    from ...config import HOP_LATENCY_GOOD, t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


DOT = "\u25cf"
SEPARATOR = "\u2502"


def _fmt_latency(value: Any) -> str:
    if value is None:
        return f"[{TEXT_DIM}]-[/{TEXT_DIM}]"
    color = lat_color(float(value))
    return f"[{color}]{float(value):.0f}[/{color}]"


def render_hop_panel(snap: StatsSnapshot, width: int, tier: LayoutTier, h_tier: HeightTier) -> Panel:
    """Render the hop health table panel."""
    connection_lost = bool(snap.get("threshold_states", {}).get("connection_lost", False))
    hops = snap.get("hop_monitor_hops", [])
    discovering = snap.get("hop_monitor_discovering", False)

    if connection_lost:
        body = Text.from_markup(f"  [{RED}]{t('status_disconnected')}[/{RED}]")
        return Panel(body, title=f"[bold {ACCENT}]{t('hop_health')}[/bold {ACCENT}]", title_align="left", border_style=ACCENT_DIM, box=box.ROUNDED, width=width, style=f"on {BG}", padding=(0, 1))

    if discovering and not hops:
        body = Text.from_markup(f"  [{TEXT_DIM}]{t('hop_discovering')}[/{TEXT_DIM}]")
        return Panel(body, title=f"[bold {ACCENT}]{t('hop_health')}[/bold {ACCENT}]", title_align="left", border_style=ACCENT_DIM, box=box.ROUNDED, width=width, style=f"on {BG}", padding=(0, 1))

    if not hops:
        body = Text.from_markup(f"  [{TEXT_DIM}]{t('hop_none')}[/{TEXT_DIM}]")
        return Panel(body, title=f"[bold {ACCENT}]{t('hop_health')}[/bold {ACCENT}]", title_align="left", border_style=ACCENT_DIM, box=box.ROUNDED, width=width, style=f"on {BG}", padding=(0, 1))

    show_extended = tier != "compact"
    show_geo = tier == "wide"

    if h_tier == "minimal":
        max_hops = 5
    elif h_tier == "short":
        max_hops = 8
    else:
        max_hops = len(hops)
    display_hops = hops[:max_hops]

    table = Table(
        show_header=True,
        header_style=f"bold {WHITE}",
        box=box.SIMPLE_HEAVY,
        padding=(0, 1),
        expand=True,
        border_style=ACCENT_DIM,
    )
    table.add_column(t("hop_col_num"), style=TEXT_DIM, width=3, justify="right", no_wrap=True)
    table.add_column("", width=1, justify="center", no_wrap=True)
    if show_extended:
        table.add_column(t("hop_col_min"), width=5, justify="right", no_wrap=True)
    table.add_column(t("hop_col_avg"), width=5, justify="right", no_wrap=True)
    table.add_column(t("hop_col_last"), width=5, justify="right", no_wrap=True)
    if show_extended:
        table.add_column(t("hop_col_delta"), width=6, justify="right", no_wrap=True)
        table.add_column(t("hop_col_jitter"), width=6, justify="right", no_wrap=True)
    table.add_column(t("hop_col_loss"), width=6, justify="right", no_wrap=True)
    if show_extended:
        table.add_column(t("ui_trend"), width=8, justify="left", no_wrap=True)
    if show_geo:
        table.add_column(t("hop_col_asn"), width=24, overflow="ellipsis", no_wrap=True)
        table.add_column(t("hop_col_loc"), width=8, no_wrap=True)
    table.add_column(t("hop_col_host"), ratio=1, overflow="ellipsis")

    worst_hop = None
    worst_value = 0.0

    for hop in display_hops:
        hop_num = hop.get("hop", "?")
        last_latency = hop.get("last_latency")
        avg_latency = hop.get("avg_latency")
        min_latency = hop.get("min_latency")
        loss_pct = float(hop.get("loss_pct", 0.0) or 0.0)
        jitter = float(hop.get("jitter", 0.0) or 0.0)
        delta = float(hop.get("latency_delta", 0.0) or 0.0)
        ok = bool(hop.get("last_ok", True))
        hostname = hop.get("hostname") or hop.get("ip", "?")
        ip = hop.get("ip", "?")
        country_code = hop.get("country_code", "")
        asn = hop.get("asn", "")

        if not ok:
            dot = f"[{RED}]{DOT}[/{RED}]"
        elif loss_pct > 0:
            dot = f"[{YELLOW}]{DOT}[/{YELLOW}]"
        else:
            dot = f"[{GREEN}]{DOT}[/{GREEN}]"

        if loss_pct >= 10:
            loss_txt = f"[{RED}]{loss_pct:.0f}%[/{RED}]"
        elif loss_pct > 0:
            loss_txt = f"[{YELLOW}]{loss_pct:.0f}%[/{YELLOW}]"
        else:
            loss_txt = f"[{GREEN}]{loss_pct:.0f}%[/{GREEN}]"

        host_txt = f"{hostname} [{TEXT_DIM}]{ip}[/{TEXT_DIM}]" if hostname != ip else ip
        row: list[str] = [str(hop_num), dot]

        if show_extended:
            row.append(_fmt_latency(min_latency))
        row.append(_fmt_latency(avg_latency))
        row.append(_fmt_latency(last_latency if ok else None))

        if show_extended:
            arrow = render_trend_arrow(delta)
            if delta > 0:
                delta_txt = f"[{YELLOW}]{arrow}+{delta:.0f}[/{YELLOW}]"
            elif delta < 0:
                delta_txt = f"[{GREEN}]{arrow}{delta:.0f}[/{GREEN}]"
            else:
                delta_txt = f"[{TEXT_DIM}]{arrow}0[/{TEXT_DIM}]"
            jitter_txt = f"[{TEXT_DIM}]{jitter:.0f}[/{TEXT_DIM}]" if jitter > 0 else f"[{TEXT_DIM}]-[/{TEXT_DIM}]"
            row.extend([delta_txt, jitter_txt])

        row.append(loss_txt)

        if show_extended:
            history = [float(v) for v in hop.get("latency_history", [])[-8:] if v is not None]
            row.append(sparkline(history, 8) if len(history) >= 2 else f"[{TEXT_DIM}]-[/{TEXT_DIM}]")

        if show_geo:
            row.append(f"[{TEXT_DIM}]{asn}[/{TEXT_DIM}]" if asn else "")
            row.append(f"[{TEXT_DIM}]{country_code}[/{TEXT_DIM}]" if country_code else "")

        row.append(host_txt)
        table.add_row(*row)

        if not ok:
            worst_hop = hop
            worst_value = float("inf")
        elif last_latency is not None and float(last_latency) > worst_value:
            worst_hop = hop
            worst_value = float(last_latency)

    items: list[Table | Text] = [table]

    if len(hops) > max_hops:
        items.append(Text.from_markup(f"  [{TEXT_DIM}]+{t('more_hops').format(count=len(hops) - max_hops)}[/{TEXT_DIM}]"))

    if worst_hop and worst_value > HOP_LATENCY_GOOD:
        hop_no = worst_hop.get("hop", "?")
        hop_ip = worst_hop.get("ip", "?")
        if worst_value == float("inf"):
            items.append(Text.from_markup(f"  [{RED}]{t('hop_worst')}: #{hop_no} {hop_ip} {t('hop_down')}[/{RED}]"))
        else:
            items.append(Text.from_markup(f"  [{YELLOW}]{t('hop_worst')}: #{hop_no} {hop_ip} {worst_value:.0f} {t('ms')}[/{YELLOW}]"))

    if discovering:
        items.append(Text.from_markup(f"  [{TEXT_DIM}]{t('hop_discovering')}[/{TEXT_DIM}]"))

    return Panel(
        Group(*items),
        title=f"[bold {ACCENT}]{t('hop_health')}[/bold {ACCENT}]",
        title_align="left",
        border_style=ACCENT_DIM,
        box=box.ROUNDED,
        width=width,
        style=f"on {BG}",
        padding=(0, 1),
    )
