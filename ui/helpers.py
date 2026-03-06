"""Static helper functions for UI rendering."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from rich.table import Table
from rich.text import Text

from ui.theme import (
    ACCENT_DIM,
    BAR_EMPTY,
    BAR_FULL,
    DOT_OK,
    DOT_WARN,
    DOT_WAIT,
    GREEN,
    RED,
    SPARK_CHARS,
    TEXT_DIM,
    WHITE,
    YELLOW,
)

try:
    from config import (
        HOP_LATENCY_GOOD,
        HOP_LATENCY_WARN,
        t,
    )
except ImportError:
    from ..config import (  # type: ignore[no-redef]
        HOP_LATENCY_GOOD,
        HOP_LATENCY_WARN,
        t,
    )

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


# ═══════════════════════════════════════════════════════════════════════════════
# Utility
# ═══════════════════════════════════════════════════════════════════════════════

def ensure_utc(dt: datetime | None) -> datetime | None:
    """Convert datetime to timezone-aware UTC. If naive, assume local time and convert."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt


# ═══════════════════════════════════════════════════════════════════════════════
# Formatting helpers
# ═══════════════════════════════════════════════════════════════════════════════

def fmt_uptime(start_time: datetime | None) -> str:
    """Format duration since *start_time* as a human-readable string."""
    if start_time is None:
        return t("na")
    start_time = ensure_utc(start_time)
    if start_time is None:
        return t("na")
    total = int((datetime.now(timezone.utc) - start_time).total_seconds())
    d = total // 86400
    h = (total % 86400) // 3600
    m = (total % 3600) // 60
    s = total % 60
    parts: list[str] = []
    if d:
        parts.append(f"{d}{t('time_d')}")
    if h or d:
        parts.append(f"{h}{t('time_h')}")
    if m or h or d:
        parts.append(f"{m}{t('time_m')}")
    parts.append(f"{s}{t('time_s')}")
    return " ".join(parts)


def fmt_since(ts: datetime | None) -> str:
    """Format a relative time-ago string from *ts*."""
    if ts is None:
        return t("never")
    ts = ensure_utc(ts)
    if ts is None:
        return t("never")
    sec = int((datetime.now(timezone.utc) - ts).total_seconds())
    if sec < 5:
        return t("just_now")
    if sec < 60:
        return f"{sec}{t('time_s')} {t('ago')}"
    if sec < 3600:
        return f"{sec // 60}{t('time_m')} {t('ago')}"
    if sec < 86400:
        return f"{sec // 3600}{t('time_h')} {(sec % 3600) // 60}{t('time_m')} {t('ago')}"
    return f"{sec // 86400}{t('time_d')} {(sec % 86400) // 3600}{t('time_h')} {t('ago')}"


def progress_bar(pct: float, width: int = 20, color: str = GREEN) -> str:
    """Render a Rich-markup progress bar."""
    pct = max(0.0, min(pct, 100.0))
    filled = int(round(pct / 100.0 * width))
    empty = width - filled
    return f"[{color}]{BAR_FULL * filled}[/{color}][{ACCENT_DIM}]{BAR_EMPTY * empty}[/{ACCENT_DIM}]"


def sparkline(values: list[float], width: int = 40) -> str:
    """Render a colour-coded Unicode sparkline from *values*."""
    if not values:
        return f"[{TEXT_DIM}]{t('no_data')}[/{TEXT_DIM}]"
    data = values[-width:]
    if len(data) < 2:
        return f"[{TEXT_DIM}]{t('waiting')}[/{TEXT_DIM}]"
    # removing zero values for more accurate scaling
    valid_data = [v for v in data if v > 0]
    if not valid_data:
        return f"[{TEXT_DIM}]{t('waiting')}[/{TEXT_DIM}]"

    mn, mx = min(valid_data), max(valid_data)
    rng = mx - mn if mx != mn else 1.0
    chars: list[str] = []
    for i, v in enumerate(data):
        if v == 0:
            # for zero values, we use the lowest symbol
            idx = 0
        else:
            idx = int((v - mn) / rng * (len(SPARK_CHARS) - 1))
        idx = max(0, min(idx, len(SPARK_CHARS) - 1))
        rel = (v - mn) / rng if v > 0 else 0

        if rel < 0.4:
            color = GREEN
        elif rel < 0.7:
            color = YELLOW
        else:
            color = RED

        # Add a visual indicator to the very last bar
        is_last = (i == len(data) - 1)
        char = SPARK_CHARS[idx]

        if is_last:
            chars.append(f"[bold {color} reverse]{char}[/bold {color} reverse]")
        else:
            chars.append(f"[{color}]{char}[/{color}]")

    return "".join(chars)


