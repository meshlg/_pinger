from __future__ import annotations

import statistics
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal
import time
import threading

def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Convert datetime to timezone-aware UTC. If naive, assume local time and convert."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt

from rich import box
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Import Protocol for DIP-compliant design
from ui_protocols.protocols import StatsDataProvider

if TYPE_CHECKING:
    from monitor import Monitor
    from stats_repository import StatsSnapshot

try:
    from config import (
        ALERT_PANEL_LINES,
        SHOW_VISUAL_ALERTS,
        TARGET_IP,
        HOP_LATENCY_GOOD,
        HOP_LATENCY_WARN,
        VERSION,
        UI_COMPACT_THRESHOLD,
        UI_WIDE_THRESHOLD,
        LOG_FILE,
        UI_THEME,
        t,
    )
except ImportError:
    from .config import (  # type: ignore[no-redef]
        ALERT_PANEL_LINES,
        SHOW_VISUAL_ALERTS,
        TARGET_IP,
        HOP_LATENCY_GOOD,
        HOP_LATENCY_WARN,
        VERSION,
        UI_COMPACT_THRESHOLD,
        UI_WIDE_THRESHOLD,
        LOG_FILE,
        UI_THEME,
        t,
    )

try:
    from config.ui_theme import get_theme
except ImportError:
    from .config.ui_theme import get_theme

# ═══════════════════════════════════════════════════════════════════════════════
# Style constants
# ═══════════════════════════════════════════════════════════════════════════════

theme = get_theme(UI_THEME)

# Color palette – dynamic from theme
_BG = theme.bg
_BG_PANEL = theme.bg_panel
_ACCENT = theme.accent
_ACCENT_DIM = theme.accent_dim
_TEXT = theme.text
_TEXT_DIM = theme.text_dim
_GREEN = theme.green
_YELLOW = theme.yellow
_RED = theme.red
_WHITE = theme.white
_CRITICAL_BG = theme.critical_bg

# Unicode elements
_SPARK_CHARS = "▁▂▃▄▅▆▇█"
_BAR_FULL = "━"
_BAR_EMPTY = "╌"
_DOT_OK = "●"
_DOT_WARN = "▲"
_DOT_WAIT = "○"

# Layout tier types
LayoutTier = Literal["compact", "standard", "wide"]
HeightTier = Literal["minimal", "short", "standard", "full"]


