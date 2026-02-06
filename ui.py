from __future__ import annotations

import statistics
from datetime import datetime
from typing import TYPE_CHECKING
import time

from rich import box
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from .monitor import Monitor

try:
    from config import (
        ALERT_PANEL_LINES,
        SHOW_VISUAL_ALERTS,
        TARGET_IP,
        t,
    )
    from monitor import Monitor  # type: ignore
except ImportError:
    from .config import (
        ALERT_PANEL_LINES,
        SHOW_VISUAL_ALERTS,
        TARGET_IP,
        t,
    )
    from .monitor import Monitor  # type: ignore


# ── Unicode characters for visual elements ──
_SPARK_CHARS = "▁▂▃▄▅▆▇█"
_BAR_FULL = "█"
_BAR_EMPTY = "░"


class MonitorUI:
    def __init__(self, console: Console, monitor: Monitor) -> None:
        self.console = console
        self.monitor = monitor
        self._cached_jitter: float = 0.0
        self._last_jitter_update: float = 0.0
        self._jitter_cache_interval: float = 5.0

    # ══════════════════ helpers ══════════════════

    @staticmethod
    def _fmt_uptime(start_time: datetime | None) -> str:
        if start_time is None:
            return t("na")
        total = int((datetime.now() - start_time).total_seconds())
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
        sec = int((datetime.now() - ts).total_seconds())
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
    def _progress_bar(pct: float, width: int = 20, color: str = "green") -> str:
        """Unicode progress bar: ████████░░░░"""
        pct = max(0.0, min(pct, 100.0))
        filled = int(round(pct / 100.0 * width))
        empty = width - filled
        return f"[{color}]{_BAR_FULL * filled}[/{color}][dim]{_BAR_EMPTY * empty}[/dim]"

    @staticmethod
    def _sparkline(values: list[float], width: int = 40) -> str:
        """Generate sparkline from values using Unicode block chars."""
        if not values:
            return f"[dim]{t('no_data')}[/dim]"
        # Take last `width` values
        data = values[-width:]
        if len(data) < 2:
            return f"[dim]{t('waiting')}[/dim]"
        mn, mx = min(data), max(data)
        rng = mx - mn if mx != mn else 1.0
        chars = []
        for v in data:
            idx = int((v - mn) / rng * (len(_SPARK_CHARS) - 1))
            idx = max(0, min(idx, len(_SPARK_CHARS) - 1))
            # Color based on relative value
            rel = (v - mn) / rng
            if rel < 0.4:
                color = "green"
            elif rel < 0.7:
                color = "yellow"
            else:
                color = "red"
            chars.append(f"[{color}]{_SPARK_CHARS[idx]}[/{color}]")
        return "".join(chars)

    @staticmethod
    def _kv_table(width: int, key_width: int = 16) -> Table:
        tbl = Table(show_header=False, box=None, padding=(0, 1), width=width)
        tbl.add_column("k", style="white dim", width=key_width, no_wrap=True)
        tbl.add_column("v", width=max(10, width - key_width - 3), no_wrap=True)
        return tbl

    @staticmethod
    def _dual_kv_table(width: int) -> Table:
        """Two-column key-value layout for compact display."""
        tbl = Table(show_header=False, box=None, padding=(0, 1), width=width)
        col_w = max(8, (width - 6) // 4)
        tbl.add_column("k1", style="white dim", width=col_w, no_wrap=True)
        tbl.add_column("v1", width=col_w, no_wrap=True)
        tbl.add_column("k2", style="white dim", width=col_w, no_wrap=True)
        tbl.add_column("v2", width=col_w, no_wrap=True)
        return tbl

    def _get_connection_state(self, snap: dict) -> tuple[str, str, str]:
        """Determine overall connection state -> (label, color, icon)."""
        if snap["threshold_states"]["connection_lost"]:
            return t("status_disconnected"), "red", "✖"
        recent = snap["recent_results"]
        if recent:
            loss30 = recent.count(False) / len(recent) * 100
            if loss30 > 5:
                return t("status_degraded"), "yellow", "▲"
        if snap["last_status"] == t("status_timeout"):
            return t("status_timeout_bar"), "red", "✖"
        if snap["last_status"] == t("status_ok"):
            return t("status_connected"), "green", "●"
        return t("status_waiting"), "white", "○"

    # ══════════════════ sections ══════════════════

    def render_header(self, width: int) -> Panel:
        now = datetime.now().strftime("%H:%M:%S")
        txt = (
            f"[bold white]{t('title')}[/bold white]  [dim]→[/dim]  "
            f"[bold cyan]{TARGET_IP}[/bold cyan]    [dim]│[/dim]    [dim]{now}[/dim]"
        )
        return Panel(
            txt, border_style="cyan", box=box.HEAVY, width=width, style="on #1a1a2e"
        )

    def render_status_bar(self, width: int) -> Panel:
        """Hero status bar — instant connection overview."""
        snap = self.monitor.get_stats_snapshot()
        label, color, icon = self._get_connection_state(snap)

        # Current ping
        current = snap["last_latency_ms"]
        if current != t("na"):
            ping_txt = f"[bold]{current}[/bold] {t('ms')}"
        else:
            ping_txt = "[dim]—[/dim]"

        # Loss 30 min
        recent = snap["recent_results"]
        loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0
        l_color = "green" if loss30 < 1 else ("yellow" if loss30 < 5 else "red")
        loss_txt = f"[{l_color}]{loss30:.1f}%[/{l_color}]"

        # Uptime
        uptime_txt = self._fmt_uptime(snap["start_time"])

        # IP
        ip_val = snap["public_ip"]
        cc = f" [{snap['country_code']}]" if snap["country_code"] else ""

        parts = (
            f"   [bold {color}]{icon} {label}[/bold {color}]"
            f"     [dim]│[/dim]  Ping: {ping_txt}"
            f"     [dim]│[/dim]  Loss: {loss_txt}"
            f"     [dim]│[/dim]  Uptime: [white]{uptime_txt}[/white]"
            f"     [dim]│[/dim]  IP: [white]{ip_val}[/white][dim]{cc}[/dim]"
        )
        return Panel(
            parts,
            border_style=color,
            box=box.DOUBLE,
            width=width,
        )

    def render_latency_panel(self, width: int) -> Panel:
        """Top-left: latency stats + sparkline."""
        snap = self.monitor.get_stats_snapshot()
        latencies = snap["latencies"]
        avg = (snap["total_latency_sum"] / snap["success"]) if snap["success"] > 0 else 0.0
        med = statistics.median(latencies) if latencies else 0.0
        jit = snap.get("jitter", 0.0)
        var = statistics.stdev(latencies) if len(latencies) > 1 else 0.0

        current = snap["last_latency_ms"]
        current_txt = f"[bold white]{current}[/bold white] {t('ms')}" if current != t("na") else "[dim]—[/dim]"
        best = f"[green]{snap['min_latency']:.1f}[/green]" if snap["min_latency"] != float("inf") else "[dim]—[/dim]"
        peak = f"[red]{snap['max_latency']:.1f}[/red]" if snap["max_latency"] > 0 else "[dim]—[/dim]"
        med_txt = f"[white]{med:.1f}[/white]" if latencies else "[dim]—[/dim]"
        avg_txt = f"[yellow]{avg:.1f}[/yellow]" if snap["success"] > 0 else "[dim]—[/dim]"
        if snap["threshold_states"]["high_avg_latency"] and snap["success"]:
            avg_txt = f"[bold red]{avg:.1f} (!)[/bold red]"

        jit_txt = f"[white]{jit:.1f}[/white]" if jit > 0 else "[dim]—[/dim]"
        if snap["threshold_states"]["high_jitter"]:
            jit_txt = f"[bold red]{jit:.1f} (!)[/bold red]"
        var_txt = f"[white]{var:.1f}[/white]" if var > 0 else "[dim]—[/dim]"

        # Dual-column key-value
        tbl = self._dual_kv_table(width)
        tbl.add_row(f"{t('current')}:", current_txt, f"{t('best')}:", f"{best} {t('ms')}")
        tbl.add_row(f"{t('average')}:", f"{avg_txt} {t('ms')}", f"{t('peak')}:", f"{peak} {t('ms')}")
        tbl.add_row(f"{t('median')}:", f"{med_txt} {t('ms')}", f"{t('jitter')}:", f"{jit_txt} {t('ms')}")
        tbl.add_row(f"{t('spread')}:", f"{var_txt} {t('ms')}", "", "")

        # Sparkline
        spark_width = max(20, width - 6)
        spark = self._sparkline(list(latencies), width=spark_width)
        mn_txt = f"{min(latencies):.0f}" if latencies else "—"
        mx_txt = f"{max(latencies):.0f}" if latencies else "—"
        avg_s = f"{avg:.0f}" if snap["success"] > 0 else "—"

        grp = Group(
            tbl,
            Text(""),
            Text.from_markup(f"  [dim]{t('latency_chart')}[/dim]"),
            Text.from_markup(f"  {spark}"),
            Text.from_markup(f"  [dim]{mn_txt}{t('ms')}{'':>10}avg {avg_s}{t('ms')}{'':>10}{mx_txt}{t('ms')}[/dim]"),
        )
        return Panel(
            grp,
            title=f"[bold]{t('lat')}[/bold]",
            title_align="left",
            border_style="cyan",
            box=box.ROUNDED,
            width=width,
        )

    def render_stats_panel(self, width: int) -> Panel:
        """Top-right: packet statistics with progress bars."""
        snap = self.monitor.get_stats_snapshot()
        success_rate = (snap["success"] / snap["total"] * 100) if snap["total"] else 0.0
        loss_total = (snap["failure"] / snap["total"] * 100) if snap["total"] else 0.0
        recent = snap["recent_results"]
        loss30 = recent.count(False) / len(recent) * 100 if recent else 0.0

        # Counters in dual-column
        tbl = self._dual_kv_table(width)
        tbl.add_row(
            f"{t('sent')}:", f"[white]{snap['total']}[/white]",
            f"{t('ok_count')}:", f"[green]{snap['success']}[/green]",
        )
        tbl.add_row(
            f"{t('lost')}:", f"[red]{snap['failure']}[/red]",
            f"{t('losses')}:", f"[dim]{loss_total:.1f}%[/dim]",
        )

        # Progress bars
        bar_w = max(10, width - 24)
        sr_color = "green" if success_rate > 95 else ("yellow" if success_rate > 80 else "red")
        sr_bar = self._progress_bar(success_rate, width=bar_w, color=sr_color)

        l30_color = "green" if loss30 < 1 else ("yellow" if loss30 < 5 else "red")
        l30_bar = self._progress_bar(loss30, width=bar_w, color=l30_color)
        loss30_txt = f"[{l30_color}]{loss30:.1f}%[/{l30_color}]"
        if snap["threshold_states"]["high_packet_loss"]:
            loss30_txt += " [red](!)[/red]"

        # Consecutive losses
        cons = snap["consecutive_losses"]
        if snap["threshold_states"]["connection_lost"]:
            cons_txt = f"[bold red]{cons} (!!!)[/bold red]"
        elif cons > 0:
            cons_txt = f"[yellow]{cons}[/yellow]"
        else:
            cons_txt = f"[green]{cons}[/green]"
        max_cons_txt = f"[red]{snap['max_consecutive_losses']}[/red]"

        grp = Group(
            tbl,
            Text(""),
            Text.from_markup(f"  [dim]{t('success_rate')}:[/dim]     [green]{success_rate:.1f}%[/green]"),
            Text.from_markup(f"  {sr_bar}"),
            Text(""),
            Text.from_markup(f"  [dim]{t('loss_30m')}:[/dim] {loss30_txt}"),
            Text.from_markup(f"  {l30_bar}"),
            Text(""),
            Text.from_markup(f"  [dim]{t('consecutive')}:[/dim] {cons_txt}    [dim]{t('max_label')}:[/dim] {max_cons_txt}"),
        )
        return Panel(
            grp,
            title=f"[bold]{t('stats')}[/bold]",
            title_align="left",
            border_style="cyan",
            box=box.ROUNDED,
            width=width,
        )

    def render_analysis_panel(self, width: int) -> Panel:
        """Bottom-left: problem analysis + route analysis combined."""
        snap = self.monitor.get_stats_snapshot()

        # ── Problem analysis ──
        problem_type = snap.get("current_problem_type", t("problem_none"))
        if problem_type == t("problem_none"):
            pt_txt = f"[green]{problem_type}[/green]"
        elif problem_type in [t("problem_isp"), t("problem_dns")]:
            pt_txt = f"[red]{problem_type}[/red]"
        elif problem_type in [t("problem_local"), t("problem_mtu")]:
            pt_txt = f"[yellow]{problem_type}[/yellow]"
        else:
            pt_txt = f"[white]{problem_type}[/white]"

        prediction = snap.get("problem_prediction", t("prediction_stable"))
        pred_txt = (
            f"[green]{prediction}[/green]"
            if prediction == t("prediction_stable")
            else f"[yellow]{prediction}[/yellow]"
        )
        pattern = snap.get("problem_pattern", "...")
        pat_txt = f"[white]{pattern}[/white]" if pattern != "..." else "[dim]...[/dim]"

        prob_tbl = self._kv_table(width, key_width=14)
        prob_tbl.add_row(f"{t('problem_type')}:", pt_txt)
        prob_tbl.add_row(f"{t('prediction')}:", pred_txt)
        prob_tbl.add_row(f"{t('pattern')}:", pat_txt)

        # ── Route analysis ──
        hops = snap.get("route_hops", [])
        hop_count = len(hops)
        hop_count_txt = f"[white]{hop_count}[/white]" if hop_count > 0 else "[dim]—[/dim]"

        problematic_hop = snap.get("route_problematic_hop")
        ph_txt = f"[red]{problematic_hop}[/red]" if problematic_hop else f"[green]{t('none_label')}[/green]"

        route_changed = snap.get("route_changed", False)
        rs_txt = (
            f"[yellow]{t('route_changed')}[/yellow]"
            if route_changed
            else f"[green]{t('route_stable')}[/green]"
        )

        avg_route_latency = None
        if hops:
            lat_list = [h.get("avg_latency") for h in hops if h.get("avg_latency")]
            if lat_list:
                avg_route_latency = statistics.mean(lat_list)
        avg_rl_txt = f"[white]{avg_route_latency:.1f}[/white] {t('ms')}" if avg_route_latency else "[dim]—[/dim]"

        route_diff = snap.get("route_last_diff_count", 0)
        route_cons = snap.get("route_consecutive_changes", 0)
        route_last_change = snap.get("route_last_change_time")
        diff_txt = f"[dim]{route_diff} {t('hops_unit')}[/dim]" if route_diff else "[dim]—[/dim]"
        if route_cons:
            since_str = self._fmt_since(route_last_change) if route_last_change else "..."
            cons_txt = f"[dim]{route_cons} / {since_str}[/dim]"
        else:
            cons_txt = "[dim]—[/dim]"

        route_tbl = self._kv_table(width, key_width=14)
        route_tbl.add_row(f"{t('route_label')}:", rs_txt)
        route_tbl.add_row(f"{t('hops_count')}:", hop_count_txt)
        route_tbl.add_row(f"{t('problematic_hop_short')}:", ph_txt)
        route_tbl.add_row(f"{t('avg_latency_short')}:", avg_rl_txt)
        route_tbl.add_row(f"{t('changed_hops')}:", diff_txt)
        route_tbl.add_row(f"{t('changes')}:", cons_txt)

        # Last problem time
        if snap["last_problem_time"] is None:
            last_prob_txt = f"[green]{t('never')}[/green]"
        else:
            age = (datetime.now() - snap["last_problem_time"]).total_seconds()
            since_txt = self._fmt_since(snap["last_problem_time"])
            last_prob_txt = f"[red]{since_txt}[/red]" if age < 60 else f"[yellow]{since_txt}[/yellow]"

        prob_time_tbl = self._kv_table(width, key_width=14)
        prob_time_tbl.add_row(f"{t('last_problem')}:", last_prob_txt)

        grp = Group(
            Text.from_markup(f"  [bold dim]{t('problem_analysis')}[/bold dim]"),
            prob_tbl,
            prob_time_tbl,
            Text(""),
            Text.from_markup(f"  [bold dim]{t('route_analysis')}[/bold dim]"),
            route_tbl,
        )
        return Panel(
            grp,
            title=f"[bold]{t('analysis')}[/bold]",
            title_align="left",
            border_style="cyan",
            box=box.ROUNDED,
            width=width,
        )

    def render_monitoring_panel(self, width: int) -> Panel:
        """Bottom-right: DNS, MTU, TTL, Traceroute + Alerts."""
        snap = self.monitor.get_stats_snapshot()

        # ── DNS ──
        if snap["dns_resolve_time"] is None:
            dns_txt = f"[red]{t('error')}[/red]" if SHOW_VISUAL_ALERTS else "[dim]—[/dim]"
        else:
            ms = snap["dns_resolve_time"]
            if snap["dns_status"] == t("ok"):
                dns_txt = f"[green]OK[/green] [dim]({ms:.0f} {t('ms')})[/dim]"
            elif snap["dns_status"] == t("slow"):
                dns_txt = f"[yellow]{t('slow')}[/yellow] [dim]({ms:.0f} {t('ms')})[/dim]"
            else:
                dns_txt = f"[red]{t('error')}[/red]"

        # ── MTU ──
        local_mtu = snap["local_mtu"]
        path_mtu = snap["path_mtu"]
        local_txt = f"{local_mtu}" if local_mtu else "—"
        path_txt = f"{path_mtu}" if path_mtu else "—"
        mtu_val_txt = f"[white]{local_txt}[/white] / [white]{path_txt}[/white]"

        mtu_status = snap.get("mtu_status", "...")
        if mtu_status == t("mtu_ok"):
            mtu_s_txt = f"[green]{mtu_status}[/green]"
        elif mtu_status == t("mtu_low"):
            mtu_s_txt = f"[yellow]{mtu_status}[/yellow]"
        elif mtu_status == t("mtu_fragmented"):
            mtu_s_txt = f"[red]{mtu_status}[/red]"
        else:
            mtu_s_txt = f"[dim]{mtu_status}[/dim]"

        # ── TTL ──
        ttl = snap["last_ttl"]
        ttl_hops = snap["ttl_hops"]
        if ttl:
            ttl_txt = f"[white]{ttl}[/white]"
            if ttl_hops:
                ttl_txt += f" [dim]({ttl_hops} {t('hop_unit')})[/dim]"
        else:
            ttl_txt = "[dim]—[/dim]"

        # ── Traceroute ──
        if snap["traceroute_running"]:
            tr_txt = f"[yellow]{t('traceroute_running')}[/yellow]"
        elif snap["last_traceroute_time"]:
            tr_txt = f"[dim]{self._fmt_since(snap['last_traceroute_time'])}[/dim]"
        else:
            tr_txt = f"[dim]{t('never')}[/dim]"

        # ── Alerts count ──
        if not SHOW_VISUAL_ALERTS:
            alert_txt = f"[dim]{t('alerts_off')}[/dim]"
        else:
            alert_cnt = len(snap["active_alerts"])
            alert_txt = f"[green]{t('none_label')}[/green]" if alert_cnt == 0 else f"[yellow]{alert_cnt}[/yellow]"

        # Compact dual-column table
        mon_tbl = self._dual_kv_table(width)
        mon_tbl.add_row("DNS:", dns_txt, f"{t('mtu')}:", mtu_val_txt)
        mon_tbl.add_row(f"{t('ttl')}:", ttl_txt, f"{t('mtu_status_label')}:", mtu_s_txt)
        mon_tbl.add_row("Traceroute:", tr_txt, f"{t('alerts_label')}:", alert_txt)

        # ── MTU details (if issues) ──
        mtu_issues = snap.get("mtu_consecutive_issues", 0)
        mtu_extra_lines: list[Text] = []
        if mtu_issues and mtu_status != t("mtu_ok"):
            mtu_last_change = snap.get("mtu_last_status_change")
            since_txt = self._fmt_since(mtu_last_change) if mtu_last_change else "..."
            mtu_extra_lines.append(
                Text.from_markup(f"  [dim]{t('mtu_issues_label')}: {mtu_issues} {t('checks_unit')} / {since_txt}[/dim]")
            )

        # ── Alerts section ──
        self.monitor.cleanup_alerts()
        alert_lines: list[str] = []
        if SHOW_VISUAL_ALERTS and snap["active_alerts"]:
            for alert in snap["active_alerts"]:
                icon = {
                    "warning": "▲",
                    "critical": "✖",
                    "info": "●",
                    "success": "✔",
                }.get(alert["type"], "●")
                color = {
                    "warning": "yellow",
                    "critical": "red",
                    "info": "white",
                    "success": "green",
                }.get(alert["type"], "white")
                alert_lines.append(f"  [{color}]{icon} {alert['message']}[/{color}]")
        else:
            alert_lines.append(f"  [dim]{t('no_alerts')}[/dim]")

        # Pad / trim to ALERT_PANEL_LINES
        while len(alert_lines) < ALERT_PANEL_LINES:
            alert_lines.append(" ")
        alert_lines = alert_lines[:ALERT_PANEL_LINES]

        items: list = [
            mon_tbl,
        ]
        for line in mtu_extra_lines:
            items.append(line)
        items.append(Text(""))
        items.append(Text.from_markup(f"  [bold dim]{t('notifications')}[/bold dim]"))
        for line in alert_lines:
            items.append(Text.from_markup(line))

        grp = Group(*items)
        return Panel(
            grp,
            title=f"[bold]{t('mon')}[/bold]",
            title_align="left",
            border_style="cyan",
            box=box.ROUNDED,
            width=width,
        )

    @staticmethod
    def render_footer(width: int) -> Panel:
        txt = f"[dim]{t('footer')}[/dim]"
        return Panel(txt, border_style="dim", box=box.SIMPLE, width=width)

    # ══════════════════ layout ══════════════════

    def generate_layout(self) -> Layout:
        w = max(100, self.console.size.width)
        inner = w - 2
        left_w = (inner // 2) - 1
        right_w = inner - left_w - 1

        layout = Layout(name="root")
        layout.split_column(
            Layout(self.render_header(w), size=3, name="header"),
            Layout(self.render_status_bar(w), size=3, name="status"),
            Layout(name="body", ratio=1),
            Layout(self.render_footer(w), size=3, name="footer"),
        )

        body = Layout(name="body_inner")
        body.split_row(
            Layout(name="col_left"),
            Layout(name="col_right"),
        )
        body["col_left"].split_column(
            Layout(self.render_latency_panel(left_w), name="latency", ratio=1),
            Layout(self.render_analysis_panel(left_w), name="analysis", ratio=1),
        )
        body["col_right"].split_column(
            Layout(self.render_stats_panel(right_w), name="stats", ratio=1),
            Layout(self.render_monitoring_panel(right_w), name="monitoring", ratio=1),
        )
        layout["body"].update(body)
        return layout


__all__ = ["MonitorUI"]
