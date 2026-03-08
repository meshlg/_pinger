"""Analysis and monitoring panel renderer."""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.theme import ACCENT, ACCENT_DIM, BG_PANEL, GREEN, HeightTier, LayoutTier, RED, TEXT_DIM, WHITE, YELLOW
from ui.helpers import dns_mini_bar, dual_kv_table, ensure_utc, fmt_since, mini_gauge, section_header, truncate

try:
    from config import SHOW_VISUAL_ALERTS, t
except ImportError:
    from ...config import SHOW_VISUAL_ALERTS, t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


DEF_DASH = f"[{TEXT_DIM}]-[/{TEXT_DIM}]"


def _problem_text(snap: StatsSnapshot, connection_lost: bool) -> tuple[str, str]:
    problem_type = snap.get("current_problem_type", t("problem_none"))
    if connection_lost:
        problem_type = t("problem_isp")

    if problem_type == t("problem_none"):
        problem_markup = f"[{GREEN}]{problem_type}[/{GREEN}]"
    elif problem_type in (t("problem_isp"), t("problem_dns")):
        problem_markup = f"[{RED}]{problem_type}[/{RED}]"
    elif problem_type in (t("problem_local"), t("problem_mtu")):
        problem_markup = f"[{YELLOW}]{problem_type}[/{YELLOW}]"
    else:
        problem_markup = f"[{WHITE}]{problem_type}[/{WHITE}]"

    prediction = snap.get("problem_prediction", t("prediction_stable"))
    if connection_lost:
        prediction = t("prediction_risk")
    if prediction == t("prediction_stable"):
        prediction_markup = f"[{GREEN}]{prediction}[/{GREEN}]"
    else:
        prediction_markup = f"[{YELLOW}]{prediction}[/{YELLOW}]"

    return problem_markup, prediction_markup


def _last_problem_markup(last_problem_time) -> str:
    if last_problem_time is None:
        return f"[{GREEN}]{t('never')}[/{GREEN}]"
    utc_ts = ensure_utc(last_problem_time)
    if utc_ts is None:
        return f"[{GREEN}]{t('never')}[/{GREEN}]"
    age = (datetime.now(timezone.utc) - utc_ts).total_seconds()
    since_txt = fmt_since(last_problem_time)
    if age < 60:
        return f"[{RED}]{since_txt}[/{RED}]"
    return f"[{YELLOW}]{since_txt}[/{YELLOW}]"