def sparkline_mini(history: list[float]) -> str:
    """Render mini chart from latency history using Unicode box characters."""
    if not history or len(history) < 2:
        return ""
    min_val, max_val = min(history), max(history)
    range_val = max_val - min_val if max_val != min_val else 1
    box_chars = " ▁▂▃▅▇"
    result: list[str] = []
    recent = history[-6:]
    for val in recent:
        idx = min(5, int((val - min_val) / range_val * 5))
        result.append(box_chars[idx])
    return "".join(result)


def sparkline_double(values: list[float], width: int = 40) -> tuple[str, str]:
    """Render a two-row sparkline with ~16 vertical levels.

    Uses upper-half (▀), lower-half (▄), full (█) and space blocks to produce
    two rows whose combined height gives finer granularity than a single row.

    Returns (top_row, bottom_row) as Rich-markup strings.
    """
    if not values:
        empty = f"[{TEXT_DIM}]{t('no_data')}[/{TEXT_DIM}]"
        return (empty, "")
    data = values[-width:]
    if len(data) < 2:
        waiting = f"[{TEXT_DIM}]{t('waiting')}[/{TEXT_DIM}]"
        return (waiting, "")

    valid_data = [v for v in data if v > 0]
    if not valid_data:
        waiting = f"[{TEXT_DIM}]{t('waiting')}[/{TEXT_DIM}]"
        return (waiting, "")

    mn, mx = min(valid_data), max(valid_data)
    rng = mx - mn if mx != mn else 1.0

    top_chars: list[str] = []
    bot_chars: list[str] = []

    for i, v in enumerate(data):
        # Normalise to 0..15 (16 levels across two rows of 8)
        if v == 0:
            level = 0
        else:
            level = int((v - mn) / rng * 15)
        level = max(0, min(level, 15))

        rel = (v - mn) / rng if v > 0 else 0
        if rel < 0.4:
            color = GREEN
        elif rel < 0.7:
            color = YELLOW
        else:
            color = RED

        is_last = (i == len(data) - 1)
        style_pre = f"bold {color} reverse" if is_last else color
        style_suf = f"bold {color} reverse" if is_last else color

        # Bottom row encodes levels 0-7; top row encodes levels 8-15
        if level <= 7:
            bot_char = SPARK_CHARS[level]
            top_char = " "
        else:
            bot_char = SPARK_CHARS[7]  # full block in bottom
            top_char = SPARK_CHARS[level - 8]

        top_chars.append(f"[{style_pre}]{top_char}[/{style_suf}]")
        bot_chars.append(f"[{style_pre}]{bot_char}[/{style_suf}]")

    return ("".join(top_chars), "".join(bot_chars))


def mini_gauge(value: float, max_val: float = 100.0, width: int = 10,
               color: str = GREEN) -> str:
    """Render a compact inline gauge: ◉ 97.2% ━━━━━━━━╌╌

    *value* is displayed as-is and used to fill the bar proportionally.
    """
    pct = max(0.0, min(value / max_val, 1.0))
    filled = int(round(pct * width))
    empty = width - filled

    if pct >= 0.95:
        icon = "◉"
    elif pct >= 0.80:
        icon = "◎"
    else:
        icon = "◗"

    bar = f"[{color}]{BAR_FULL * filled}[/{color}][{ACCENT_DIM}]{BAR_EMPTY * empty}[/{ACCENT_DIM}]"
    return f"[{color}]{icon}[/{color}] [{color}]{value:.1f}%[/{color}] {bar}"


