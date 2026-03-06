"""Dashboard panel renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel

from ui.theme import (
    ACCENT_DIM,
    BG,
    CRITICAL_BG,
    GREEN,
    LayoutTier,
    RED,
    TEXT_DIM,
    WHITE,
    YELLOW,
)
from ui.helpers import fmt_uptime, get_connection_state, sparkline

try:
    from config import t
except ImportError:
    from ...config import t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


def _trend_icon(recent: list[bool]) -> str:
    """Return ▲/▼/► trend icon based on recent results pattern."""
    if len(recent) < 4:
        return "►"
    last_q = recent[-4:]
    prev_q = recent[-8:-4] if len(recent) >= 8 else recent[:4]
    last_ok = sum(1 for r in last_q if r)
    prev_ok = sum(1 for r in prev_q if r)
    if last_ok > prev_ok:
        return "▲"
    elif last_ok < prev_ok:
        return "▼"
    return "►"


def _result_dots(recent: list[bool], max_dots: int = 20) -> str:
    """Render recent results as coloured dots (●/○)."""
    dots = recent[-max_dots:]
    parts: list[str] = []
    for ok in dots:
        if ok:
            parts.append(f"[{GREEN}]●[/{GREEN}]")
        else:
            parts.append(f"[{RED}]●[/{RED}]")
    return "".join(parts)


def render_dashboard(snap: StatsSnapshot, width: int, tier: LayoutTier) -> Panel:
    """Render the compact status dashboard bar."""
    label, color, icon = get_connection_state(snap)
    current = snap["last_latency_ms"]
    ping_txt = f"{current}" if current != t("na") else "—"

    recent = snap["recent_results"]
    loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0
    l_color = GREEN if loss30 < 1 else (YELLOW if loss30 < 5 else RED)
    loss_txt = f"{loss30:.1f}%"

    uptime_txt = fmt_uptime(snap["start_time"])
    ip_val = snap["public_ip"]
    lbl_ping = f"{t('ping').upper()}:"
    lbl_loss = f"{t('loss').upper()}:"
    lbl_up = f"{t('uptime').upper()}:"
    lbl_ip = f"{t('ip_label').upper()}:"
    cc = f" [{snap['country_code']}]" if snap["country_code"] else ""

    # Trend icon for latency direction
    trend = _trend_icon(recent)
    trend_color = GREEN if trend == "▲" else (RED if trend == "▼" else TEXT_DIM)

    warmup = snap.get("threshold_warmup", {})
    warmup_part = ""
    warmup_part_compact = ""
    if warmup:
        max_req = 0
        curr_samples = 0
        for v in warmup.values():
            if v["min_samples"] > max_req:
                max_req = v["min_samples"]
                curr_samples = v["samples"]
        if max_req > 0:
            warmup_part = f"  [{ACCENT_DIM}]│[/{ACCENT_DIM}]  [{TEXT_DIM}]{t('warmup_status')}:[/{TEXT_DIM}] [{YELLOW}]{curr_samples}/{max_req}[/{YELLOW}]"
            warmup_part_compact = f"  [{ACCENT_DIM}]│[/{ACCENT_DIM}]  [{YELLOW}]{t('warmup_compact')}:{curr_samples}/{max_req}[/{YELLOW}]"

    sep = f"  [{ACCENT_DIM}]│[/{ACCENT_DIM}]  "

    if tier == "compact":
        parts = (
            f"  [bold {color}]{icon} {label}[/bold {color}]{sep}"
            f"[{TEXT_DIM}]{lbl_ping}[/{TEXT_DIM}] [bold {WHITE}]{ping_txt}[/bold {WHITE}] [{trend_color}]{trend}[/{trend_color}]{sep}"
            f"[{TEXT_DIM}]{lbl_loss}[/{TEXT_DIM}] [bold {l_color}]{loss_txt}[/bold {l_color}]"
            f"{warmup_part_compact}"
        )
        bg_col = CRITICAL_BG if snap.get("threshold_states", {}).get("connection_lost") else BG
        return Panel(
            parts, border_style=color, box=box.SIMPLE, width=width,
            style=f"on {bg_col}",
            padding=(0, 1),
        )
    else:
        # Build recent results dots (last 20)
        dots = _result_dots(recent, max_dots=20) if recent else ""
        dots_section = f"{sep}{dots}" if dots else ""

        parts = (
            f"  [bold {color}]{icon} {label}[/bold {color}]"
            f"{sep}[{TEXT_DIM}]{lbl_ping}[/{TEXT_DIM}] [bold {WHITE}]{ping_txt}[/bold {WHITE}] [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}] [{trend_color}]{trend}[/{trend_color}]"
            f"{sep}[{TEXT_DIM}]{lbl_loss}[/{TEXT_DIM}] [bold {l_color}]{loss_txt}[/bold {l_color}]"
            f"{sep}[{TEXT_DIM}]{lbl_up}[/{TEXT_DIM}] [{WHITE}]{uptime_txt}[/{WHITE}]"
            f"{sep}[{TEXT_DIM}]{lbl_ip}[/{TEXT_DIM}] [{WHITE}]🌐 {ip_val}{cc}[/{WHITE}]"
            f"{warmup_part}"
            f"{dots_section}"
        )

        bg_col = CRITICAL_BG if snap.get("threshold_states", {}).get("connection_lost") else BG
        return Panel(
            parts, border_style=color, box=box.SIMPLE, width=width,
            style=f"on {bg_col}",
            padding=(0, 1),
        )