def render_analysis_panel(snap: StatsSnapshot, width: int, tier: LayoutTier, h_tier: HeightTier) -> Panel:
    """Render a cleaner analysis and diagnostics panel."""
    connection_lost = bool(snap.get("threshold_states", {}).get("connection_lost", False))
    inner_w = max(20, width - 4)
    items: list[Table | Text] = []

    problem_markup, prediction_markup = _problem_text(snap, connection_lost)
    last_problem_markup = _last_problem_markup(snap.get("last_problem_time"))
    pattern = snap.get("problem_pattern", "...")
    pattern_markup = f"[{WHITE}]{pattern}[/{WHITE}]" if pattern != "..." else DEF_DASH

    items.append(section_header(t("problem_analysis"), inner_w))
    summary = dual_kv_table(width)
    summary.add_row(f"{t('problem_type')}:", problem_markup, f"{t('prediction')}:", prediction_markup)
    summary.add_row(f"{t('last_problem')}:", last_problem_markup, f"{t('pattern')}:", pattern_markup)
    items.append(summary)

    route_hops = snap.get("route_hops", []) if not connection_lost else []
    hop_count = len(route_hops)
    route_changed = bool(snap.get("route_changed", False)) if not connection_lost else False
    route_state = f"[{YELLOW}]{t('route_changed')}[/{YELLOW}]" if route_changed else f"[{GREEN}]{t('route_stable')}[/{GREEN}]"
    if connection_lost:
        route_state = f"[{RED}]{t('status_disconnected')}[/{RED}]"
    problematic_hop = snap.get("route_problematic_hop") if not connection_lost else None
    problematic_markup = f"[{RED}]{problematic_hop}[/{RED}]" if problematic_hop else f"[{GREEN}]{t('none_label')}[/{GREEN}]"
    avg_route_latency = None
    if route_hops:
        lat_values = [hop["avg_latency"] for hop in route_hops if hop.get("avg_latency") is not None]
        if lat_values:
            avg_route_latency = statistics.mean(lat_values)

    items.append(Text(""))
    items.append(section_header(t("route_analysis"), inner_w))
    route_tbl = dual_kv_table(width)
    route_tbl.add_row(f"{t('route_label')}:", route_state, f"{t('hops_count')}:", f"[{WHITE}]{hop_count}[/{WHITE}]" if hop_count else DEF_DASH)
    route_tbl.add_row(f"{t('problematic_hop_short')}:", problematic_markup, f"{t('avg_latency_short')}:", f"[{WHITE}]{avg_route_latency:.1f}[/{WHITE}] [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]" if avg_route_latency else DEF_DASH)
    if h_tier in ("standard", "full"):
        route_diff = snap.get("route_last_diff_count", 0) if not connection_lost else 0
        route_cons = snap.get("route_consecutive_changes", 0) if not connection_lost else 0
        route_last_change = snap.get("route_last_change_time") if not connection_lost else None
        route_tbl.add_row(
            f"{t('changed_hops')}:",
            f"[{TEXT_DIM}]{route_diff} {t('hops_unit')}[/{TEXT_DIM}]" if route_diff else DEF_DASH,
            f"{t('changes')}:",
            f"[{TEXT_DIM}]{route_cons} / {fmt_since(route_last_change)}[/{TEXT_DIM}]" if route_cons else DEF_DASH,
        )
    items.append(route_tbl)

    dns_health = snap.get("dns_health", {})
    dns_results = snap.get("dns_results", {})
    dns_benchmark = snap.get("dns_benchmark", {})

    items.append(Text(""))
    items.append(section_header(t("dns"), inner_w))
    if dns_health:
        score = float(dns_health.get("score", 0.0))
        reliability = float(dns_health.get("reliability", 0.0))
        jitter = dns_health.get("jitter")
        status = dns_health.get("status", "critical")
        if status in ("excellent", "good"):
            score_color = GREEN
        elif status == "fair":
            score_color = YELLOW
        else:
            score_color = RED

        items.append(Text.from_markup(
            f"  [{TEXT_DIM}]{t('dns_score')}[/{TEXT_DIM}] {mini_gauge(score, max_val=100.0, width=max(6, width - 34), color=score_color)}"
        ))
        if jitter is not None:
            dns_line = (
                f"  [{TEXT_DIM}]{t('dns_reliability_short')}[/{TEXT_DIM}] [{WHITE}]{reliability:.0f}%[/{WHITE}]  "
                f"[{TEXT_DIM}]{t('dns_jitter_short')}[/{TEXT_DIM}] [{WHITE}]{jitter:.1f}[/{WHITE}] [{TEXT_DIM}]{t('ms')}[/{TEXT_DIM}]"
            )
        else:
            dns_line = f"  [{TEXT_DIM}]{t('dns_reliability_short')}[/{TEXT_DIM}] [{WHITE}]{reliability:.0f}%[/{WHITE}]"
        items.append(Text.from_markup(dns_line))
    elif snap.get("dns_resolve_time") is None:
        fallback = f"[{RED}]{t('error')}[/{RED}]" if SHOW_VISUAL_ALERTS else f"[{TEXT_DIM}]-[/{TEXT_DIM}]"
        items.append(Text.from_markup(f"  {fallback}"))
    else:
        dns_time = snap.get("dns_resolve_time")
        dns_status = snap.get("dns_status")
        if dns_status == t("ok"):
            dns_markup = f"[{GREEN}]{t('ok_label')}[/{GREEN}]"
        elif dns_status == t("slow"):
            dns_markup = f"[{YELLOW}]{t('slow')}[/{YELLOW}]"
        else:
            dns_markup = f"[{RED}]{t('error')}[/{RED}]"
        items.append(Text.from_markup(f"  {dns_markup} [{TEXT_DIM}]({dns_time:.0f}{t('ms')})[/{TEXT_DIM}]"))

    if dns_results and h_tier in ("standard", "full"):
        dns_tbl = Table(show_header=True, header_style=f"bold {WHITE}", box=None, padding=(0, 1), width=inner_w)
        dns_tbl.add_column(t("ui_type"), width=6, no_wrap=True)
        dns_tbl.add_column(t("ui_ok_short"), width=4, justify="center", no_wrap=True)
        dns_tbl.add_column(t("avg_short"), width=6, justify="right", no_wrap=True)
        dns_tbl.add_column(t("ui_bar"), width=8, justify="left", no_wrap=True)
        dns_tbl.add_column(t("ttl"), width=6, justify="right", no_wrap=True)
        dns_tbl.add_column(t("ui_value"), ratio=1, overflow="ellipsis")

        for record_type in ("A", "AAAA", "NS", "MX", "CNAME", "TXT"):
            result = dns_results.get(record_type)
            if not result:
                continue
            success = bool(result.get("success"))
            response_ms = result.get("response_time_ms")
            ttl_value = result.get("ttl")
            record_count = result.get("record_count", 0)
            ok_markup = f"[{GREEN}]{t('ui_yes')}[/{GREEN}]" if success else f"[{RED}]{t('ui_no')}[/{RED}]"

            if response_ms is not None:
                ms_color = GREEN if response_ms < 50 else (YELLOW if response_ms < 150 else RED)
                avg_markup = f"[{ms_color}]{response_ms:.0f}[/{ms_color}]"
                bar_markup = dns_mini_bar(response_ms, max_ms=200.0, width=6)
            else:
                avg_markup = DEF_DASH
                bar_markup = f"[{TEXT_DIM}]------[/{TEXT_DIM}]"

            ttl_markup = f"[{TEXT_DIM}]{ttl_value}[/{TEXT_DIM}]" if ttl_value is not None else DEF_DASH
            if success and record_count > 0:
                value_markup = f"[{TEXT_DIM}]{record_count} {t('checks_unit')}[/{TEXT_DIM}]"
            elif not success:
                value_markup = f"[{RED}]{truncate(result.get('error', '') or t('failed'), 20)}[/{RED}]"
            else:
                value_markup = DEF_DASH

            dns_tbl.add_row(record_type, ok_markup, avg_markup, bar_markup, ttl_markup, value_markup)

        items.append(Text(""))
        items.append(dns_tbl)

    if dns_benchmark and h_tier == "full":
        benchmark_parts: list[str] = []
        for record_type in ("A", "AAAA", "NS", "MX", "TXT"):
            result = dns_benchmark.get(record_type, {})
            if not result:
                continue
            if not result.get("success"):
                benchmark_parts.append(f"[{RED}]{record_type}:fail[/{RED}]")
                continue
            response_ms = result.get("response_time_ms")
            avg_ms = result.get("avg_ms")
            status = result.get("status", t("failed"))
            color = GREEN if status == t("ok") else (YELLOW if status == t("slow") else RED)
            cell = f"[{color}]{record_type}:{response_ms:.0f}[/{color}]" if response_ms is not None else f"[{color}]{record_type}:ok[/{color}]"
            if avg_ms is not None:
                cell += f" [{TEXT_DIM}]/{avg_ms:.0f}[/{TEXT_DIM}]"
            benchmark_parts.append(cell)
        if benchmark_parts:
            items.append(Text(""))
            items.append(Text.from_markup(
                f"  [{ACCENT}]{t('avg_short')} {t('ui_benchmark')}[/{ACCENT}]  " + "  ".join(benchmark_parts)
            ))

    ttl_value = snap.get("ttl")
    ttl_hops = snap.get("ttl_hops")
    if ttl_value is None:
        ttl_markup = DEF_DASH
    else:
        ttl_markup = f"[{WHITE}]{ttl_value}[/{WHITE}]"
        if ttl_hops is not None:
            ttl_markup += f" [{TEXT_DIM}]({ttl_hops} {t('hop_unit')})[/{TEXT_DIM}]"

    mtu_value = snap.get("mtu")
    mtu_markup = f"[{WHITE}]{mtu_value}[/{WHITE}]" if mtu_value else DEF_DASH
    if connection_lost:
        mtu_status_markup = f"[{RED}]{t('status_disconnected')}[/{RED}]"
    else:
        mtu_status = snap.get("mtu_status", "...")
        if mtu_status == t("mtu_ok"):
            mtu_status_markup = f"[{GREEN}]{mtu_status}[/{GREEN}]"
        elif mtu_status == t("mtu_low"):
            mtu_status_markup = f"[{YELLOW}]{mtu_status}[/{YELLOW}]"
        elif mtu_status == t("mtu_fragmented"):
            mtu_status_markup = f"[{RED}]{mtu_status}[/{RED}]"
        else:
            mtu_status_markup = f"[{TEXT_DIM}]{mtu_status}[/{TEXT_DIM}]"

    traceroute_running = snap.get("traceroute_running", False)
    last_trace = snap.get("last_traceroute_time")
    if traceroute_running:
        traceroute_markup = f"[{YELLOW}]{t('traceroute_running')}[/{YELLOW}]"
    elif last_trace is not None:
        traceroute_markup = f"[{TEXT_DIM}]{fmt_since(last_trace)}[/{TEXT_DIM}]"
    else:
        traceroute_markup = f"[{TEXT_DIM}]{t('never')}[/{TEXT_DIM}]"

    items.append(Text(""))
    items.append(section_header(t("network"), inner_w))
    network_tbl = dual_kv_table(width)
    network_tbl.add_row(f"{t('ttl')}:", ttl_markup, f"{t('mtu')}:", mtu_markup)
    network_tbl.add_row(f"{t('mtu_status_label')}:", mtu_status_markup, f"{t('traceroute')}:", traceroute_markup)
    items.append(network_tbl)

    return Panel(
        Group(*items),
        title=f"[bold {ACCENT}]{t('analysis')}[/bold {ACCENT}]",
        title_align="left",
        border_style=ACCENT_DIM,
        box=box.ROUNDED,
        width=width,
        style=f"on {BG_PANEL}",
        padding=(0, 1),
    )
