"""Hop health table panel renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.theme import (
    ACCENT,
    ACCENT_DIM,
    BG,
    GREEN,
    HeightTier,
    LayoutTier,
    RED,
    TEXT_DIM,
    WHITE,
    YELLOW,
)
from ui.helpers import lat_color, render_trend_arrow, sparkline

try:
    from config import HOP_LATENCY_GOOD, t
except ImportError:
    from ...config import HOP_LATENCY_GOOD, t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


def render_hop_panel(
    snap: StatsSnapshot, width: int, tier: LayoutTier, h_tier: HeightTier
) -> Panel:
    """Render the hop health table panel."""
    connection_lost = bool(snap.get("threshold_states", {}).get("connection_lost", False))
    hops = snap.get("hop_monitor_hops", [])
    discovering = snap.get("hop_monitor_discovering", False)
    panel_style = f"on {BG}"
    title = f"[bold {WHITE}]{t('hop_health')}[/bold {WHITE}]"
    border = ACCENT_DIM

    if connection_lost:
        return Panel(
            Text.from_markup(f"  [{RED}]{t('status_disconnected')}[/{RED}]"),
            title=title, title_align="left", border_style=border,
            box=box.SIMPLE, width=width, style=f"on {BG}",
            padding=(0, 1),
        )

    if discovering and not hops:
        return Panel(
            Text.from_markup(f"  [{TEXT_DIM}]{t('hop_discovering')}[/{TEXT_DIM}]"),
            title=title, title_align="left", border_style=border,
            box=box.SIMPLE, width=width, style=f"on {BG}",
            padding=(0, 1),
        )
    if not hops:
        return Panel(
            Text.from_markup(f"  [{TEXT_DIM}]{t('hop_none')}[/{TEXT_DIM}]"),
            title=title, title_align="left", border_style=border,
            box=box.SIMPLE, width=width, style=f"on {BG}",
            padding=(0, 1),
        )

    # Adaptive columns based on width tier
    show_extended = tier != "compact"
    show_geo = tier == "wide"

    tbl = Table(
        show_header=True, header_style=f"bold {TEXT_DIM}",
        box=box.SIMPLE_HEAD, padding=(0, 1), expand=True,
        border_style=ACCENT_DIM,
    )
    tbl.add_column(t("hop_col_num"), style=TEXT_DIM, width=3, justify="right", no_wrap=True)
    tbl.add_column("", width=1, justify="center", no_wrap=True)
    if show_extended:
        tbl.add_column(t("hop_col_min"), width=6, justify="right", no_wrap=True)
    tbl.add_column(t("hop_col_avg"), width=6, justify="right", no_wrap=True)
    tbl.add_column(t("hop_col_last"), width=6, justify="right", no_wrap=True)
    if show_extended:
        tbl.add_column(t("hop_col_delta"), width=7, justify="right", no_wrap=True)
        tbl.add_column(t("hop_col_jitter"), width=8, justify="right", no_wrap=True)
    tbl.add_column(t("hop_col_loss"), width=6, justify="right", no_wrap=True)
    if show_extended:
        tbl.add_column("⠿", width=8, justify="left", no_wrap=True)  # sparkline trend
    if show_geo:
        tbl.add_column(t("hop_col_asn"), width=28, justify="left", no_wrap=True, overflow="ellipsis")
        tbl.add_column(t("hop_col_loc"), width=8, justify="left", no_wrap=True)
    tbl.add_column(t("hop_col_host"), ratio=1, no_wrap=True, overflow="ellipsis")

    # Limit hops based on height
    if h_tier == "minimal":
        max_hops = 5
    elif h_tier == "short":
        max_hops = 8
    else:
        max_hops = len(hops)
    display_hops = hops[:max_hops]

    worst_hop = None
    worst_lat = 0.0

    for hop in display_hops:
        hop_num = hop["hop"]
        lat = hop.get("last_latency")
        avg_h = hop.get("avg_latency", 0.0)
        mn = hop.get("min_latency")
        ok = hop.get("last_ok", True)
        loss = hop.get("loss_pct", 0.0)
        ip = hop.get("ip", "?")
        hostname = hop.get("hostname", ip)
        jitter_h = hop.get("jitter", 0.0)
        delta = hop.get("latency_delta", 0.0)
        country_code = hop.get("country_code", "")
        asn = hop.get("asn", "")

        # Clean ASN
        if asn:
            asn_clean = asn
            for suffix in [" Inc.", " LLC", " Ltd", " Limited", " Corporation", " Corp.", " AB", " AG", " BV"]:
                asn_clean = asn_clean.replace(suffix, "").replace(suffix.upper(), "")
            asn_display = asn_clean if asn_clean.upper().startswith("AS") else f"AS{asn_clean}"
        else:
            asn_display = ""

        # Host text
        host_txt = f"{hostname} [{TEXT_DIM}][{ip}][/{TEXT_DIM}]" if (hostname and hostname != ip) else ip

        # Status dot
        if not ok:
            dot = f"[{RED}]●[/{RED}]"
        elif loss > 0:
            dot = f"[{YELLOW}]●[/{YELLOW}]"
        else:
            dot = f"[{GREEN}]●[/{GREEN}]"

        def _lf(val: Any) -> str:
            if val is None:
                return f"[{RED}]*[/{RED}]"
            c = lat_color(val)
            return f"[{c}]{val:.0f}[/{c}]"

        last_txt = f"[{RED}]*[/{RED}]" if (not ok or lat is None) else _lf(lat)

        # Loss text
        if loss > 10:
            loss_txt = f"[{RED}]{loss:.0f}![/{RED}]"
        elif loss > 0:
            loss_txt = f"[{YELLOW}]{loss:.0f}%[/{YELLOW}]"
        else:
            loss_txt = f"[{GREEN}]{loss:.0f}%[/{GREEN}]"

        row_style = TEXT_DIM if (not ok and hop.get("total_pings", 0) > 2) else ""

        row: list[str] = [str(hop_num), dot]
        if show_extended:
            row.append(_lf(mn))
        row.extend([_lf(avg_h if avg_h > 0 else None), last_txt])
        if show_extended:
            trend = render_trend_arrow(delta)
            if delta > 0:
                d_txt = f"[{YELLOW}]{trend}+{delta:.0f}[/{YELLOW}]"
            elif delta < 0:
                d_txt = f"[{GREEN}]{trend}{delta:.0f}[/{GREEN}]"
            else:
                d_txt = f"[{TEXT_DIM}]{trend}—[/{TEXT_DIM}]"
            j_txt = f"[{TEXT_DIM}]{jitter_h:.0f}[/{TEXT_DIM}]" if jitter_h > 0 else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
            row.extend([d_txt, j_txt])
        row.append(loss_txt)
        if show_extended:
            # Mini sparkline from latency history
            lat_hist = hop.get("latency_history", [])
            if lat_hist and len(lat_hist) >= 2:
                # Take last 8 samples for compact sparkline
                samples = [float(v) for v in lat_hist[-8:] if v is not None]
                if samples:
                    sl_color = lat_color(avg_h if avg_h > 0 else (lat or 0))
                    row.append(f"[{sl_color}]{sparkline(samples, 8)}[/{sl_color}]")
                else:
                    row.append(f"[{TEXT_DIM}]·[/{TEXT_DIM}]")
            else:
                row.append(f"[{TEXT_DIM}]·[/{TEXT_DIM}]")
        if show_geo:
            row.append(f"[{TEXT_DIM}]{asn_display}[/{TEXT_DIM}]")
            row.append(f"[{TEXT_DIM}]{country_code}[/{TEXT_DIM}]" if country_code else "")
        row.append(host_txt)
        tbl.add_row(*row, style=row_style)

        if not ok:
            worst_hop = hop
            worst_lat = float("inf")
        elif lat is not None and lat > worst_lat:
            worst_lat = lat
            worst_hop = hop

    items: list[Table | Text] = [tbl]

    if len(hops) > max_hops:
        more_txt = t("more_hops").format(count=len(hops) - max_hops)
        items.append(Text.from_markup(f"  [{TEXT_DIM}]+{more_txt}[/{TEXT_DIM}]"))

    if worst_hop and worst_lat > HOP_LATENCY_GOOD:
        w_ip = worst_hop.get("ip", "?")
        w_num = worst_hop.get("hop", "?")
        if worst_lat == float("inf"):
            items.append(Text.from_markup(f"  [{RED}]{t('hop_worst')}: #{w_num} {w_ip} — {t('hop_down')}[/{RED}]"))
        else:
            items.append(Text.from_markup(f"  [{YELLOW}]{t('hop_worst')}: #{w_num} {w_ip} — {worst_lat:.0f} {t('ms')}[/{YELLOW}]"))

    if discovering:
        items.append(Text.from_markup(f"  [{TEXT_DIM} italic]{t('hop_discovering')}[/{TEXT_DIM} italic]"))

    return Panel(
        Group(*items),
        title=title, title_align="left", border_style=border,
        box=box.SIMPLE, width=width, style=panel_style,
        padding=(0, 1),
    )
