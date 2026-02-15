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
        # Naive datetime - assume it's local time and convert to UTC
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
        t,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Style constants
# ═══════════════════════════════════════════════════════════════════════════════

# Color palette – black theme with orange accent
_BG = "#000000"          # True black background
_BG_PANEL = "#0a0a0a"    # Near-black panel background
_ACCENT = "#ff8c00"      # Warm orange accent for borders & titles
_ACCENT_DIM = "#3d2800"  # Dim amber for section dividers
_TEXT = "#d4d4d4"        # Primary text
_TEXT_DIM = "#707070"    # Secondary / label text
_GREEN = "#4ec94e"       # Semantic: good
_YELLOW = "#ffb347"      # Semantic: warning (soft orange)
_RED = "#ff4444"         # Semantic: critical
_WHITE = "#f0f0f0"       # High-contrast values

# Unicode elements
_SPARK_CHARS = "▁▂▃▄▅▆▇█"
_BAR_FULL = "━"
_BAR_EMPTY = "╌"
_DOT_OK = "●"
_DOT_WARN = "▲"
_DOT_ERR = "✖"
_DOT_WAIT = "○"
_ICON_INFO = "◆"

# Layout tier type
LayoutTier = Literal["compact", "standard", "wide"]


class MonitorUI:
    """
    Adaptive Rich-based UI for network monitoring.

    Renders in 3 tiers based on terminal width:
    - compact  (<100 cols): single column, essential info only
    - standard (100–149):   2-column grid, full detail
    - wide     (≥150):      3-column grid, maximum detail
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
    # Layout tier detection
    # ═══════════════════════════════════════════════════════════════════════════

    def _get_tier(self) -> LayoutTier:
        w = self.console.size.width
        if w < UI_COMPACT_THRESHOLD:
            return "compact"
        if w >= UI_WIDE_THRESHOLD:
            return "wide"
        return "standard"

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
        mn, mx = min(data), max(data)
        rng = mx - mn if mx != mn else 1.0
        chars = []
        for v in data:
            idx = int((v - mn) / rng * (len(_SPARK_CHARS) - 1))
            idx = max(0, min(idx, len(_SPARK_CHARS) - 1))
            rel = (v - mn) / rng
            if rel < 0.4:
                color = _GREEN
            elif rel < 0.7:
                color = _YELLOW
            else:
                color = _RED
            chars.append(f"[{color}]{_SPARK_CHARS[idx]}[/{color}]")
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
            return t("status_disconnected"), _RED, _DOT_ERR
        recent = snap["recent_results"]
        if recent:
            loss30 = recent.count(False) / len(recent) * 100
            if loss30 > 5:
                return t("status_degraded"), _YELLOW, _DOT_WARN
        if snap["last_status"] == t("status_timeout"):
            return t("status_timeout_bar"), _RED, _DOT_ERR
        if snap["last_status"] == t("status_ok"):
            return t("status_connected"), _GREEN, _DOT_OK
        return t("status_waiting"), _TEXT_DIM, _DOT_WAIT

    # Helper for semantic coloring of latency values
    @staticmethod
    def _lat_color(val: float | None) -> str:
        if val is None:
            return _RED
        if val > HOP_LATENCY_WARN:
            return _RED
        if val > HOP_LATENCY_GOOD:
            return _YELLOW
        return _GREEN

    # Render sparkline from latency history
    @staticmethod
    def _render_sparkline(history: list) -> str:
        """Render mini chart from latency history using Unicode box characters."""
        if not history or len(history) < 2:
            return ""
        
        # Normalize to 6 levels
        min_val, max_val = min(history), max(history)
        range_val = max_val - min_val if max_val != min_val else 1
        
        chars = " ▁▂▃▅▇"  # 6 levels (index 0-5)
        
        result = []
        # Take only last 6 values to fit column width
        recent = history[-6:]
        for val in recent:
            idx = min(5, int((val - min_val) / range_val * 5))
            result.append(chars[idx])
        
        return "".join(result)

    # Render trend arrow based on delta
    @staticmethod
    def _render_trend_arrow(delta: float, threshold: float = 2.0) -> str:
        """Render trend arrow based on delta value."""
        if delta > threshold:
            return "↑"  # increasing
        elif delta < -threshold:
            return "↓"  # decreasing
        return "→"  # stable

    # ═══════════════════════════════════════════════════════════════════════════
    # Panels
    # ═══════════════════════════════════════════════════════════════════════════

    def render_header(self, width: int, tier: LayoutTier) -> Panel:
        now = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
        snap = self.monitor.get_stats_snapshot()
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
        return Panel(
            txt, border_style=_ACCENT, box=box.HORIZONTALS, width=width,
            style=f"on {_BG}",
        )

    def render_status_bar(self, width: int, tier: LayoutTier) -> Panel:
        snap = self.monitor.get_stats_snapshot()
        label, color, icon = self._get_connection_state(snap)

        current = snap["last_latency_ms"]
        ping_txt = f"[bold {_WHITE}]{current}[/bold {_WHITE}] {t('ms')}" if current != t("na") else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"

        recent = snap["recent_results"]
        loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0
        l_color = _GREEN if loss30 < 1 else (_YELLOW if loss30 < 5 else _RED)
        loss_txt = f"[{l_color}]{loss30:.1f}%[/{l_color}]"

        uptime_txt = self._fmt_uptime(snap["start_time"])

        ip_val = snap["public_ip"]
        cc = f" [{snap['country_code']}]" if snap["country_code"] else ""

        sep = f"  [{_ACCENT_DIM}]│[/{_ACCENT_DIM}]  "

        if tier == "compact":
            parts = (
                f"  [bold {color}]{icon} {label}[/bold {color}]"
                f"{sep}{t('ping')}: {ping_txt}"
                f"{sep}{t('loss')}: {loss_txt}"
            )
        else:
            parts = (
                f"   [bold {color}]{icon} {label}[/bold {color}]"
                f"   {sep}{t('ping')}: {ping_txt}"
                f"{sep}{t('loss')}: {loss_txt}"
                f"{sep}{t('uptime')}: [{_WHITE}]{uptime_txt}[/{_WHITE}]"
                f"{sep}IP: [{_WHITE}]{ip_val}[/{_WHITE}][{_TEXT_DIM}]{cc}[/{_TEXT_DIM}]"
            )
        return Panel(
            parts, border_style=color, box=box.HEAVY, width=width,
            style=f"on {_BG}",
        )

    def render_latency_panel(self, width: int, tier: LayoutTier) -> Panel:
        snap = self.monitor.get_stats_snapshot()
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

        tbl = self._dual_kv_table(width)
        tbl.add_row(f"{t('current')}:", cur_txt, f"{t('best')}:", f"{best} {t('ms')}")
        tbl.add_row(f"{t('average')}:", f"{avg_txt} {t('ms')}", f"{t('p95')}:", f"{p95_txt} {t('ms')}")
        tbl.add_row(f"{t('median')}:", f"{med_txt} {t('ms')}", f"{t('jitter')}:", f"{jit_txt} {t('ms')}")

        items: list[Table | Text] = [tbl]

        # Sparklines: show in standard/wide, hide in compact
        if tier != "compact":
            spark_w = max(20, width - 6)
            items.append(Text(""))
            items.append(Text.from_markup(f"  [{_TEXT_DIM}]{t('latency_chart')}[/{_TEXT_DIM}]"))
            items.append(Text.from_markup(f"  {self._sparkline(list(latencies), width=spark_w)}"))
            items.append(Text.from_markup(f"  [{_TEXT_DIM}]{t('jitter')}[/{_TEXT_DIM}]"))
            items.append(Text.from_markup(f"  {self._sparkline(list(jitter_hist) or [jit], width=spark_w)}"))

        return Panel(
            Group(*items),
            title=f"[bold {_ACCENT}]{t('lat')}[/bold {_ACCENT}]",
            title_align="left",
            border_style=_ACCENT_DIM,
            box=box.ROUNDED,
            width=width,
            style=f"on {_BG_PANEL}",
        )

    def render_stats_panel(self, width: int, tier: LayoutTier) -> Panel:
        snap = self.monitor.get_stats_snapshot()
        success_rate = (snap["success"] / snap["total"] * 100) if snap["total"] else 0.0
        loss_total = (snap["failure"] / snap["total"] * 100) if snap["total"] else 0.0
        recent = snap["recent_results"]
        loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0

        # Counters
        tbl = self._dual_kv_table(width)
        tbl.add_row(
            f"{t('sent')}:", f"[{_WHITE}]{snap['total']}[/{_WHITE}]",
            f"{t('ok_count')}:", f"[{_GREEN}]{snap['success']}[/{_GREEN}]",
        )
        tbl.add_row(
            f"{t('lost')}:", f"[{_RED}]{snap['failure']}[/{_RED}]",
            f"{t('losses')}:", f"[{_TEXT_DIM}]{loss_total:.1f}%[/{_TEXT_DIM}]",
        )

        items: list[Table | Text] = [tbl]

        # Progress bars: show in standard/wide
        if tier != "compact":
            bar_w = max(10, width - 24)
            sr_color = _GREEN if success_rate > 95 else (_YELLOW if success_rate > 80 else _RED)
            l30_color = _GREEN if loss30 < 1 else (_YELLOW if loss30 < 5 else _RED)

            loss30_txt = f"[{l30_color}]{loss30:.1f}%[/{l30_color}]"
            if snap["threshold_states"]["high_packet_loss"]:
                loss30_txt += f" [{_RED}](!)[/{_RED}]"

            items.append(Text(""))
            items.append(Text.from_markup(
                f"  [{_TEXT_DIM}]{t('success_rate')}:[/{_TEXT_DIM}]     [{_GREEN}]{success_rate:.1f}%[/{_GREEN}]"
            ))
            items.append(Text.from_markup(f"  {self._progress_bar(success_rate, width=bar_w, color=sr_color)}"))
            items.append(Text(""))
            items.append(Text.from_markup(f"  [{_TEXT_DIM}]{t('loss_30m')}:[/{_TEXT_DIM}] {loss30_txt}"))
            items.append(Text.from_markup(f"  {self._progress_bar(loss30, width=bar_w, color=l30_color)}"))

        # Consecutive losses
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
            title=f"[bold {_ACCENT}]{t('stats')}[/bold {_ACCENT}]",
            title_align="left",
            border_style=_ACCENT_DIM,
            box=box.ROUNDED,
            width=width,
            style=f"on {_BG_PANEL}",
        )

    def render_trend_panel(self, width: int, tier: LayoutTier) -> Panel:
        snap = self.monitor.get_stats_snapshot()
        recent = snap["recent_results"]
        loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0
        jitter_hist = snap.get("jitter_history", [])
        hops = snap.get("route_hops", [])

        tbl = self._kv_table(width, key_width=16)
        loss_color = _GREEN if loss30 < 1 else (_YELLOW if loss30 < 5 else _RED)
        tbl.add_row(f"{t('loss_30m')}:", f"[{loss_color}]{loss30:.1f}%[/{loss_color}]")

        if jitter_hist:
            jit_now = jitter_hist[-1]
            if tier != "compact":
                tbl.add_row(f"{t('jitter_trend')}:", self._sparkline(jitter_hist, width=max(10, width - 24)))
            tbl.add_row(f"{t('jitter_now')}:", f"[{_WHITE}]{jit_now:.1f} {t('ms')}[/{_WHITE}]")
        else:
            tbl.add_row(f"{t('jitter_trend')}:", f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]")

        tbl.add_row(f"{t('hops_count')}:", f"[{_WHITE}]{len(hops)}[/{_WHITE}]")

        return Panel(
            tbl,
            title=f"[bold {_ACCENT}]{t('trends')}[/bold {_ACCENT}]",
            title_align="left",
            border_style=_ACCENT_DIM,
            box=box.ROUNDED,
            width=width,
            style=f"on {_BG_PANEL}",
        )

    def render_analysis_panel(self, width: int, tier: LayoutTier) -> Panel:
        snap = self.monitor.get_stats_snapshot()
        inner_w = max(20, width - 4)

        # ── Problem analysis ──
        problem_type = snap.get("current_problem_type", t("problem_none"))
        if problem_type == t("problem_none"):
            pt_txt = f"[{_GREEN}]{problem_type}[/{_GREEN}]"
        elif problem_type in [t("problem_isp"), t("problem_dns")]:
            pt_txt = f"[{_RED}]{problem_type}[/{_RED}]"
        elif problem_type in [t("problem_local"), t("problem_mtu")]:
            pt_txt = f"[{_YELLOW}]{problem_type}[/{_YELLOW}]"
        else:
            pt_txt = f"[{_WHITE}]{problem_type}[/{_WHITE}]"

        prediction = snap.get("problem_prediction", t("prediction_stable"))
        pred_txt = (
            f"[{_GREEN}]{prediction}[/{_GREEN}]"
            if prediction == t("prediction_stable")
            else f"[{_YELLOW}]{prediction}[/{_YELLOW}]"
        )
        pattern = snap.get("problem_pattern", "...")
        pat_txt = f"[{_WHITE}]{pattern}[/{_WHITE}]" if pattern != "..." else f"[{_TEXT_DIM}]...[/{_TEXT_DIM}]"

        prob_tbl = self._kv_table(width, key_width=14)
        prob_tbl.add_row(f"{t('problem_type')}:", pt_txt)
        prob_tbl.add_row(f"{t('prediction')}:", pred_txt)
        if tier != "compact":
            prob_tbl.add_row(f"{t('pattern')}:", pat_txt)

        # ── Route analysis ──
        hops = snap.get("route_hops", [])
        hop_count = len(hops)
        hop_count_txt = f"[{_WHITE}]{hop_count}[/{_WHITE}]" if hop_count > 0 else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"

        problematic_hop = snap.get("route_problematic_hop")
        ph_txt = f"[{_RED}]{problematic_hop}[/{_RED}]" if problematic_hop else f"[{_GREEN}]{t('none_label')}[/{_GREEN}]"

        route_changed = snap.get("route_changed", False)
        rs_txt = (
            f"[{_YELLOW}]{t('route_changed')}[/{_YELLOW}]"
            if route_changed
            else f"[{_GREEN}]{t('route_stable')}[/{_GREEN}]"
        )

        avg_route_latency = None
        if hops:
            lat_list: list[float] = [h["avg_latency"] for h in hops if h.get("avg_latency") is not None]
            if lat_list:
                avg_route_latency = statistics.mean(lat_list)
        avg_rl_txt = f"[{_WHITE}]{avg_route_latency:.1f}[/{_WHITE}] {t('ms')}" if avg_route_latency else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"

        route_tbl = self._kv_table(width, key_width=14)
        route_tbl.add_row(f"{t('route_label')}:", rs_txt)
        route_tbl.add_row(f"{t('hops_count')}:", hop_count_txt)
        route_tbl.add_row(f"{t('problematic_hop_short')}:", ph_txt)

        if tier != "compact":
            route_tbl.add_row(f"{t('avg_latency_short')}:", avg_rl_txt)

            route_diff = snap.get("route_last_diff_count", 0)
            route_cons = snap.get("route_consecutive_changes", 0)
            route_last_change = snap.get("route_last_change_time")
            diff_txt = f"[{_TEXT_DIM}]{route_diff} {t('hops_unit')}[/{_TEXT_DIM}]" if route_diff else f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
            if route_cons:
                since_str = self._fmt_since(route_last_change) if route_last_change else "..."
                cons_txt = f"[{_TEXT_DIM}]{route_cons} / {since_str}[/{_TEXT_DIM}]"
            else:
                cons_txt = f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"
            route_tbl.add_row(f"{t('changed_hops')}:", diff_txt)
            route_tbl.add_row(f"{t('changes')}:", cons_txt)

        # Last problem
        if snap["last_problem_time"] is None:
            last_prob_txt = f"[{_GREEN}]{t('never')}[/{_GREEN}]"
        else:
            last_problem_time = _ensure_utc(snap["last_problem_time"])
            if last_problem_time is None:
                last_prob_txt = f"[{_GREEN}]{t('never')}[/{_GREEN}]"
            else:
                age = (datetime.now(timezone.utc) - last_problem_time).total_seconds()
                since_txt = self._fmt_since(snap["last_problem_time"])
                last_prob_txt = f"[{_RED}]{since_txt}[/{_RED}]" if age < 60 else f"[{_YELLOW}]{since_txt}[/{_YELLOW}]"

        prob_time_tbl = self._kv_table(width, key_width=14)
        prob_time_tbl.add_row(f"{t('last_problem')}:", last_prob_txt)

        grp = Group(
            self._section_header(t("problem_analysis"), inner_w),
            prob_tbl,
            prob_time_tbl,
            self._section_header(t("route_analysis"), inner_w),
            route_tbl,
        )
        return Panel(
            grp,
            title=f"[bold {_ACCENT}]{t('analysis')}[/bold {_ACCENT}]",
            title_align="left",
            border_style=_ACCENT_DIM,
            box=box.ROUNDED,
            width=width,
            style=f"on {_BG_PANEL}",
        )

    def render_hop_panel(self, width: int, tier: LayoutTier) -> Panel:
        snap = self.monitor.get_stats_snapshot()
        hops = snap.get("hop_monitor_hops", [])
        discovering = snap.get("hop_monitor_discovering", False)

        panel_style = f"on {_BG_PANEL}"
        title = f"[bold {_ACCENT}]{t('hop_health')}[/bold {_ACCENT}]"
        border = _ACCENT_DIM

        if discovering and not hops:
            return Panel(
                Text.from_markup(f"  [{_TEXT_DIM}]{t('hop_discovering')}[/{_TEXT_DIM}]"),
                title=title, title_align="left", border_style=border,
                box=box.ROUNDED, width=width, style=panel_style,
            )

        if not hops:
            return Panel(
                Text.from_markup(f"  [{_TEXT_DIM}]{t('hop_none')}[/{_TEXT_DIM}]"),
                title=title, title_align="left", border_style=border,
                box=box.ROUNDED, width=width, style=panel_style,
            )

        tbl = Table(
            show_header=True, header_style=f"bold {_TEXT_DIM}",
            box=None, padding=(0, 1), expand=True,
        )
        tbl.add_column(t("hop_col_num"), style=_TEXT_DIM, width=3, justify="right")
        # Add sparkline column for compact mode
        if tier == "compact":
            tbl.add_column("", width=6, justify="left")
        tbl.add_column(t("hop_col_min"), width=9, justify="right")
        tbl.add_column(t("hop_col_avg"), width=9, justify="right")
        tbl.add_column(t("hop_col_last"), width=9, justify="right")
        # Add delta and jitter columns for standard/wide modes
        if tier != "compact":
            tbl.add_column(t("hop_col_delta"), width=7, justify="right")
            tbl.add_column(t("hop_col_jitter"), width=8, justify="right")
        tbl.add_column(t("hop_col_loss"), width=7, justify="right")
        tbl.add_column(t("hop_col_host"), ratio=1, no_wrap=True)

        worst_hop = None
        worst_lat = 0.0

        # In compact: limit displayed hops
        display_hops = hops if tier != "compact" else hops[:8]

        for h in display_hops:
            hop_num = h["hop"]
            lat = h.get("last_latency")
            avg = h.get("avg_latency", 0.0)
            mn = h.get("min_latency")
            ok = h.get("last_ok", True)
            loss = h.get("loss_pct", 0.0)
            ip = h.get("ip", "?")
            hostname = h.get("hostname", ip)
            
            # New fields for Etap 1
            jitter = h.get("jitter", 0.0)
            delta = h.get("latency_delta", 0.0)
            latency_history = h.get("latency_history", [])
            
            # Stage 3 - geolocation fields
            country = h.get("country", "")
            country_code = h.get("country_code", "")
            asn = h.get("asn", "")
            
            if hostname and hostname != ip and tier != "compact":
                host_txt = f"{hostname} [{_TEXT_DIM}][{ip}][/{_TEXT_DIM}]"
            else:
                host_txt = ip
            
            # Add geo info after hostname (for all tiers)
            if country_code or asn:
                geo_parts = []
                if country_code:
                    geo_parts.append(country_code)
                if asn:
                    geo_parts.append(f"AS{asn}")
                geo_txt = f" [{_TEXT_DIM}]({' '.join(geo_parts)})[/{_TEXT_DIM}]"
                host_txt = host_txt + geo_txt

            def _lat_fmt(val: Any) -> str:
                if val is None:
                    return f"[{_RED}]  *[/{_RED}]"
                c = self._lat_color(val)
                return f"[{c}]{val:.0f} {t('ms')}[/{c}]"

            last_txt = f"[{_RED}]  *[/{_RED}]" if (not ok or lat is None) else _lat_fmt(lat)
            min_txt = _lat_fmt(mn)
            avg_txt = _lat_fmt(avg if avg > 0 else None)
            
            # Sparkline for compact mode
            if tier == "compact":
                spark = self._render_sparkline(latency_history)
                if spark:
                    spark_txt = f"[{_TEXT_DIM}]{spark}[/{_TEXT_DIM}]"
                else:
                    spark_txt = ""
                # Compact: show sparkline + trend arrow instead of delta/jitter
                trend = self._render_trend_arrow(delta)
                if trend and delta != 0:
                    if delta > 0:
                        trend_txt = f"[{_YELLOW}]{trend}[/{_YELLOW}]"
                    else:
                        trend_txt = f"[{_GREEN}]{trend}[/{_GREEN}]"
                else:
                    trend_txt = f"[{_TEXT_DIM}]{trend}[/{_TEXT_DIM}]"
                last_txt = f"{last_txt} {trend_txt}"
            
            # Delta formatting (standard/wide mode)
            if tier != "compact":
                trend = self._render_trend_arrow(delta)
                if delta > 0:
                    delta_txt = f"[{_YELLOW}]{trend}+{delta:.0f}[/{_YELLOW}]"
                elif delta < 0:
                    delta_txt = f"[{_GREEN}]{trend}{delta:.0f}[/{_GREEN}]"
                else:
                    delta_txt = f"[{_TEXT_DIM}]{trend}—[/{_TEXT_DIM}]"
                
                # Jitter formatting
                if jitter > 0:
                    jitter_txt = f"[{_TEXT_DIM}]{jitter:.1f}[/{_TEXT_DIM}]"
                else:
                    jitter_txt = f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"

            if loss > 10:
                loss_txt = f"[{_RED}]{loss:.1f}![/{_RED}]"
            elif loss > 0:
                loss_txt = f"[{_YELLOW}]{loss:.1f}%[/{_YELLOW}]"
            else:
                loss_txt = f"[{_GREEN}]{loss:.1f}%[/{_GREEN}]"

            row_style = _TEXT_DIM if (not ok and h.get("total_pings", 0) > 2) else ""
            
            # Build row based on tier
            if tier == "compact":
                # Compact: spark + trend
                tbl.add_row(str(hop_num), spark_txt, min_txt, avg_txt, last_txt, loss_txt, host_txt, style=row_style)
            else:
                # Standard/wide: delta and jitter columns already show trend info
                tbl.add_row(str(hop_num), min_txt, avg_txt, last_txt, delta_txt, jitter_txt, loss_txt, host_txt, style=row_style)

            if not ok:
                worst_hop = h
                worst_lat = float("inf")
            elif lat is not None and lat > worst_lat:
                worst_lat = lat
                worst_hop = h

        items: list[Table | Text] = [tbl]

        if tier == "compact" and len(hops) > 8:
            items.append(Text.from_markup(f"  [{_TEXT_DIM}]+{len(hops) - 8} more...[/{_TEXT_DIM}]"))

        if worst_hop and worst_lat > HOP_LATENCY_GOOD:
            w_ip = worst_hop.get("ip", "?")
            w_num = worst_hop.get("hop", "?")
            if worst_lat == float("inf"):
                items.append(Text.from_markup(
                    f"  [{_RED}]{t('hop_worst')}: #{w_num} {w_ip} — {t('hop_down')}[/{_RED}]"
                ))
            else:
                items.append(Text.from_markup(
                    f"  [{_YELLOW}]{t('hop_worst')}: #{w_num} {w_ip} — {worst_lat:.0f} {t('ms')}[/{_YELLOW}]"
                ))

        if discovering:
            items.append(Text.from_markup(f"  [{_TEXT_DIM} italic]{t('hop_discovering')}[/{_TEXT_DIM} italic]"))

        return Panel(
            Group(*items),
            title=title, title_align="left", border_style=border,
            box=box.ROUNDED, width=width, style=panel_style,
        )

    def render_monitoring_panel(self, width: int, tier: LayoutTier) -> Panel:
        snap = self.monitor.get_stats_snapshot()
        inner_w = max(20, width - 4)

        # ── DNS ──
        dns_results = snap.get("dns_results", {})
        if dns_results:
            type_parts = []
            total_time = 0
            time_count = 0
            for rt, res in sorted(dns_results.items()):
                status = res.get("status", t("failed"))
                ms = res.get("response_time_ms")
                if ms:
                    total_time += ms
                    time_count += 1
                if status == t("ok"):
                    type_parts.append(f"[{_GREEN}]{rt}✓[/{_GREEN}]")
                elif status == t("slow"):
                    type_parts.append(f"[{_YELLOW}]{rt}~[/{_YELLOW}]")
                else:
                    type_parts.append(f"[{_RED}]{rt}✗[/{_RED}]")
            avg_time = total_time / time_count if time_count > 0 else 0
            dns_types_txt = f"  {' '.join(type_parts)}  [{_TEXT_DIM}]{avg_time:.0f}ms[/{_TEXT_DIM}]"
        elif snap["dns_resolve_time"] is None:
            dns_types_txt = f"  [{_RED}]{t('error')}[/{_RED}]" if SHOW_VISUAL_ALERTS else f"  [{_TEXT_DIM}]—[/{_TEXT_DIM}]"
        else:
            ms = snap["dns_resolve_time"]
            if snap["dns_status"] == t("ok"):
                dns_types_txt = f"  [{_GREEN}]OK[/{_GREEN}] [{_TEXT_DIM}]({ms:.0f}ms)[/{_TEXT_DIM}]"
            elif snap["dns_status"] == t("slow"):
                dns_types_txt = f"  [{_YELLOW}]{t('slow')}[/{_YELLOW}] [{_TEXT_DIM}]({ms:.0f}ms)[/{_TEXT_DIM}]"
            else:
                dns_types_txt = f"  [{_RED}]{t('error')}[/{_RED}]"

        # ── Benchmark ──
        dns_benchmark = snap.get("dns_benchmark", {})
        bench_txt = None
        if dns_benchmark and tier != "compact":
            parts = []
            total_queries = 0
            all_avg: list[float] = []
            all_std: list[float] = []
            for tt in ["cached", "uncached", "dotcom"]:
                r = dns_benchmark.get(tt, {})
                lbl = tt[0].upper()
                if not r.get("success"):
                    parts.append(f"[{_RED}]{lbl}:✗[/{_RED}]")
                else:
                    ms_val = r.get("response_time_ms")
                    val = f"{ms_val:.0f}" if ms_val else "—"
                    status = r.get("status", "failed")
                    color = _GREEN if status == t("ok") else (_YELLOW if status == t("slow") else _RED)
                    parts.append(f"[{color}]{lbl}:{val}[/{color}]")
                q = r.get("queries", 0)
                total_queries = max(total_queries, q)
                if r.get("avg_ms") is not None:
                    all_avg.append(r["avg_ms"])
                if r.get("std_dev") is not None:
                    all_std.append(r["std_dev"])

            bench_line = "  " + "  ".join(parts)
            if total_queries > 1 and all_avg:
                avg_all = sum(all_avg) / len(all_avg)
                stats_suffix = f"[{_TEXT_DIM}]│ {total_queries}q avg:{avg_all:.0f}"
                if all_std:
                    avg_std_val = sum(all_std) / len(all_std)
                    stats_suffix += f" σ:{avg_std_val:.0f}"
                stats_suffix += f"ms[/{_TEXT_DIM}]"
                bench_txt = f"{bench_line}  {stats_suffix}"
            else:
                bench_txt = bench_line

        # ── Network metrics ──
        ttl = snap["last_ttl"]
        ttl_hops = snap["ttl_hops"]
        if ttl:
            ttl_txt = f"[{_WHITE}]{ttl}[/{_WHITE}]"
            if ttl_hops:
                ttl_txt += f" [{_TEXT_DIM}]({ttl_hops} {t('hop_unit')})[/{_TEXT_DIM}]"
        else:
            ttl_txt = f"[{_TEXT_DIM}]—[/{_TEXT_DIM}]"

        local_mtu = snap["local_mtu"]
        path_mtu = snap["path_mtu"]
        local_txt = f"{local_mtu}" if local_mtu else "—"
        path_txt = f"{path_mtu}" if path_mtu else "—"
        mtu_val_txt = f"[{_WHITE}]{local_txt}[/{_WHITE}]/[{_WHITE}]{path_txt}[/{_WHITE}]"

        mtu_status = snap.get("mtu_status", "...")
        if mtu_status == t("mtu_ok"):
            mtu_s_txt = f"[{_GREEN}]{mtu_status}[/{_GREEN}]"
        elif mtu_status == t("mtu_low"):
            mtu_s_txt = f"[{_YELLOW}]{mtu_status}[/{_YELLOW}]"
        elif mtu_status == t("mtu_fragmented"):
            mtu_s_txt = f"[{_RED}]{mtu_status}[/{_RED}]"
        else:
            mtu_s_txt = f"[{_TEXT_DIM}]{mtu_status}[/{_TEXT_DIM}]"

        # Traceroute
        if snap["traceroute_running"]:
            tr_txt = f"[{_YELLOW}]{t('traceroute_running')}[/{_YELLOW}]"
        elif snap["last_traceroute_time"]:
            tr_txt = f"[{_TEXT_DIM}]{self._fmt_since(snap['last_traceroute_time'])}[/{_TEXT_DIM}]"
        else:
            tr_txt = f"[{_TEXT_DIM}]{t('never')}[/{_TEXT_DIM}]"

        # Alerts count
        if not SHOW_VISUAL_ALERTS:
            alert_txt = f"[{_TEXT_DIM}]{t('alerts_off')}[/{_TEXT_DIM}]"
        else:
            alert_cnt = len(snap["active_alerts"])
            alert_txt = f"[{_GREEN}]{t('none_label')}[/{_GREEN}]" if alert_cnt == 0 else f"[{_YELLOW}]{alert_cnt}[/{_YELLOW}]"

        net_tbl = self._dual_kv_table(width)
        net_tbl.add_row(f"{t('ttl')}:", ttl_txt, f"{t('mtu')}:", mtu_val_txt)
        net_tbl.add_row(f"{t('mtu_status_label')}:", mtu_s_txt, f"{t('alerts_label')}:", alert_txt)
        net_tbl.add_row(f"{t('traceroute')}:", tr_txt, "", "")

        # MTU details
        mtu_issues = snap.get("mtu_consecutive_issues", 0)
        mtu_extra: list[Text] = []
        if mtu_issues and mtu_status != t("mtu_ok") and tier != "compact":
            mtu_last_change = snap.get("mtu_last_status_change")
            since_txt = self._fmt_since(mtu_last_change) if mtu_last_change else "..."
            mtu_extra.append(Text.from_markup(
                f"  [{_TEXT_DIM}]{t('mtu_issues_label')}: {mtu_issues} {t('checks_unit')} / {since_txt}[/{_TEXT_DIM}]"
            ))

        # ── Alerts ──
        self.monitor.cleanup_alerts()
        alert_lines: list[str] = []
        if SHOW_VISUAL_ALERTS and snap["active_alerts"]:
            for alert in snap["active_alerts"]:
                icon = {"warning": _DOT_WARN, "critical": _DOT_ERR, "info": _DOT_OK, "success": "✔"}.get(alert["type"], _DOT_OK)
                color = {"warning": _YELLOW, "critical": _RED, "info": _WHITE, "success": _GREEN}.get(alert["type"], _WHITE)
                alert_lines.append(f"  [{color}]{icon} {alert['message']}[/{color}]")
        else:
            alert_lines.append(f"  [{_TEXT_DIM}]{t('no_alerts')}[/{_TEXT_DIM}]")

        max_alerts = 2 if tier == "compact" else ALERT_PANEL_LINES
        while len(alert_lines) < max_alerts:
            alert_lines.append(" ")
        alert_lines = alert_lines[:max_alerts]

        # ── Assemble ──
        items: list[Text | Table] = [
            self._section_header(t("dns"), inner_w),
            Text.from_markup(dns_types_txt),
        ]
        if bench_txt:
            items.append(Text.from_markup(bench_txt))
        items.append(self._section_header(t("network"), inner_w))
        items.append(net_tbl)
        for line in mtu_extra:
            items.append(line)
        items.append(self._section_header(t("notifications"), inner_w))
        for line in alert_lines:
            items.append(Text.from_markup(line))

        return Panel(
            Group(*items),
            title=f"[bold {_ACCENT}]{t('mon')}[/bold {_ACCENT}]",
            title_align="left",
            border_style=_ACCENT_DIM,
            box=box.ROUNDED,
            width=width,
            style=f"on {_BG_PANEL}",
        )

    def render_footer(self, width: int, tier: LayoutTier) -> Panel:
        log_path = LOG_FILE.replace(os.path.expanduser("~"), "~")
        txt = f"[{_TEXT_DIM}]{t('footer').format(log_file=log_path)}[/{_TEXT_DIM}]"
        snap = self.monitor.get_stats_snapshot()
        latest_version = snap.get("latest_version")
        if latest_version:
            txt += f"    [{_YELLOW}]{_DOT_WARN} {t('update_available').format(current=VERSION, latest=latest_version)}[/{_YELLOW}]"
        return Panel(txt, border_style=_ACCENT_DIM, box=box.SIMPLE, width=width, style=f"on {_BG}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Compact summary (single-panel condensed view)
    # ═══════════════════════════════════════════════════════════════════════════

    def render_compact_summary(self, width: int) -> Panel:
        """Combined summary for compact mode: latency + stats + analysis in one dense panel."""
        snap = self.monitor.get_stats_snapshot()
        success_rate = (snap["success"] / snap["total"] * 100) if snap["total"] else 0.0
        recent = snap["recent_results"]
        loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0
        jit = snap.get("jitter", 0.0)

        problem_type = snap.get("current_problem_type", t("problem_none"))
        if problem_type == t("problem_none"):
            pt_txt = f"[{_GREEN}]{problem_type}[/{_GREEN}]"
        elif problem_type in [t("problem_isp"), t("problem_dns")]:
            pt_txt = f"[{_RED}]{problem_type}[/{_RED}]"
        else:
            pt_txt = f"[{_YELLOW}]{problem_type}[/{_YELLOW}]"

        tbl = self._dual_kv_table(width)
        sr_color = _GREEN if success_rate > 95 else (_YELLOW if success_rate > 80 else _RED)
        l30_color = _GREEN if loss30 < 1 else (_YELLOW if loss30 < 5 else _RED)

        tbl.add_row(
            f"{t('success_rate')}:", f"[{sr_color}]{success_rate:.1f}%[/{sr_color}]",
            f"{t('loss_30m')}:", f"[{l30_color}]{loss30:.1f}%[/{l30_color}]",
        )
        tbl.add_row(
            f"{t('jitter')}:", f"[{_WHITE}]{jit:.1f} {t('ms')}[/{_WHITE}]",
            f"{t('problem_type')}:", pt_txt,
        )

        return Panel(
            tbl,
            title=f"[bold {_ACCENT}]{t('analysis')}[/bold {_ACCENT}]",
            title_align="left",
            border_style=_ACCENT_DIM,
            box=box.ROUNDED,
            width=width,
            style=f"on {_BG_PANEL}",
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Layout generation
    # ═══════════════════════════════════════════════════════════════════════════

    def generate_layout(self) -> Layout:
        w = max(60, self.console.size.width)
        tier = self._get_tier()
        inner = w - 2

        layout = Layout(name="root")

        if tier == "compact":
            return self._layout_compact(layout, w, inner)
        elif tier == "wide":
            return self._layout_wide(layout, w, inner)
        else:
            return self._layout_standard(layout, w, inner)

    def _layout_compact(self, layout: Layout, w: int, inner: int) -> Layout:
        """Single-column layout for narrow terminals."""
        layout.split_column(
            Layout(self.render_header(w, "compact"), size=3, name="header"),
            Layout(self.render_status_bar(w, "compact"), size=3, name="status"),
            Layout(self.render_latency_panel(w, "compact"), name="latency", ratio=1),
            Layout(self.render_compact_summary(w), name="summary", size=6),
            Layout(self.render_monitoring_panel(w, "compact"), name="mon", ratio=1),
            Layout(self.render_footer(w, "compact"), size=3, name="footer"),
        )
        return layout

    def _layout_standard(self, layout: Layout, w: int, inner: int) -> Layout:
        """Two-column layout for normal terminals."""
        left_w = (inner // 2) - 1
        right_w = inner - left_w - 1

        layout.split_column(
            Layout(self.render_header(w, "standard"), size=3, name="header"),
            Layout(self.render_status_bar(w, "standard"), size=3, name="status"),
            Layout(name="body", ratio=1),
            Layout(self.render_footer(w, "standard"), size=3, name="footer"),
        )

        body = Layout(name="body_inner")
        body.split_column(
            Layout(name="upper", ratio=1),
            Layout(name="lower", ratio=1),
            Layout(self.render_hop_panel(w, "standard"), name="hops", ratio=1),
        )
        body["upper"].split_row(
            Layout(self.render_latency_panel(left_w, "standard"), name="latency"),
            Layout(name="stats_trends", ratio=1),
        )
        body["upper"]["stats_trends"].split_column(
            Layout(self.render_stats_panel(right_w, "standard"), name="stats"),
            Layout(self.render_trend_panel(right_w, "standard"), name="trends"),
        )
        body["lower"].split_row(
            Layout(self.render_analysis_panel(left_w, "standard"), name="analysis"),
            Layout(self.render_monitoring_panel(right_w, "standard"), name="mon"),
        )
        layout["body"].update(body)
        return layout

    def _layout_wide(self, layout: Layout, w: int, inner: int) -> Layout:
        """Three-column layout for wide terminals."""
        col_w = (inner - 2) // 3

        layout.split_column(
            Layout(self.render_header(w, "wide"), size=3, name="header"),
            Layout(self.render_status_bar(w, "wide"), size=3, name="status"),
            Layout(name="body", ratio=1),
            Layout(self.render_hop_panel(w, "wide"), name="hops", ratio=1),
            Layout(self.render_footer(w, "wide"), size=3, name="footer"),
        )

        body = Layout(name="body_inner")
        body.split_row(
            Layout(name="col1", ratio=1),
            Layout(name="col2", ratio=1),
            Layout(name="col3", ratio=1),
        )
        body["col1"].update(self.render_latency_panel(col_w, "wide"))
        body["col2"].split_column(
            Layout(self.render_stats_panel(col_w, "wide"), name="stats", ratio=1),
            Layout(self.render_trend_panel(col_w, "wide"), name="trends", ratio=1),
        )
        body["col3"].split_column(
            Layout(self.render_analysis_panel(col_w, "wide"), name="analysis", ratio=1),
            Layout(self.render_monitoring_panel(col_w, "wide"), name="mon", ratio=1),
        )
        layout["body"].update(body)
        return layout


__all__ = ["MonitorUI"]
