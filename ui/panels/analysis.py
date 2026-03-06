"""Analysis & Monitoring panel renderer."""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.theme import (
    ACCENT,
    ACCENT_DIM,
    BAR_EMPTY,
    BAR_FULL,
    BG_PANEL,
    GREEN,
    HeightTier,
    LayoutTier,
    RED,
    TEXT_DIM,
    WHITE,
    YELLOW,
)
from ui.helpers import (
    dns_mini_bar,
    dual_kv_table,
    ensure_utc,
    fmt_since,
    kv_table,
    mini_gauge,
    section_header,
    sparkline,
    truncate,
)

try:
    from config import SHOW_VISUAL_ALERTS, t
except ImportError:
    from ...config import SHOW_VISUAL_ALERTS, t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


def render_analysis_panel(
    snap: StatsSnapshot, width: int, tier: LayoutTier, h_tier: HeightTier
) -> Panel:
    """Render the combined analysis & monitoring panel."""
    inner_w = max(20, width - 4)
    items: list[Table | Text] = []
    connection_lost = bool(snap.get("threshold_states", {}).get("connection_lost", False))

    # ── Problem analysis ──
    items.append(section_header(t("problem_analysis"), inner_w))
    problem_type = snap.get("current_problem_type", t("problem_none"))
    if connection_lost:
        problem_type = t("problem_isp")
    if problem_type == t("problem_none"):
        pt_txt = f"[{GREEN}]{problem_type}[/{GREEN}]"
    elif problem_type in [t("problem_isp"), t("problem_dns")]:
        pt_txt = f"[{RED}]{problem_type}[/{RED}]"
    elif problem_type in [t("problem_local"), t("problem_mtu")]:
        pt_txt = f"[{YELLOW}]{problem_type}[/{YELLOW}]"
    else:
        pt_txt = f"[{WHITE}]{problem_type}[/{WHITE}]"

    prediction = snap.get("problem_prediction", t("prediction_stable"))
    if connection_lost:
        prediction = t("prediction_risk")
    pred_txt = (
        f"[{GREEN}]{prediction}[/{GREEN}]"
        if prediction == t("prediction_stable")
        else f"[{YELLOW}]{prediction}[/{YELLOW}]"
    )

    prob_tbl = kv_table(width, key_width=14)
    prob_tbl.add_row(f"{t('problem_type')}:", pt_txt)
    prob_tbl.add_row(f"{t('prediction')}:", pred_txt)
    if h_tier not in ("minimal", "short"):
        pattern = snap.get("problem_pattern", "...")
        pat_txt = f"[{WHITE}]{pattern}[/{WHITE}]" if pattern != "..." else f"[{TEXT_DIM}]...[/{TEXT_DIM}]"
        prob_tbl.add_row(f"{t('pattern')}:", pat_txt)
    items.append(prob_tbl)

    # Last problem time
    if snap["last_problem_time"] is None:
        last_prob_txt = f"[{GREEN}]{t('never')}[/{GREEN}]"
    else:
        lpt = ensure_utc(snap["last_problem_time"])
        if lpt is None:
            last_prob_txt = f"[{GREEN}]{t('never')}[/{GREEN}]"
        else:
            age = (datetime.now(timezone.utc) - lpt).total_seconds()
            since_txt = fmt_since(snap["last_problem_time"])
            last_prob_txt = f"[{RED}]{since_txt}[/{RED}]" if age < 60 else f"[{YELLOW}]{since_txt}[/{YELLOW}]"

    lp_tbl = kv_table(width, key_width=14)
    lp_tbl.add_row(f"{t('last_problem')}:", last_prob_txt)
    items.append(lp_tbl)

    # ── Route analysis ──
    items.append(section_header(t("route_analysis"), inner_w))
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
        rs_txt = f"[{RED}]{t('status_disconnected')}[/{RED}]"
    else:
        rs_txt = f"[{YELLOW}]{t('route_changed')}[/{YELLOW}]" if route_changed else f"[{GREEN}]{t('route_stable')}[/{GREEN}]"
    ph_txt = f"[{RED}]{problematic_hop}[/{RED}]" if problematic_hop else f"[{GREEN}]{t('none_label')}[/{GREEN}]"
    hc_txt = f"[{WHITE}]{hop_count}[/{WHITE}]" if hop_count > 0 else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"

    route_tbl = kv_table(width, key_width=14)
    route_tbl.add_row(f"{t('route_label')}:", rs_txt)
    route_tbl.add_row(f"{t('hops_count')}:", hc_txt)
    route_tbl.add_row(f"{t('problematic_hop_short')}:", ph_txt)

    if h_tier not in ("minimal", "short"):
        avg_route_latency = None
        if route_hops:
            lat_list = [h_["avg_latency"] for h_ in route_hops if h_.get("avg_latency") is not None]
            if lat_list:
                avg_route_latency = statistics.mean(lat_list)
        avg_rl_txt = f"[{WHITE}]{avg_route_latency:.1f}[/{WHITE}] {t('ms')}" if avg_route_latency else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
        route_tbl.add_row(f"{t('avg_latency_short')}:", avg_rl_txt)

        route_diff = snap.get("route_last_diff_count", 0)
        route_cons = snap.get("route_consecutive_changes", 0)
        route_last_change = snap.get("route_last_change_time")
        if connection_lost:
            route_diff = 0
            route_cons = 0
            route_last_change = None
        diff_txt = f"[{TEXT_DIM}]{route_diff} {t('hops_unit')}[/{TEXT_DIM}]" if route_diff else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
        cons_r_txt = f"[{TEXT_DIM}]{route_cons} / {fmt_since(route_last_change)}[/{TEXT_DIM}]" if route_cons else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
        route_tbl.add_row(f"{t('changed_hops')}:", diff_txt)
        route_tbl.add_row(f"{t('changes')}:", cons_r_txt)
    items.append(route_tbl)

    # ── DNS ──
    items.append(section_header(t("dns"), inner_w))

    # DNS Health (Score, Reliability, Jitter)
    dns_health = snap.get("dns_health", {})
    dns_results = snap.get("dns_results", {})
    dns_benchmark = snap.get("dns_benchmark", {})

    # Score color based on status
    if dns_health:
        status = dns_health.get("status", "critical")
        if status == "excellent":
            score_color = GREEN
        elif status == "good":
            score_color = GREEN
        elif status == "fair":
            score_color = YELLOW
        elif status == "poor":
            score_color = RED
        else:
            score_color = RED
    else:
        score_color = TEXT_DIM

    # Line 1: Score + Reliability + Jitter (compact header) with gauge
    if dns_health:
        score = dns_health.get("score", 0)
        reliability = dns_health.get("reliability", 0)
        jitter = dns_health.get("jitter")

        score_gauge = mini_gauge(score, max_val=100.0, width=5, color=score_color)
        rel_txt = f"[{WHITE}]{reliability:.0f}%[/{WHITE}]"
        jitter_txt = f"[{WHITE}]{jitter:.1f}[/{WHITE}]" if jitter else f"[{TEXT_DIM}]—[/{TEXT_DIM}]"

        items.append(Text.from_markup(
            f"  [{TEXT_DIM}]{t('dns_score')}:[/{TEXT_DIM}] {score_gauge}  "
            f"[{TEXT_DIM}]{t('dns_reliability_short')}:[/{TEXT_DIM}]{rel_txt}  "
            f"[{TEXT_DIM}]{t('dns_jitter_short')}:[/{TEXT_DIM}]{jitter_txt}{t('ms')}"
        ))
    elif snap["dns_resolve_time"] is None and not dns_health:
        dns_fallback = f"  [{RED}]{t('error')}[/{RED}]" if SHOW_VISUAL_ALERTS else f"  [{TEXT_DIM}]—[/{TEXT_DIM}]"
        items.append(Text.from_markup(dns_fallback))
    elif not dns_health:
        ms_dns = snap["dns_resolve_time"]
        if snap["dns_status"] == t("ok"):
            items.append(Text.from_markup(f"  [{GREEN}]{t('ok_label')}[/{GREEN}] [{TEXT_DIM}]({ms_dns:.0f}{t('ms')})[/{TEXT_DIM}]"))
        elif snap["dns_status"] == t("slow"):
            items.append(Text.from_markup(f"  [{YELLOW}]{t('slow')}[/{YELLOW}] [{TEXT_DIM}]({ms_dns:.0f}{t('ms')})[/{TEXT_DIM}]"))
        else:
            items.append(Text.from_markup(f"  [{RED}]{t('error')}[/{RED}]"))

    # Line 2: Detailed DNS table by record type (in standard/full height)
    if dns_results and h_tier not in ("minimal", "short"):
        # Create a compact table for DNS record types
        dns_tbl = Table(
            show_header=True,
            header_style=f"bold {TEXT_DIM}",
            box=None,
            padding=(0, 1),
            width=inner_w,
        )
        dns_tbl.add_column(t("hop_col_num"), width=5, justify="left", no_wrap=True)
        dns_tbl.add_column(t("status_ok"), width=6, justify="center", no_wrap=True)
        dns_tbl.add_column(t("avg_short"), width=6, justify="right", no_wrap=True)
        dns_tbl.add_column("", width=8, justify="left", no_wrap=True)  # mini bar
        dns_tbl.add_column(t("ttl"), width=5, justify="right", no_wrap=True)
        dns_tbl.add_column(t("hop_col_host"), ratio=1, no_wrap=True, overflow="ellipsis")

        for rt in ["A", "AAAA", "NS", "MX", "CNAME", "TXT"]:
            res = dns_results.get(rt)
            if not res:
                continue

            success = res.get("success", False)
            ms_v = res.get("response_time_ms")
            ttl_v = res.get("ttl")
            record_count = res.get("record_count", 0)
            dns_st = res.get("status", t("failed"))

            # Status icon
            if success:
                if dns_st == t("slow"):
                    st_txt = f"[{YELLOW}] ~ [/{YELLOW}]"
                else:
                    st_txt = f"[{GREEN}] ✓ [/{GREEN}]"
            else:
                st_txt = f"[{RED}] ✗ [/{RED}]"

            # Response time + mini bar
            if ms_v is not None:
                ms_color = GREEN if ms_v < 50 else (YELLOW if ms_v < 150 else RED)
                ms_txt = f"[{ms_color}]{ms_v:.0f}[/{ms_color}]"
                ms_bar = dns_mini_bar(ms_v, max_ms=200.0, width=6)
            else:
                ms_txt = f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
                ms_bar = f"[{TEXT_DIM}]      [/{TEXT_DIM}]"

            # TTL
            if ttl_v is not None:
                ttl_txt = f"[{TEXT_DIM}]{ttl_v}[/{TEXT_DIM}]"
            else:
                ttl_txt = f"[{TEXT_DIM}]—[/{TEXT_DIM}]"

            # Value preview (count or error)
            if success and record_count > 0:
                val_txt = f"[{TEXT_DIM}]{record_count} {t('checks_unit')}[/{TEXT_DIM}]"
            elif not success:
                err = res.get("error", "")
                val_txt = f"[{RED}]{truncate(err or t('failed'), 20)}[/{RED}]"
            else:
                val_txt = f"[{TEXT_DIM}]—[/{TEXT_DIM}]"

            dns_tbl.add_row(
                f"[{ACCENT}]{rt}[/{ACCENT}]",
                st_txt,
                ms_txt,
                Text.from_markup(ms_bar),
                ttl_txt,
                val_txt,
            )

        items.append(Text(""))
        items.append(dns_tbl)

    # Line 3: Benchmark (C:cached U:uncached D:dotcom) - compact format
    if dns_benchmark and h_tier not in ("minimal",):
        bench_parts: list[str] = []
        all_avg: list[float] = []
        for tt in ["cached", "uncached", "dotcom"]:
            r = dns_benchmark.get(tt, {})
            lbl = tt[0].upper()
            if not r.get("success"):
                bench_parts.append(f"[{RED}]{lbl}:✗[/{RED}]")
            else:
                rv = r.get("response_time_ms")
                v_str = f"{rv:.0f}" if rv else "—"
                st = r.get("status", "failed")
                c = GREEN if st == t("ok") else (YELLOW if st == t("slow") else RED)
                bench_parts.append(f"[{c}]{lbl}:{v_str}[/{c}]")
            if r.get("avg_ms") is not None:
                all_avg.append(r["avg_ms"])

        # Compact: C:18  U:114  D:18  │ ср:55мс
        items.append(Text(""))  # Add empty line before benchmark
        bench_line = f"  {' '.join(bench_parts)}"
        if all_avg:
            bench_line += f"  [{ACCENT_DIM}]│[/{ACCENT_DIM}]  [{TEXT_DIM}]{t('avg_short')}:{sum(all_avg)/len(all_avg):.0f}{t('ms')}[/{TEXT_DIM}]"
        items.append(Text.from_markup(bench_line))

    # ── Network (TTL, MTU, Traceroute) ──
    items.append(section_header(t("network"), inner_w))
    if connection_lost:
        ttl_txt = f"[{TEXT_DIM}]—[/{TEXT_DIM}]"
    else:
        ttl = snap["last_ttl"]
        ttl_hops_val = snap["ttl_hops"]
        ttl_txt = f"[{WHITE}]{ttl}[/{WHITE}]"
        if ttl:
            if ttl_hops_val:
                ttl_txt += f" [{TEXT_DIM}]({ttl_hops_val} {t('hop_unit')})[/{TEXT_DIM}]"
        else:
            ttl_txt = f"[{TEXT_DIM}]—[/{TEXT_DIM}]"

    local_mtu = snap["local_mtu"]
    path_mtu = snap["path_mtu"]
    if connection_lost:
        mtu_val = f"[{TEXT_DIM}]—[/{TEXT_DIM}]/[{TEXT_DIM}]—[/{TEXT_DIM}]"
        mtu_s = f"[{RED}]{t('status_disconnected')}[/{RED}]"
    else:
        mtu_val = f"[{WHITE}]{local_mtu or '—'}[/{WHITE}]/[{WHITE}]{path_mtu or '—'}[/{WHITE}]"
        mtu_status = snap.get("mtu_status", "...")
        if mtu_status == t("mtu_ok"):
            mtu_s = f"[{GREEN}]{mtu_status}[/{GREEN}]"
        elif mtu_status == t("mtu_low"):
            mtu_s = f"[{YELLOW}]{mtu_status}[/{YELLOW}]"
        elif mtu_status == t("mtu_fragmented"):
            mtu_s = f"[{RED}]{mtu_status}[/{RED}]"
        else:
            mtu_s = f"[{TEXT_DIM}]{mtu_status}[/{TEXT_DIM}]"

    if snap["traceroute_running"]:
        tr_txt = f"[{YELLOW}]{t('traceroute_running')}[/{YELLOW}]"
    elif snap["last_traceroute_time"]:
        tr_txt = f"[{TEXT_DIM}]{fmt_since(snap['last_traceroute_time'])}[/{TEXT_DIM}]"
    else:
        tr_txt = f"[{TEXT_DIM}]{t('never')}[/{TEXT_DIM}]"

    net_tbl = dual_kv_table(width)
    net_tbl.add_row(f"{t('ttl')}:", ttl_txt, f"{t('mtu')}:", mtu_val)
    net_tbl.add_row(f"{t('mtu_status_label')}:", mtu_s, f"{t('traceroute')}:", tr_txt)
    items.append(net_tbl)

    return Panel(
        Group(*items),
        title=f"[bold {ACCENT}]{t('analysis')} & {t('mon')}[/bold {ACCENT}]",
        title_align="left",
        border_style=ACCENT_DIM,
        box=box.ROUNDED,
        width=width,
        style=f"on {BG_PANEL}",
    )
