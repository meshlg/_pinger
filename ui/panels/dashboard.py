"""Dashboard panel renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.theme import ACCENT, ACCENT_DIM, BG, CRITICAL_BG, GREEN, LayoutTier, RED, TEXT_DIM, WHITE, YELLOW
from ui.helpers import fmt_uptime, get_connection_state

try:
    from config import t
except ImportError:
    from ...config import t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


TREND_UP = "\u2197"
TREND_DOWN = "\u2198"
TREND_FLAT = "\u2192"
DOT = "\u25cf"


def _trend_icon(recent: list[bool]) -> str:
    """Return an at-a-glance trend icon for recent results."""
    if len(recent) < 4:
        return TREND_FLAT
    last_window = recent[-4:]
    prev_window = recent[-8:-4] if len(recent) >= 8 else recent[:4]
    last_ok = sum(1 for value in last_window if value)
    prev_ok = sum(1 for value in prev_window if value)
    if last_ok > prev_ok:
        return TREND_UP
    if last_ok < prev_ok:
        return TREND_DOWN
    return TREND_FLAT


def _result_strip(recent: list[bool], max_dots: int = 18) -> str:
    """Render the recent history as a compact signal strip."""
    dots = recent[-max_dots:]
    if not dots:
        return f"[{TEXT_DIM}]{t('ui_signal_none')}[/{TEXT_DIM}]"
    parts: list[str] = []
    for ok in dots:
        color = GREEN if ok else RED
        parts.append(f"[{color}]{DOT}[/{color}]")
    return "".join(parts)


def render_dashboard(snap: StatsSnapshot, width: int, tier: LayoutTier) -> Panel:
    """Render the hero telemetry strip."""
    label, color, icon = get_connection_state(snap)
    current = snap["last_latency_ms"]
    ping_txt = f"{current}" if current != t("na") else "-"

    recent = snap["recent_results"]
    loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0
    loss_color = GREEN if loss30 < 1 else (YELLOW if loss30 < 5 else RED)
    uptime_txt = fmt_uptime(snap["start_time"])
    jitter = snap.get("jitter", 0.0)
    jitter_txt = f"{jitter:.1f}" if jitter > 0 else "-"

    trend = _trend_icon(recent)
    if trend == TREND_UP:
        trend_color = GREEN
    elif trend == TREND_DOWN:
        trend_color = RED
    else:
        trend_color = TEXT_DIM

    history = _result_strip(recent)
    bg_color = CRITICAL_BG if snap.get("threshold_states", {}).get("connection_lost") else BG

    if tier == "compact":
        body = Text.from_markup(
            f"[bold {color}]{icon} {label}[/bold {color}]  "
            f"[{TEXT_DIM}]{t('ui_live')}[/{TEXT_DIM}] [bold {WHITE}]{ping_txt}[/bold {WHITE}] [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]  "
            f"[{TEXT_DIM}]{t('loss')}[/{TEXT_DIM}] [bold {loss_color}]{loss30:.1f}%[/bold {loss_color}]"
        )
    else:
        grid = Table.grid(expand=True)
        grid.add_column(ratio=3)
        grid.add_column(ratio=2, justify="right")
        left = Text.from_markup(
            f"[bold {color}]{icon} {label}[/bold {color}]  "
            f"[{TEXT_DIM}]{t('ui_live_latency')}[/{TEXT_DIM}] [bold {WHITE}]{ping_txt}[/bold {WHITE}] [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]  "
            f"[{trend_color}]{trend}[/{trend_color}]"
        )
        right = Text.from_markup(
            f"[{TEXT_DIM}]{t('jitter')}[/{TEXT_DIM}] [{WHITE}]{jitter_txt}[/{WHITE}] [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]  "
            f"[{TEXT_DIM}]{t('loss')}[/{TEXT_DIM}] [bold {loss_color}]{loss30:.1f}%[/bold {loss_color}]"
        )
        grid.add_row(left, right)
        grid.add_row(
            Text.from_markup(f"[{TEXT_DIM}]{t('uptime')}[/{TEXT_DIM}] [{WHITE}]{uptime_txt}[/{WHITE}]"),
            Text.from_markup(f"[{ACCENT}]{t('ui_history')}[/{ACCENT}] {history}"),
        )
        body = grid

    return Panel(
        body,
        border_style=color if snap.get("threshold_states", {}).get("connection_lost") else ACCENT_DIM,
        box=box.ROUNDED,
        width=width,
        style=f"on {bg_color}",
        padding=(0, 1),
    )