class MonitorUI:
    """
    Adaptive Rich-based UI for network monitoring.

    Renders adaptively based on both terminal width AND height:
    Width tiers:
      - compact  (<100 cols): single column
      - standard (100–149):   two columns
      - wide     (≥150):      two columns + extended hop table
    Height tiers:
      - minimal  (<25 rows): status + essential data only
      - short    (25–39):    condensed panels
      - standard (40–54):    full panels
      - full     (≥55):      sparklines, progress bars, expanded details
    """

    def __init__(self, console: Console, data_provider: StatsDataProvider) -> None:
        self.console = console
        self._data_provider = data_provider
        self.monitor = data_provider
        self._cached_jitter: float = 0.0
        self._last_jitter_update: float = 0.0
        self._jitter_cache_interval: float = 5.0

    @property
    def data_provider(self) -> StatsDataProvider:
        return self._data_provider

    # ═══════════════════════════════════════════════════════════════════════════
    # Tier detection
    # ═══════════════════════════════════════════════════════════════════════════

    def _get_tier(self) -> LayoutTier:
        w = self.console.size.width
        if w < UI_COMPACT_THRESHOLD:
            return "compact"
        if w >= UI_WIDE_THRESHOLD:
            return "wide"
        return "standard"

    def _get_height_tier(self) -> HeightTier:
        h = self.console.size.height
        if h < 25:
            return "minimal"
        if h < 32:
            return "short"
        if h < 40:
            return "standard"
        return "full"

    # ═══════════════════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _fmt_uptime(start_time: datetime | None) -> str:
        if start_time is None:
            return t("na")
        start_time = _ensure_utc(start_time)
        if start_time is None:
            return t("na")
        total = int((datetime.now(timezone.utc) - start_time).total_seconds())
        d = total // 86400
        h = (total % 86400) // 3600
        m = (total % 3600) // 60
        s = total % 60
        parts = []
        if d:
            parts.append(f"{d}{t('time_d')}")
        if h or d:
            parts.append(f"{h}{t('time_h')}")
        if m or h or d:
            parts.append(f"{m}{t('time_m')}")
        parts.append(f"{s}{t('time_s')}")
        return " ".join(parts)

    @staticmethod
    def _fmt_since(ts: datetime | None) -> str:
        if ts is None:
            return t("never")
        ts = _ensure_utc(ts)
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

    @staticmethod
    def _progress_bar(pct: float, width: int = 20, color: str = _GREEN) -> str:
        pct = max(0.0, min(pct, 100.0))
        filled = int(round(pct / 100.0 * width))
        empty = width - filled
        return f"[{color}]{_BAR_FULL * filled}[/{color}][{_ACCENT_DIM}]{_BAR_EMPTY * empty}[/{_ACCENT_DIM}]"

    @staticmethod
    def _sparkline(values: list[float], width: int = 40) -> str:
        if not values:
            return f"[{_TEXT_DIM}]{t('no_data')}[/{_TEXT_DIM}]"
        data = values[-width:]
        if len(data) < 2:
            return f"[{_TEXT_DIM}]{t('waiting')}[/{_TEXT_DIM}]"
        # removing zero values for more accurate scaling
        valid_data = [v for v in data if v > 0]
        if not valid_data:
            return f"[{_TEXT_DIM}]{t('waiting')}[/{_TEXT_DIM}]"
            
        mn, mx = min(valid_data), max(valid_data)
        rng = mx - mn if mx != mn else 1.0
        chars = []
        for i, v in enumerate(data):
            if v == 0:
                # for zero values, we use the lowest symbol
                idx = 0
            else:
                idx = int((v - mn) / rng * (len(_SPARK_CHARS) - 1))
            idx = max(0, min(idx, len(_SPARK_CHARS) - 1))
            rel = (v - mn) / rng if v > 0 else 0

            if rel < 0.4:
                color = _GREEN
            elif rel < 0.7:
                color = _YELLOW
            else:
                color = _RED

            # Add a visual indicator to the very last bar
            is_last = (i == len(data) - 1)
            char = _SPARK_CHARS[idx]

            if is_last:
                chars.append(f"[bold {color} reverse]{char}[/bold {color} reverse]")
            else:
                chars.append(f"[{color}]{char}[/{color}]")

        return "".join(chars)

    @staticmethod
    def _kv_table(width: int, key_width: int = 14) -> Table:
        tbl = Table(show_header=False, box=None, padding=(0, 1), width=width)
        tbl.add_column("k", style=_TEXT_DIM, width=key_width, no_wrap=True)
        tbl.add_column("v", width=max(10, width - key_width - 3), no_wrap=True)
        return tbl

    @staticmethod
    def _dual_kv_table(width: int) -> Table:
        tbl = Table(show_header=False, box=None, padding=(0, 1), width=width)
        col_w = max(8, (width - 6) // 4)
        tbl.add_column("k1", style=_TEXT_DIM, width=col_w, no_wrap=True)
        tbl.add_column("v1", width=col_w, no_wrap=True)
        tbl.add_column("k2", style=_TEXT_DIM, width=col_w, no_wrap=True)
        tbl.add_column("v2", width=col_w, no_wrap=True)
        return tbl

    def _section_header(self, label: str, width: int) -> Text:
        line_len = max(0, width - len(label) - 7)
        return Text.from_markup(f"  [{_ACCENT_DIM}]── {label} {'─' * line_len}[/{_ACCENT_DIM}]")

    def _get_connection_state(self, snap: StatsSnapshot) -> tuple[str, str, str]:
        if snap["threshold_states"]["connection_lost"]:
            return t("status_disconnected"), _RED, _DOT_WARN
        recent = snap["recent_results"]
        if recent:
            loss30 = recent.count(False) / len(recent) * 100
            if loss30 > 5:
                return t("status_degraded"), _YELLOW, _DOT_WARN
        if snap["last_status"] == t("status_timeout"):
            return t("status_timeout_bar"), _RED, _DOT_WARN
        if snap["last_status"] == t("status_ok"):
            return t("status_connected"), _GREEN, _DOT_OK
        return t("status_waiting"), _TEXT_DIM, _DOT_WAIT

    @staticmethod
    def _lat_color(val: float | None) -> str:
        if val is None:
            return _RED
        if val > HOP_LATENCY_WARN:
            return _RED
        if val > HOP_LATENCY_GOOD:
            return _YELLOW
        return _GREEN

    @staticmethod
    def _render_trend_arrow(delta: float, threshold: float = 2.0) -> str:
        """Render trend arrow based on delta value."""
        if delta > threshold:
            return "↑"
        elif delta < -threshold:
            return "↓"
        return "→"

    @staticmethod
    def _render_sparkline(history: list) -> str:
        """Render mini chart from latency history using Unicode box characters."""
        if not history or len(history) < 2:
            return ""
        min_val, max_val = min(history), max(history)
        range_val = max_val - min_val if max_val != min_val else 1
        chars = " ▁▂▃▅▇"
        result = []
        recent = history[-6:]
        for val in recent:
            idx = min(5, int((val - min_val) / range_val * 5))
            result.append(chars[idx])
        return "".join(result)

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate text with ellipsis if it exceeds max_len."""
        if len(text) <= max_len:
            return text
        return text[:max_len - 1] + "…"

    # ═══════════════════════════════════════════════════════════════════════════
    # Render sections — all receive snap to avoid redundant snapshot calls
    # ═══════════════════════════════════════════════════════════════════════════

    def _render_header(self, snap: StatsSnapshot, width: int, tier: LayoutTier) -> Panel:
        now = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
        latest_version = snap.get("latest_version")
        version_up_to_date = snap.get("version_up_to_date", False)

        if latest_version:
            ver = f"[{_TEXT_DIM}]v{VERSION}[/{_TEXT_DIM}] [{_YELLOW}]→ v{latest_version}[/{_YELLOW}]"
        elif version_up_to_date:
            ver = f"[{_TEXT_DIM}]v{VERSION}[/{_TEXT_DIM}] [{_GREEN}]✓[/{_GREEN}]"
        else:
            ver = f"[{_TEXT_DIM}]v{VERSION}[/{_TEXT_DIM}]"

        if tier == "compact":
            txt = (
                f"[bold {_WHITE}]{t('title')}[/bold {_WHITE}]  "
                f"[{_ACCENT}]{TARGET_IP}[/{_ACCENT}]  "
                f"[{_TEXT_DIM}]{now}[/{_TEXT_DIM}]"
            )
        else:
            txt = (
                f"[bold {_WHITE}]{t('title')}[/bold {_WHITE}]  [{_TEXT_DIM}]›[/{_TEXT_DIM}]  "
                f"[bold {_ACCENT}]{TARGET_IP}[/bold {_ACCENT}]    "
                f"[{_TEXT_DIM}]│[/{_TEXT_DIM}]    {ver}    "
                f"[{_TEXT_DIM}]│[/{_TEXT_DIM}]    [{_TEXT_DIM}]{now}[/{_TEXT_DIM}]"
            )
        bg_col = _CRITICAL_BG if snap.get("threshold_states", {}).get("connection_lost") else _BG
        return Panel(
            txt, border_style=_ACCENT_DIM, box=box.SIMPLE, width=width,
            style=f"on {bg_col}",
            padding=(0, 1),
        )

    def _render_toast(self, snap: StatsSnapshot, width: int) -> Panel | None:
        if not SHOW_VISUAL_ALERTS or not snap.get("active_alerts"):
            return None
        
        alert = snap["active_alerts"][0]
        a_icon = {"warning": _DOT_WARN, "info": _DOT_OK, "success": "✔"}.get(alert["type"], _DOT_OK)
        bg_col = {"warning": _YELLOW, "critical": _RED, "info": _TEXT_DIM, "success": _GREEN}.get(alert["type"], _TEXT_DIM)
        fg_col = _BG

        txt = f"[bold {fg_col}]{a_icon} {alert['message']}[/bold {fg_col}]"
        return Panel(
            txt, border_style=bg_col, box=box.SIMPLE, width=width,
            style=f"on {bg_col}",
            padding=(0, 1),
        )

    def _render_dashboard(self, snap: StatsSnapshot, width: int, tier: LayoutTier) -> Panel:
        label, color, icon = self._get_connection_state(snap)
        current = snap["last_latency_ms"]
        ping_txt = f"{current}" if current != t("na") else "—"
        
        recent = snap["recent_results"]
        loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0
        l_color = _GREEN if loss30 < 1 else (_YELLOW if loss30 < 5 else _RED)
        loss_txt = f"{loss30:.1f}%"
        
        uptime_txt = self._fmt_uptime(snap["start_time"])
        ip_val = snap["public_ip"]
        lbl_ping = f"{t('ping').upper()}:"
        lbl_loss = f"{t('loss').upper()}:"
        lbl_up = f"{t('uptime').upper()}:"
        lbl_ip = f"{t('ip_label').upper()}:"
        cc = f" [{snap['country_code']}]" if snap["country_code"] else ""

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
                warmup_part = f"  [{_ACCENT_DIM}]│[/{_ACCENT_DIM}]  [{_TEXT_DIM}]{t('warmup_status')}:[/{_TEXT_DIM}] [{_YELLOW}]{curr_samples}/{max_req}[/{_YELLOW}]"
                warmup_part_compact = f"  [{_ACCENT_DIM}]│[/{_ACCENT_DIM}]  [{_YELLOW}]{t('warmup_compact')}:{curr_samples}/{max_req}[/{_YELLOW}]"

        if tier == "compact":
            parts = (
                f"  [bold {color}]{label}[/bold {color}]  [{_ACCENT_DIM}]│[/{_ACCENT_DIM}]  "
                f"[{_TEXT_DIM}]{lbl_ping}[/{_TEXT_DIM}] [bold {_WHITE}]{ping_txt}[/bold {_WHITE}]  [{_ACCENT_DIM}]│[/{_ACCENT_DIM}]  "
                f"[{_TEXT_DIM}]{lbl_loss}[/{_TEXT_DIM}] [bold {l_color}]{loss_txt}[/bold {l_color}]"
                f"{warmup_part_compact}"
            )
            bg_col = _CRITICAL_BG if snap.get("threshold_states", {}).get("connection_lost") else _BG
            return Panel(
                parts, border_style=color, box=box.SIMPLE, width=width,
                style=f"on {bg_col}",
                padding=(0, 1),
            )
        else:
            sep = f"  [{_ACCENT_DIM}]│[/{_ACCENT_DIM}]  "
            parts = (
                f"  [bold {color}]{label}[/bold {color}]"
                f"{sep}[{_TEXT_DIM}]{lbl_ping}[/{_TEXT_DIM}] [bold {_WHITE}]{ping_txt}[/bold {_WHITE}] [{_TEXT_DIM}]{t('ms')}[/{_TEXT_DIM}]"
                f"{sep}[{_TEXT_DIM}]{lbl_loss}[/{_TEXT_DIM}] [bold {l_color}]{loss_txt}[/bold {l_color}]"
                f"{sep}[{_TEXT_DIM}]{lbl_up}[/{_TEXT_DIM}] [{_WHITE}]{uptime_txt}[/{_WHITE}]"
                f"{sep}[{_TEXT_DIM}]{lbl_ip}[/{_TEXT_DIM}] [{_WHITE}]{ip_val}{cc}[/{_WHITE}]"
                f"{warmup_part}"
            )
            
            bg_col = _CRITICAL_BG if snap.get("threshold_states", {}).get("connection_lost") else _BG
            return Panel(
                parts, border_style=color, box=box.SIMPLE, width=width,
                style=f"on {bg_col}",
                padding=(0, 1),
            )

    # ── Metrics Panel (Latency + Stats merged) ──────────────────────────────

    def _render_metrics_panel(self, snap: StatsSnapshot, width: int,
                              tier: LayoutTier, h_tier: HeightTier) -> Panel:
        latencies = snap["latencies"]
        jitter_hist = snap.get("jitter_history", [])
        avg = (snap["total_latency_sum"] / snap["success"]) if snap["success"] > 0 else 0.0
        med = statistics.median(latencies) if latencies else 0.0
        jit = snap.get("jitter", 0.0)
        p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else (max(latencies) if latencies else 0.0)

        current = snap["last_latency_ms"]
        cur_txt = f"[bold {_WHITE}]{current}[/bold {_WHITE}] {t('ms')}" if current != t("na") else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
        best = f"[{_GREEN}]{snap['min_latency']:.1f}[/{_GREEN}]" if snap["min_latency"] != float("inf") else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
        peak = f"[{_RED}]{snap['max_latency']:.1f}[/{_RED}]" if snap["max_latency"] > 0 else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
        med_txt = f"[{_WHITE}]{med:.1f}[/{_WHITE}]" if latencies else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
        avg_txt = f"[{_YELLOW}]{avg:.1f}[/{_YELLOW}]" if snap["success"] > 0 else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
        p95_txt = f"[{_WHITE}]{p95:.1f}[/{_WHITE}]" if latencies else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"

        if snap["threshold_states"].get("high_avg_latency") and snap["success"]:
            avg_txt = f"[bold {_RED}]{avg:.1f} (!)[/bold {_RED}]"

        jit_txt = f"[{_WHITE}]{jit:.1f}[/{_WHITE}]" if jit > 0 else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
        if snap["threshold_states"].get("high_jitter"):
            jit_txt = f"[bold {_RED}]{jit:.1f} (!)[/bold {_RED}]"

        inner_w = max(20, width - 4)
        items: list[Table | Text] = []

        # ── Latency section ──
        items.append(self._section_header(t("lat"), inner_w))
        tbl = Table(show_header=False, box=None, padding=(0, 1), width=width)
        col_w = max(8, (width - 6) // 4)
        tbl.add_column("k1", style=_TEXT_DIM, width=col_w, no_wrap=True)
        tbl.add_column("v1", width=col_w, no_wrap=True)
        tbl.add_column("k2", style=_TEXT_DIM, width=col_w, no_wrap=True)
        tbl.add_column("v2", width=col_w, no_wrap=True)
        tbl.add_row(f"{t('current')}:", cur_txt, f"{t('average')}:", f"{avg_txt} {t('ms')}")
        tbl.add_row(f"{t('best')}:", f"{best} {t('ms')}", f"{t('median')}:", f"{med_txt} {t('ms')}")
        tbl.add_row(f"{t('p95')}:", f"{p95_txt} {t('ms')}", f"{t('jitter')}:", f"{jit_txt} {t('ms')}")
        items.append(tbl)

        # Sparklines: show in short/standard/full height and non-compact width
        if h_tier in ("short", "standard", "full") and tier != "compact":
            spark_w = max(20, width - 6)
            items.append(Text(""))
            
            # Latency sparkline
            if latencies:
                items.append(Text.from_markup(f"  [{_TEXT_DIM}]{t('latency_chart')} ›[/{_TEXT_DIM}]  {self._sparkline(list(latencies), width=spark_w)}"))
            else:
                items.append(Text.from_markup(f"  [{_TEXT_DIM}]{t('latency_chart')} ›[/{_TEXT_DIM}]  [{_TEXT_DIM}]{t('no_data')}[/{_TEXT_DIM}]"))
                
            # Jitter sparkline
            if jitter_hist:
                items.append(Text.from_markup(f"  [{_TEXT_DIM}]{t('jitter')} ›[/{_TEXT_DIM}]  {self._sparkline(list(jitter_hist), width=spark_w)}"))
            else:
                items.append(Text.from_markup(f"  [{_TEXT_DIM}]{t('jitter')} ›[/{_TEXT_DIM}]  [{_TEXT_DIM}]{t('no_data')}[/{_TEXT_DIM}]"))

        # ── Stats section ──
        items.append(self._section_header(t("stats"), inner_w))
        success_rate = (snap["success"] / snap["total"] * 100) if snap["total"] else 0.0
        loss_total = (snap["failure"] / snap["total"] * 100) if snap["total"] else 0.0
        recent = snap["recent_results"]
        loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0

        stbl = Table(show_header=False, box=None, padding=(0, 1), width=width)
        col_w = max(8, (width - 6) // 4)
        stbl.add_column("k1", style=_TEXT_DIM, width=col_w, no_wrap=True)
        stbl.add_column("v1", width=col_w, no_wrap=True)
        stbl.add_column("k2", style=_TEXT_DIM, width=col_w, no_wrap=True)
        stbl.add_column("v2", width=col_w, no_wrap=True)
        stbl.add_row(
            f"{t('sent')}:", f"[{_WHITE}]{snap['total']}[/{_WHITE}]",
            f"{t('lost')}:", f"[{_RED}]{snap['failure']}[/{_RED}]",
        )
        stbl.add_row(
            f"{t('ok_count')}:", f"[{_GREEN}]{snap['success']}[/{_GREEN}]",
            f"{t('losses')}:", f"[{_TEXT_DIM}]{loss_total:.1f}%[/{_TEXT_DIM}]",
        )
        items.append(stbl)

        # Progress bars: in standard/full height and non-compact width
        if h_tier in ("full", "standard") and tier != "compact":
            bar_w = max(10, width - 24)
            sr_color = _GREEN if success_rate > 95 else (_YELLOW if success_rate > 80 else _RED)
            l30_color = _GREEN if loss30 < 1 else (_YELLOW if loss30 < 5 else _RED)
            loss30_txt_bar = f"[{l30_color}]{loss30:.1f}%[/{l30_color}]"
            if snap["threshold_states"]["high_packet_loss"]:
                loss30_txt_bar += f" [{_RED}](!)[/{_RED}]"

            items.append(Text(""))
            items.append(Text.from_markup(
                f"  [{_TEXT_DIM}]{t('success_rate')}:[/{_TEXT_DIM}]     [{_GREEN}]{success_rate:.1f}%[/{_GREEN}]"
            ))
            items.append(Text.from_markup(f"  {self._progress_bar(success_rate, width=bar_w, color=sr_color)}"))
            items.append(Text(""))
            items.append(Text.from_markup(f"  [{_TEXT_DIM}]{t('loss_30m')}:[/{_TEXT_DIM}] {loss30_txt_bar}"))
            items.append(Text.from_markup(f"  {self._progress_bar(loss30, width=bar_w, color=l30_color)}"))

        # Consecutive losses (always shown)
        cons = snap["consecutive_losses"]
        if snap["threshold_states"]["connection_lost"]:
            cons_txt = f"[bold {_RED}]{cons} (!!!)[/bold {_RED}]"
        elif cons > 0:
            cons_txt = f"[{_YELLOW}]{cons}[/{_YELLOW}]"
        else:
            cons_txt = f"[{_GREEN}]{cons}[/{_GREEN}]"
        max_cons_txt = f"[{_RED}]{snap['max_consecutive_losses']}[/{_RED}]"

        items.append(Text(""))
        items.append(Text.from_markup(
            f"  [{_TEXT_DIM}]{t('consecutive')}:[/{_TEXT_DIM}] {cons_txt}"
            f"    [{_TEXT_DIM}]{t('max_label')}:[/{_TEXT_DIM}] {max_cons_txt}"
        ))

        return Panel(
            Group(*items),
            title=f"[bold {_ACCENT}]{t('lat')} & {t('stats')}[/bold {_ACCENT}]",
            title_align="left",
            border_style=_ACCENT_DIM,
            box=box.ROUNDED,
            width=width,
            style=f"on {_BG_PANEL}",
            padding=(0, 1),
        )

    # ── Analysis & Monitoring Panel (merged) ─────────────────────────────────

    def _render_analysis_panel(self, snap: StatsSnapshot, width: int,
                               tier: LayoutTier, h_tier: HeightTier) -> Panel:
        inner_w = max(20, width - 4)
        items: list[Table | Text] = []
        connection_lost = bool(snap.get("threshold_states", {}).get("connection_lost", False))

        # ── Problem analysis ──
        items.append(self._section_header(t("problem_analysis"), inner_w))
        problem_type = snap.get("current_problem_type", t("problem_none"))
        if connection_lost:
            problem_type = t("problem_isp")
        if problem_type == t("problem_none"):
            pt_txt = f"[{_GREEN}]{problem_type}[/{_GREEN}]"
        elif problem_type in [t("problem_isp"), t("problem_dns")]:
            pt_txt = f"[{_RED}]{problem_type}[/{_RED}]"
        elif problem_type in [t("problem_local"), t("problem_mtu")]:
            pt_txt = f"[{_YELLOW}]{problem_type}[/{_YELLOW}]"
        else:
            pt_txt = f"[{_WHITE}]{problem_type}[/{_WHITE}]"

        prediction = snap.get("problem_prediction", t("prediction_stable"))
        if connection_lost:
            prediction = t("prediction_risk")
        pred_txt = (
            f"[{_GREEN}]{prediction}[/{_GREEN}]"
            if prediction == t("prediction_stable")
            else f"[{_YELLOW}]{prediction}[/{_YELLOW}]"
        )

        prob_tbl = self._kv_table(width, key_width=14)
        prob_tbl.add_row(f"{t('problem_type')}:", pt_txt)
        prob_tbl.add_row(f"{t('prediction')}:", pred_txt)
        if h_tier not in ("minimal", "short"):
            pattern = snap.get("problem_pattern", "...")
            pat_txt = f"[{_WHITE}]{pattern}[/{_WHITE}]" if pattern != "..." else f"[{_TEXT_DIM}]...[/{_TEXT_DIM}]"
            prob_tbl.add_row(f"{t('pattern')}:", pat_txt)
        items.append(prob_tbl)

        # Last problem time
        if snap["last_problem_time"] is None:
            last_prob_txt = f"[{_GREEN}]{t('never')}[/{_GREEN}]"
        else:
            lpt = _ensure_utc(snap["last_problem_time"])
            if lpt is None:
                last_prob_txt = f"[{_GREEN}]{t('never')}[/{_GREEN}]"
            else:
                age = (datetime.now(timezone.utc) - lpt).total_seconds()
                since_txt = self._fmt_since(snap["last_problem_time"])
                last_prob_txt = f"[{_RED}]{since_txt}[/{_RED}]" if age < 60 else f"[{_YELLOW}]{since_txt}[/{_YELLOW}]"

        lp_tbl = self._kv_table(width, key_width=14)
        lp_tbl.add_row(f"{t('last_problem')}:", last_prob_txt)
        items.append(lp_tbl)

        # ── Route analysis ──
        items.append(self._section_header(t("route_analysis"), inner_w))
        route_hops = snap.get("route_hops", [])
        hop_count = len(route_hops)
        route_changed = snap.get("route_changed", False)
        problematic_hop = snap.get("route_problematic_hop")

        if connection_lost:
            route_hops = []
            hop_count = 0
            route_changed = False
            problematic_hop = None

        if connection_lost:
            rs_txt = f"[{_RED}]{t('status_disconnected')}[/{_RED}]"
        else:
            rs_txt = f"[{_YELLOW}]{t('route_changed')}[/{_YELLOW}]" if route_changed else f"[{_GREEN}]{t('route_stable')}[/{_GREEN}]"
        ph_txt = f"[{_RED}]{problematic_hop}[/{_RED}]" if problematic_hop else f"[{_GREEN}]{t('none_label')}[/{_GREEN}]"
        hc_txt = f"[{_WHITE}]{hop_count}[/{_WHITE}]" if hop_count > 0 else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"

        route_tbl = self._kv_table(width, key_width=14)
        route_tbl.add_row(f"{t('route_label')}:", rs_txt)
        route_tbl.add_row(f"{t('hops_count')}:", hc_txt)
        route_tbl.add_row(f"{t('problematic_hop_short')}:", ph_txt)

        if h_tier not in ("minimal", "short"):
            avg_route_latency = None
            if route_hops:
                lat_list = [h_["avg_latency"] for h_ in route_hops if h_.get("avg_latency") is not None]
                if lat_list:
                    avg_route_latency = statistics.mean(lat_list)
            avg_rl_txt = f"[{_WHITE}]{avg_route_latency:.1f}[/{_WHITE}] {t('ms')}" if avg_route_latency else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
            route_tbl.add_row(f"{t('avg_latency_short')}:", avg_rl_txt)

            route_diff = snap.get("route_last_diff_count", 0)
            route_cons = snap.get("route_consecutive_changes", 0)
            route_last_change = snap.get("route_last_change_time")
            if connection_lost:
                route_diff = 0
                route_cons = 0
                route_last_change = None
            diff_txt = f"[{_TEXT_DIM}]{route_diff} {t('hops_unit')}[/{_TEXT_DIM}]" if route_diff else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
            cons_r_txt = f"[{_TEXT_DIM}]{route_cons} / {self._fmt_since(route_last_change)}[/{_TEXT_DIM}]" if route_cons else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
            route_tbl.add_row(f"{t('changed_hops')}:", diff_txt)
            route_tbl.add_row(f"{t('changes')}:", cons_r_txt)
        items.append(route_tbl)

        # ── DNS ──
        items.append(self._section_header(t("dns"), inner_w))
        dns_results = snap.get("dns_results", {})
        if dns_results:
            type_parts = []
            total_time = 0
            time_count = 0
            for rt, res in sorted(dns_results.items()):
                dns_st = res.get("status", t("failed"))
                ms_v = res.get("response_time_ms")
                if ms_v:
                    total_time += ms_v
                    time_count += 1
                if dns_st == t("ok"):
                    type_parts.append(f"[{_GREEN}]{rt}✓[/{_GREEN}]")
                elif dns_st == t("slow"):
                    type_parts.append(f"[{_YELLOW}]{rt}~[/{_YELLOW}]")
                else:
                    type_parts.append(f"[{_RED}]{rt}✗[/{_RED}]")
            avg_dns = total_time / time_count if time_count > 0 else 0
            items.append(Text.from_markup(f"  {' '.join(type_parts)}  [{_TEXT_DIM}]{avg_dns:.0f}ms[/{_TEXT_DIM}]"))
        elif snap["dns_resolve_time"] is None:
            dns_fallback = f"  [{_RED}]{t('error')}[/{_RED}]" if SHOW_VISUAL_ALERTS else f"  [{_TEXT_DIM}]—[/{_TEXT_DIM}]"
            items.append(Text.from_markup(dns_fallback))
        else:
            ms_dns = snap["dns_resolve_time"]
            if snap["dns_status"] == t("ok"):
                items.append(Text.from_markup(f"  [{_GREEN}]{t('ok_label')}[/{_GREEN}] [{_TEXT_DIM}]({ms_dns:.0f}{t('ms')})[/{_TEXT_DIM}]"))
            elif snap["dns_status"] == t("slow"):
                items.append(Text.from_markup(f"  [{_YELLOW}]{t('slow')}[/{_YELLOW}] [{_TEXT_DIM}]({ms_dns:.0f}{t('ms')})[/{_TEXT_DIM}]"))
            else:
                items.append(Text.from_markup(f"  [{_RED}]{t('error')}[/{_RED}]"))

        # DNS Benchmark
        dns_benchmark = snap.get("dns_benchmark", {})
        if dns_benchmark and h_tier not in ("minimal", "short"):
            bench_parts = []
            all_avg: list[float] = []
            bench_queries = 0
            for tt in ["cached", "uncached", "dotcom"]:
                r = dns_benchmark.get(tt, {})
                lbl = tt[0].upper()
                if not r.get("success"):
                    bench_parts.append(f"[{_RED}]{lbl}:✗[/{_RED}]")
                else:
                    rv = r.get("response_time_ms")
                    v_str = f"{rv:.0f}" if rv else "—"
                    st = r.get("status", "failed")
                    c = _GREEN if st == t("ok") else (_YELLOW if st == t("slow") else _RED)
                    bench_parts.append(f"[{c}]{lbl}:{v_str}[/{c}]")
                bench_queries = max(bench_queries, r.get("queries", 0))
                if r.get("avg_ms") is not None:
                    all_avg.append(r["avg_ms"])
            bench_line = "  " + "  ".join(bench_parts)
            if bench_queries > 1 and all_avg:
                bench_line += f"  [{_TEXT_DIM}]│ {t('avg_ms')}:{sum(all_avg)/len(all_avg):.0f}{t('ms')}[/{_TEXT_DIM}]"
            items.append(Text.from_markup(bench_line))

        # ── Network (TTL, MTU, Traceroute) ──
        items.append(self._section_header(t("network"), inner_w))
        if connection_lost:
            ttl_txt = f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
        else:
            ttl = snap["last_ttl"]
            ttl_hops_val = snap["ttl_hops"]
            ttl_txt = f"[{_WHITE}]{ttl}[/{_WHITE}]"
            if ttl:
                if ttl_hops_val:
                    ttl_txt += f" [{_TEXT_DIM}]({ttl_hops_val} {t('hop_unit')})[/{_TEXT_DIM}]"
            else:
                ttl_txt = f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"

        local_mtu = snap["local_mtu"]
        path_mtu = snap["path_mtu"]
        if connection_lost:
            mtu_val = f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]/[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
            mtu_s = f"[{_RED}]{t('status_disconnected')}[/{_RED}]"
        else:
            mtu_val = f"[{_WHITE}]{local_mtu or '—'}[/{_WHITE}]/[{_WHITE}]{path_mtu or '—'}[/{_WHITE}]"
            mtu_status = snap.get("mtu_status", "...")
            if mtu_status == t("mtu_ok"):
                mtu_s = f"[{_GREEN}]{mtu_status}[/{_GREEN}]"
            elif mtu_status == t("mtu_low"):
                mtu_s = f"[{_YELLOW}]{mtu_status}[/{_YELLOW}]"
            elif mtu_status == t("mtu_fragmented"):
                mtu_s = f"[{_RED}]{mtu_status}[/{_RED}]"
            else:
                mtu_s = f"[{_TEXT_DIM}]{mtu_status}[/{_TEXT_DIM}]"

        if snap["traceroute_running"]:
            tr_txt = f"[{_YELLOW}]{t('traceroute_running')}[/{_YELLOW}]"
        elif snap["last_traceroute_time"]:
            tr_txt = f"[{_TEXT_DIM}]{self._fmt_since(snap['last_traceroute_time'])}[/{_TEXT_DIM}]"
        else:
            tr_txt = f"[{_TEXT_DIM}]{t('never')}[/{_TEXT_DIM}]"

        net_tbl = self._dual_kv_table(width)
        net_tbl.add_row(f"{t('ttl')}:", ttl_txt, f"{t('mtu')}:", mtu_val)
        net_tbl.add_row(f"{t('mtu_status_label')}:", mtu_s, f"{t('traceroute')}:", tr_txt)
        items.append(net_tbl)

        # ── Alerts ──
        items.append(self._section_header(t("notifications"), inner_w))
        alert_lines: list[str] = []
        if SHOW_VISUAL_ALERTS and snap["active_alerts"]:
            for alert in snap["active_alerts"]:
                a_icon = {"warning": _DOT_WARN, "info": _DOT_OK, "success": "✔"}.get(alert["type"], _DOT_OK)
                a_color = {"warning": _YELLOW, "critical": _RED, "info": _WHITE, "success": _GREEN}.get(alert["type"], _WHITE)
                alert_lines.append(f"  [{a_color}]{a_icon} {alert['message']}[/{a_color}]")
        else:
            alert_lines.append(f"  [{_TEXT_DIM}]{t('no_alerts')}[/{_TEXT_DIM}]")

        max_alerts = 2 if h_tier in ("minimal", "short") else ALERT_PANEL_LINES
        while len(alert_lines) < max_alerts:
            alert_lines.append(" ")
        alert_lines = alert_lines[:max_alerts]
        for line in alert_lines:
            items.append(Text.from_markup(line))

        return Panel(
            Group(*items),
            title=f"[bold {_ACCENT}]{t('analysis')} & {t('mon')}[/bold {_ACCENT}]",
            title_align="left",
            border_style=_ACCENT_DIM,
            box=box.ROUNDED,
            width=width,
            style=f"on {_BG_PANEL}",
        )

    # ── Hop Health Table ─────────────────────────────────────────────────────

    def _render_hop_panel(self, snap: StatsSnapshot, width: int,
                          tier: LayoutTier, h_tier: HeightTier) -> Panel:
        connection_lost = bool(snap.get("threshold_states", {}).get("connection_lost", False))
        hops = snap.get("hop_monitor_hops", [])
        discovering = snap.get("hop_monitor_discovering", False)
        panel_style = f"on {_BG}"
        title = f"[bold {_WHITE}]{t('hop_health')}[/bold {_WHITE}]"
        border = _ACCENT_DIM

        if connection_lost:
            return Panel(
                Text.from_markup(f"  [{_RED}]{t('status_disconnected')}[/{_RED}]"),
                title=title, title_align="left", border_style=border,
                box=box.SIMPLE, width=width, style=f"on {_BG}",
                padding=(0, 1),
            )

        if discovering and not hops:
            return Panel(
                Text.from_markup(f"  [{_TEXT_DIM}]{t('hop_discovering')}[/{_TEXT_DIM}]"),
                title=title, title_align="left", border_style=border,
                box=box.SIMPLE, width=width, style=f"on {_BG}",
                padding=(0, 1),
            )
        if not hops:
            return Panel(
                Text.from_markup(f"  [{_TEXT_DIM}]{t('hop_none')}[/{_TEXT_DIM}]"),
                title=title, title_align="left", border_style=border,
                box=box.SIMPLE, width=width, style=f"on {_BG}",
                padding=(0, 1),
            )

        # Adaptive columns based on width tier
        show_extended = tier != "compact"
        show_geo = tier == "wide"

        tbl = Table(
            show_header=True, header_style=f"bold {_TEXT_DIM}",
            box=box.SIMPLE_HEAD, padding=(0, 1), expand=True,
            border_style=_ACCENT_DIM,
        )
        tbl.add_column(t("hop_col_num"), style=_TEXT_DIM, width=3, justify="right", no_wrap=True)
        tbl.add_column("", width=1, justify="center", no_wrap=True)
        if show_extended:
            tbl.add_column(t("hop_col_min"), width=6, justify="right", no_wrap=True)
        tbl.add_column(t("hop_col_avg"), width=6, justify="right", no_wrap=True)
        tbl.add_column(t("hop_col_last"), width=6, justify="right", no_wrap=True)
        if show_extended:
            tbl.add_column(t("hop_col_delta"), width=7, justify="right", no_wrap=True)
            tbl.add_column(t("hop_col_jitter"), width=8, justify="right", no_wrap=True)
        tbl.add_column(t("hop_col_loss"), width=6, justify="right", no_wrap=True)
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
            host_txt = f"{hostname} [{_TEXT_DIM}][{ip}][/{_TEXT_DIM}]" if (hostname and hostname != ip) else ip

            # Status dot
            if not ok:
                dot = f"[{_RED}]●[/{_RED}]"
            elif loss > 0:
                dot = f"[{_YELLOW}]●[/{_YELLOW}]"
            else:
                dot = f"[{_GREEN}]●[/{_GREEN}]"

            def _lf(val: Any) -> str:
                if val is None:
                    return f"[{_RED}]*[/{_RED}]"
                c = self._lat_color(val)
                return f"[{c}]{val:.0f}[/{c}]"

            last_txt = f"[{_RED}]*[/{_RED}]" if (not ok or lat is None) else _lf(lat)

            # Loss text
            if loss > 10:
                loss_txt = f"[{_RED}]{loss:.0f}![/{_RED}]"
            elif loss > 0:
                loss_txt = f"[{_YELLOW}]{loss:.0f}%[/{_YELLOW}]"
            else:
                loss_txt = f"[{_GREEN}]{loss:.0f}%[/{_GREEN}]"

            row_style = _TEXT_DIM if (not ok and hop.get("total_pings", 0) > 2) else ""

            row = [str(hop_num), dot]
            if show_extended:
                row.append(_lf(mn))
            row.extend([_lf(avg_h if avg_h > 0 else None), last_txt])
            if show_extended:
                trend = self._render_trend_arrow(delta)
                if delta > 0:
                    d_txt = f"[{_YELLOW}]{trend}+{delta:.0f}[/{_YELLOW}]"
                elif delta < 0:
                    d_txt = f"[{_GREEN}]{trend}{delta:.0f}[/{_GREEN}]"
                else:
                    d_txt = f"[{_TEXT_DIM}]{trend}—[/{_TEXT_DIM}]"
                j_txt = f"[{_TEXT_DIM}]{jitter_h:.0f}[/{_TEXT_DIM}]" if jitter_h > 0 else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
                row.extend([d_txt, j_txt])
            row.append(loss_txt)
            if show_geo:
                row.append(f"[{_TEXT_DIM}]{asn_display}[/{_TEXT_DIM}]")
                row.append(f"[{_TEXT_DIM}]{country_code}[/{_TEXT_DIM}]" if country_code else "")
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
            items.append(Text.from_markup(f"  [{_TEXT_DIM}]+{more_txt}[/{_TEXT_DIM}]"))

        if worst_hop and worst_lat > HOP_LATENCY_GOOD:
            w_ip = worst_hop.get("ip", "?")
            w_num = worst_hop.get("hop", "?")
            if worst_lat == float("inf"):
                items.append(Text.from_markup(f"  [{_RED}]{t('hop_worst')}: #{w_num} {w_ip} — {t('hop_down')}[/{_RED}]"))
            else:
                items.append(Text.from_markup(f"  [{_YELLOW}]{t('hop_worst')}: #{w_num} {w_ip} — {worst_lat:.0f} {t('ms')}[/{_YELLOW}]"))

        if discovering:
            items.append(Text.from_markup(f"  [{_TEXT_DIM} italic]{t('hop_discovering')}[/{_TEXT_DIM} italic]"))

        return Panel(
            Group(*items),
            title=title, title_align="left", border_style=border,
            box=box.SIMPLE, width=width, style=panel_style,
            padding=(0, 1),
        )

    # ── Footer ───────────────────────────────────────────────────────────────

    def _render_footer(self, snap: StatsSnapshot, width: int, tier: LayoutTier) -> Panel:
        log_path = LOG_FILE.replace(os.path.expanduser("~"), "~")
        txt = f"[{_TEXT_DIM}]{t('footer').format(log_file=log_path)}[/{_TEXT_DIM}]"
        latest_version = snap.get("latest_version")
        if latest_version:
            txt += f"    [{_YELLOW}]{_DOT_WARN} {t('update_available').format(current=VERSION, latest=latest_version)}[/{_YELLOW}]"
        return Panel(txt, border_style=_ACCENT_DIM, box=box.SIMPLE, width=width, style=f"on {_BG}", padding=(0, 1))

    # ═══════════════════════════════════════════════════════════════════════════
    # Layout generation — single snapshot, height-aware sizing
    # ═══════════════════════════════════════════════════════════════════════════

    def generate_layout(self) -> Layout:
        w = max(60, self.console.size.width)
        h = max(20, self.console.size.height)
        tier = self._get_tier()
        h_tier = self._get_height_tier()
        inner = w - 2

        # Single snapshot for entire render cycle
        snap = self.monitor.get_stats_snapshot()

        layout = Layout(name="root")

        header_panel = self._render_header(snap, w, tier)
        toast_panel = self._render_toast(snap, w)
        dashboard_panel = self._render_dashboard(snap, w, tier)
        footer_panel = self._render_footer(snap, w, tier)

        connection_lost = bool(snap.get("threshold_states", {}).get("connection_lost", False))
        hops = snap.get("hop_monitor_hops", [])
        if connection_lost:
            hops = []
        if h_tier == "minimal":
            hop_display_count = min(len(hops), 5)
        elif h_tier == "short":
            hop_display_count = min(len(hops), 8)
        else:
            hop_display_count = len(hops)

        toast_h = 3 if toast_panel else 0
        fixed_lines = 9 + toast_h
        remaining = h - fixed_lines

        hop_panel_h = hop_display_count + 5 if hops else 4
        hop_panel_h = min(hop_panel_h, max(4, remaining * 2 // 3))

        body_h = max(8, remaining - hop_panel_h)
        hop_panel = self._render_hop_panel(snap, w, tier, h_tier)

        splits = [Layout(header_panel, size=3, name="header")]
        if toast_panel:
            splits.append(Layout(toast_panel, size=3, name="toast"))
        splits.append(Layout(dashboard_panel, size=3, name="dashboard"))

        if tier == "compact":
            metrics_panel = self._render_metrics_panel(snap, w, tier, h_tier)
            analysis_panel = self._render_analysis_panel(snap, w, tier, h_tier)

            if h_tier == "minimal":
                splits.append(Layout(hop_panel, name="hops", ratio=1))
                splits.append(Layout(footer_panel, size=3, name="footer"))
                layout.split_column(*splits)
            else:
                body = Layout(name="body_inner")
                body.split_column(
                    Layout(metrics_panel, name="metrics", ratio=1),
                    Layout(analysis_panel, name="analysis", ratio=1),
                )
                splits.append(Layout(name="body", size=body_h))
                splits.append(Layout(hop_panel, name="hops", size=hop_panel_h))
                splits.append(Layout(footer_panel, size=3, name="footer"))
                layout.split_column(*splits)
                layout["body"].update(body)
        else:
            left_w = (inner // 2) - 1
            right_w = inner - left_w - 1

            metrics_panel = self._render_metrics_panel(snap, left_w, tier, h_tier)
            analysis_panel = self._render_analysis_panel(snap, right_w, tier, h_tier)

            body = Layout(name="body_inner")
            body.split_row(
                Layout(metrics_panel, name="metrics", ratio=1),
                Layout(analysis_panel, name="analysis", ratio=1),
            )

            splits.append(Layout(name="body", size=body_h))
            splits.append(Layout(hop_panel, name="hops", size=hop_panel_h))
            splits.append(Layout(footer_panel, size=3, name="footer"))
            layout.split_column(*splits)
            layout["body"].update(body)

        return layout


__all__ = ["MonitorUI"]