def dns_mini_bar(ms: float | None, max_ms: float = 200.0, width: int = 6) -> str:
    """Render a tiny horizontal bar for DNS response time."""
    if ms is None:
        return f"[{TEXT_DIM}]{'░' * width}[/{TEXT_DIM}]"
    pct = max(0.0, min(ms / max_ms, 1.0))
    filled = int(round(pct * width))
    empty = width - filled
    color = GREEN if ms < 50 else (YELLOW if ms < 150 else RED)
    return f"[{color}]{'█' * filled}{'░' * empty}[/{color}]"


# ═══════════════════════════════════════════════════════════════════════════════
# Table builders
# ═══════════════════════════════════════════════════════════════════════════════

def kv_table(width: int, key_width: int = 14) -> Table:
    """Create a two-column key/value Rich Table."""
    tbl = Table(show_header=False, box=None, padding=(0, 1), width=width)
    tbl.add_column("k", style=TEXT_DIM, width=key_width, no_wrap=True)
    tbl.add_column("v", width=max(10, width - key_width - 3), no_wrap=True)
    return tbl


def dual_kv_table(width: int) -> Table:
    """Create a four-column dual key/value Rich Table."""
    tbl = Table(show_header=False, box=None, padding=(0, 1), width=width)
    col_w = max(8, (width - 6) // 4)
    tbl.add_column("k1", style=TEXT_DIM, width=col_w, no_wrap=True)
    tbl.add_column("v1", width=col_w, no_wrap=True)
    tbl.add_column("k2", style=TEXT_DIM, width=col_w, no_wrap=True)
    tbl.add_column("v2", width=col_w, no_wrap=True)
    return tbl


def section_header(label: str, width: int) -> Text:
    """Render a styled section-header line."""
    line_len = max(0, width - len(label) - 7)
    return Text.from_markup(f"  [{ACCENT_DIM}]── {label} {'─' * line_len}[/{ACCENT_DIM}]")


# ═══════════════════════════════════════════════════════════════════════════════
# Misc helpers
# ═══════════════════════════════════════════════════════════════════════════════

def truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if it exceeds *max_len*."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def render_trend_arrow(delta: float, threshold: float = 2.0) -> str:
    """Render trend arrow based on delta value."""
    if delta > threshold:
        return "↑"
    elif delta < -threshold:
        return "↓"
    return "→"


def lat_color(val: float | None) -> str:
    """Return a Rich colour string based on latency thresholds."""
    if val is None:
        return RED
    if val > HOP_LATENCY_WARN:
        return RED
    if val > HOP_LATENCY_GOOD:
        return YELLOW
    return GREEN


def get_connection_state(snap: StatsSnapshot) -> tuple[str, str, str]:
    """Return (label, color, icon) tuple describing current connection state."""
    if snap["threshold_states"]["connection_lost"]:
        return t("status_disconnected"), RED, DOT_WARN
    recent = snap["recent_results"]
    if recent:
        loss30 = recent.count(False) / len(recent) * 100
        if loss30 > 5:
            return t("status_degraded"), YELLOW, DOT_WARN
    if snap["last_status"] == t("status_timeout"):
        return t("status_timeout_bar"), RED, DOT_WARN
    if snap["last_status"] == t("status_ok"):
        return t("status_connected"), GREEN, DOT_OK
    return t("status_waiting"), TEXT_DIM, DOT_WAIT


__all__ = [
    "ensure_utc",
    "fmt_uptime",
    "fmt_since",
    "progress_bar",
    "sparkline",
    "sparkline_mini",
    "sparkline_double",
    "mini_gauge",
    "dns_mini_bar",
    "kv_table",
    "dual_kv_table",
    "section_header",
    "truncate",
    "render_trend_arrow",
    "lat_color",
    "get_connection_state",
]
