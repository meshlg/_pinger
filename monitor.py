from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from config import (
    ALERT_ON_HIGH_LATENCY,
    ALERT_ON_PACKET_LOSS,
    AVG_LATENCY_THRESHOLD,
    CONSECUTIVE_LOSS_THRESHOLD,
    DNS_CHECK_INTERVAL,
    ENABLE_AUTO_TRACEROUTE,
    ENABLE_DNS_MONITORING,
    ENABLE_IP_CHANGE_ALERT,
    ENABLE_MTU_MONITORING,
    ENABLE_PROBLEM_ANALYSIS,
    ENABLE_ROUTE_ANALYSIS,
    ENABLE_THRESHOLD_ALERTS,
    ENABLE_HOP_MONITORING,
    HIGH_LATENCY_THRESHOLD,
    HOP_PING_INTERVAL,
    HOP_REDISCOVER_INTERVAL,
    JITTER_THRESHOLD,
    MTU_CHECK_INTERVAL,
    MTU_DIFF_THRESHOLD,
    MTU_ISSUE_CONSECUTIVE,
    MTU_CLEAR_CONSECUTIVE,
    ENABLE_TTL_MONITORING,
    PACKET_LOSS_THRESHOLD,
    PROBLEM_ANALYSIS_INTERVAL,
    ROUTE_ANALYSIS_INTERVAL,
    TARGET_IP,
    TRACEROUTE_TRIGGER_LOSSES,
    TTL_CHECK_INTERVAL,
    IP_CHECK_INTERVAL,
    t,
)
from stats_repository import StatsRepository
from services import (
    PingService,
    DNSService,
    MTUService,
    IPService,
    TracerouteService,
    HopMonitorService,
)
from problem_analyzer import ProblemAnalyzer
from route_analyzer import RouteAnalyzer
from alerts import add_visual_alert, clean_old_alerts, trigger_alert
from infrastructure import (
    METRICS_AVAILABLE,
    PING_TOTAL,
    PING_SUCCESS,
    PING_FAILURE,
    PING_LATENCY_MS,
    PACKET_LOSS_GAUGE,
    MTU_PROBLEMS_TOTAL,
    MTU_STATUS_GAUGE,
    ROUTE_CHANGES_TOTAL,
    ROUTE_CHANGED_GAUGE,
    start_metrics_server,
    HealthServer,
    start_health_server,
)


class Monitor:
    """
    Main monitoring orchestrator.
    
    Uses service layer for operations and StatsRepository for data.
    """

    def __init__(self) -> None:
        # Core infrastructure
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.stop_event = asyncio.Event()
        
        # Data repository
        self.stats_repo = StatsRepository()
        
        # Services
        self.ping_service = PingService()
        self.dns_service = DNSService()
        self.mtu_service = MTUService()
        self.ip_service = IPService()
        self.traceroute_service = TracerouteService(
            stats_lock=self.stats_repo.lock,
            stats=self.stats_repo.get_stats(),
            executor=self.executor,
        )
        
        # Hop monitor
        self.hop_monitor_service = HopMonitorService(executor=self.executor)
        
        # Analyzers
        self.problem_analyzer = ProblemAnalyzer(stats_repo=self.stats_repo)
        self.route_analyzer = RouteAnalyzer()
        
        # Infrastructure
        self.health_server = start_health_server(stats_repo=self.stats_repo)

    @property
    def stats_lock(self):
        """Backward compat for UI - use stats_repo.lock instead."""
        return self.stats_repo.lock

    @property
    def stats(self):
        """Backward compat - use stats_repo.get_stats() instead."""
        return self.stats_repo.get_stats()

    @property
    def recent_results(self):
        """Backward compat - use stats_repo.get_recent_results() instead."""
        return self.stats_repo.get_recent_results()

    def get_stats_snapshot(self) -> dict[str, Any]:
        """Get immutable snapshot for UI."""
        return self.stats_repo.get_snapshot()

    def shutdown(self) -> None:
        """Shutdown the monitor."""
        if self.health_server:
            self.health_server.stop()
        self.executor.shutdown(wait=True)

    async def run_blocking[T](self, func, *args, **kwargs) -> T:
        """Run blocking function in executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: func(*args, **kwargs)
        )

    # ==================== Main Loop ====================

    async def ping_once(self) -> tuple[bool, float | None]:
        """Single ping cycle."""
        ok, latency = await self.run_blocking(
            self.ping_service.ping_host,
            TARGET_IP
        )
        
        # Update stats
        high_lat, loss = self.stats_repo.update_after_ping(
            ok,
            latency,
            alert_on_high_latency=ALERT_ON_HIGH_LATENCY,
            high_latency_threshold=HIGH_LATENCY_THRESHOLD,
            alert_on_packet_loss=ALERT_ON_PACKET_LOSS,
        )
        
        # Handle alerts
        if high_lat:
            trigger_alert(self.stats_repo.lock, self.stats_repo.get_stats(), "high_latency")
        if loss:
            trigger_alert(self.stats_repo.lock, self.stats_repo.get_stats(), "loss")
            self._check_auto_traceroute()
        
        # Update Prometheus metrics
        if METRICS_AVAILABLE:
            try:
                PING_TOTAL.inc()
                if ok:
                    PING_SUCCESS.inc()
                    if latency is not None:
                        PING_LATENCY_MS.observe(latency)
                else:
                    PING_FAILURE.inc()
                
                snap = self.get_stats_snapshot()
                if snap["recent_results"]:
                    loss_pct = snap["recent_results"].count(False) / len(snap["recent_results"]) * 100
                    PACKET_LOSS_GAUGE.set(loss_pct)
            except Exception:
                pass
        
        return ok, latency

    def _check_auto_traceroute(self) -> None:
        """Trigger traceroute if conditions met."""
        if not ENABLE_AUTO_TRACEROUTE:
            return
        
        with self.stats_repo.lock:
            cons_losses = self.stats_repo.get_stats()["consecutive_losses"]
        
        if cons_losses >= TRACEROUTE_TRIGGER_LOSSES:
            self.traceroute_service.trigger_traceroute(TARGET_IP)

    def cleanup_alerts(self) -> None:
        """Clean old visual alerts."""
        clean_old_alerts(self.stats_repo.lock, self.stats_repo.get_stats())

    # ==================== Background Tasks ====================

    async def background_ip_updater(self) -> None:
        """Update public IP info periodically."""
        if not ENABLE_IP_CHANGE_ALERT:
            return
            
        while not self.stop_event.is_set():
            try:
                ip, country, code = await self.run_blocking(
                    self.ip_service.get_public_ip_info
                )
                
                # Check for IP change
                change_info = self.ip_service.check_ip_change(ip, country, code)
                if change_info:
                    add_visual_alert(
                        self.stats_repo.lock,
                        self.stats_repo.get_stats(),
                        f"[i] {t('alert_ip_changed').format(old=change_info['old_ip'], new=change_info['new_ip'])}",
                        "info"
                    )
                    trigger_alert(self.stats_repo.lock, self.stats_repo.get_stats(), "ip")
                
                # Update stats
                self.stats_repo.update_public_ip(ip, country, code)
                
            except Exception as exc:
                logging.error(f"IP update failed: {exc}")
            
            await asyncio.sleep(IP_CHECK_INTERVAL)

    async def background_dns_monitor(self) -> None:
        """Monitor DNS resolution."""
        if not ENABLE_DNS_MONITORING:
            return
            
        while not self.stop_event.is_set():
            try:
                # Use run_blocking because check_dns_resolve is sync (uses socket.gethostbyname)
                success, ms, status = await self.run_blocking(
                    self.dns_service.check_dns_resolve
                )
                self.stats_repo.update_dns(ms if success else None, status)
            except Exception as exc:
                logging.error(f"DNS monitor failed: {exc}")
                # Set status to failed on exception
                self.stats_repo.update_dns(None, t("failed"))
            
            await asyncio.sleep(DNS_CHECK_INTERVAL)

    async def background_mtu_monitor(self) -> None:
        """Monitor MTU."""
        if not ENABLE_MTU_MONITORING:
            return
            
        while not self.stop_event.is_set():
            try:
                # Get MTU info
                mtu_info = await self.run_blocking(
                    self.mtu_service.check_mtu,
                    TARGET_IP
                )
                
                local_mtu = mtu_info["local_mtu"]
                path_mtu = mtu_info["path_mtu"]
                
                # Determine status
                status = t("mtu_ok")
                if local_mtu and path_mtu:
                    diff = local_mtu - path_mtu
                    if path_mtu < 1000:
                        status = t("mtu_fragmented")
                    elif diff >= MTU_DIFF_THRESHOLD and path_mtu < local_mtu:
                        status = t("mtu_low")
                
                # Update stats with hysteresis logic
                with self.stats_repo.lock:
                    stats = self.stats_repo.get_stats()
                    current = stats.get("mtu_status", t("mtu_ok"))
                    
                    # Update counters
                    if status in [t("mtu_low"), t("mtu_fragmented")]:
                        stats["mtu_consecutive_issues"] = stats.get("mtu_consecutive_issues", 0) + 1
                        stats["mtu_consecutive_ok"] = 0
                    else:
                        stats["mtu_consecutive_ok"] = stats.get("mtu_consecutive_ok", 0) + 1
                        stats["mtu_consecutive_issues"] = 0
                    
                    # Apply hysteresis
                    if status in [t("mtu_low"), t("mtu_fragmented")]:
                        if stats["mtu_consecutive_issues"] >= MTU_ISSUE_CONSECUTIVE and current != status:
                            self.stats_repo.update_mtu(local_mtu, path_mtu, status)
                            stats["mtu_last_status_change"] = datetime.now()
                            logging.info(f"MTU problem: {status}")
                            if METRICS_AVAILABLE:
                                try:
                                    MTU_PROBLEMS_TOTAL.inc()
                                    MTU_STATUS_GAUGE.set(1 if status == t("mtu_low") else 2)
                                except Exception:
                                    pass
                    else:
                        if stats["mtu_consecutive_ok"] >= MTU_CLEAR_CONSECUTIVE and current != t("mtu_ok"):
                            self.stats_repo.update_mtu(local_mtu, path_mtu, t("mtu_ok"))
                            stats["mtu_last_status_change"] = datetime.now()
                            logging.info("MTU status cleared")
                            if METRICS_AVAILABLE:
                                try:
                                    MTU_STATUS_GAUGE.set(0)
                                except Exception:
                                    pass
                
            except Exception as exc:
                logging.error(f"MTU monitor failed: {exc}")
            
            await asyncio.sleep(MTU_CHECK_INTERVAL)

    async def background_ttl_monitor(self) -> None:
        """Monitor TTL."""
        if not ENABLE_TTL_MONITORING:
            return
            
        while not self.stop_event.is_set():
            try:
                ttl, hops = await self.run_blocking(
                    self._extract_ttl,
                    TARGET_IP
                )
                self.stats_repo.update_ttl(ttl, hops)
            except Exception as exc:
                logging.error(f"TTL monitor failed: {exc}")
            
            await asyncio.sleep(TTL_CHECK_INTERVAL)

    def _extract_ttl(self, host: str) -> tuple[int | None, int | None]:
        """Extract TTL from ping - using PingService internals."""
        try:
            ping_cmd = shutil.which("ping")
            if not ping_cmd:
                return None, None
            
            is_ipv6 = self.ping_service._detect_ipv6(host)
            
            if sys.platform == "win32":
                cmd = [ping_cmd, "-n", "1", "-w", "1000", host]
                encoding = "oem"
            else:
                if is_ipv6:
                    cmd = [ping_cmd, "-6", "-c", "1", host]
                else:
                    cmd = [ping_cmd, "-c", "1", host]
                encoding = "utf-8"
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2,
                encoding=encoding,
                errors="replace",
            )
            
            ttl_match = re.search(r"TTL[=:\s]+(\d+)", result.stdout, re.IGNORECASE)
            if ttl_match:
                ttl = int(ttl_match.group(1))
                common_initial_ttl_values = [64, 128, 255]
                estimated_hops = None
                for initial_ttl in common_initial_ttl_values:
                    if ttl <= initial_ttl:
                        estimated_hops = initial_ttl - ttl
                        break
                return ttl, estimated_hops
        except Exception as exc:
            logging.error(f"TTL extraction failed: {exc}")
        return None, None

    async def background_problem_analyzer(self) -> None:
        """Analyze problems periodically."""
        if not ENABLE_PROBLEM_ANALYSIS:
            return
            
        while not self.stop_event.is_set():
            try:
                problem_type = self.problem_analyzer.analyze_current_problem()
                prediction = self.problem_analyzer.predict_problems()
                pattern = self.problem_analyzer.identify_pattern()
                
                self.stats_repo.update_problem_analysis(problem_type, prediction, pattern)
                
            except Exception as exc:
                logging.error(f"Problem analysis failed: {exc}")
            
            await asyncio.sleep(PROBLEM_ANALYSIS_INTERVAL)

    async def background_hop_monitor(self) -> None:
        """Discover hops and ping them periodically."""
        if not ENABLE_HOP_MONITORING:
            return

        import time as _time

        # Initial discovery
        self.stats_repo.update_hop_monitor([], discovering=True)
        await self.run_blocking(
            self.hop_monitor_service.discover_hops, TARGET_IP
        )
        self.stats_repo.update_hop_monitor(
            self.hop_monitor_service.get_hops_snapshot(), discovering=False
        )

        last_discovery = _time.time()

        while not self.stop_event.is_set():
            try:
                # Ping all hops
                await self.run_blocking(self.hop_monitor_service.ping_all_hops)
                self.stats_repo.update_hop_monitor(
                    self.hop_monitor_service.get_hops_snapshot(), discovering=False
                )

                # Re-discover hops periodically
                if _time.time() - last_discovery > HOP_REDISCOVER_INTERVAL:
                    self.stats_repo.update_hop_monitor(
                        self.hop_monitor_service.get_hops_snapshot(), discovering=True
                    )
                    await self.run_blocking(
                        self.hop_monitor_service.discover_hops, TARGET_IP
                    )
                    self.stats_repo.update_hop_monitor(
                        self.hop_monitor_service.get_hops_snapshot(), discovering=False
                    )
                    last_discovery = _time.time()

            except Exception as exc:
                logging.error(f"Hop monitor failed: {exc}")

            await asyncio.sleep(HOP_PING_INTERVAL)

    async def background_route_analyzer(self) -> None:
        """Analyze route periodically."""
        from config import (
            ROUTE_CHANGE_CONSECUTIVE,
            ROUTE_CHANGE_HOP_DIFF,
            ROUTE_IGNORE_FIRST_HOPS,
            ROUTE_SAVE_ON_CHANGE_CONSECUTIVE,
        )
        
        if not ENABLE_ROUTE_ANALYSIS:
            return
            
        while not self.stop_event.is_set():
            try:
                traceroute_output = await self.run_blocking(
                    self.traceroute_service.run_traceroute,
                    TARGET_IP
                )
                
                hops = self.route_analyzer.parse_traceroute_output(traceroute_output)
                analysis = self.route_analyzer.analyze_route(hops)
                
                # Determine significant diffs
                diff_indices = analysis.get("diff_indices", [])
                significant_diffs = [i for i in diff_indices if i >= ROUTE_IGNORE_FIRST_HOPS]
                sig_count = len(significant_diffs)
                
                # Update consecutive counters
                with self.stats_repo.lock:
                    stats = self.stats_repo.get_stats()
                    
                    if sig_count >= ROUTE_CHANGE_HOP_DIFF:
                        stats["route_consecutive_changes"] = stats.get("route_consecutive_changes", 0) + 1
                        stats["route_consecutive_ok"] = 0
                    else:
                        stats["route_consecutive_ok"] = stats.get("route_consecutive_ok", 0) + 1
                        stats["route_consecutive_changes"] = 0
                    
                    # Update route status
                    route_changed = False
                    if stats["route_consecutive_changes"] >= ROUTE_CHANGE_CONSECUTIVE:
                        if not stats.get("route_changed"):
                            route_changed = True
                            stats["route_changed"] = True
                            stats["route_last_change_time"] = datetime.now()
                            add_visual_alert(
                                self.stats_repo.lock,
                                stats,
                                f"[i] {t('route_changed')}",
                                "info"
                            )
                            if METRICS_AVAILABLE:
                                try:
                                    ROUTE_CHANGES_TOTAL.inc()
                                    ROUTE_CHANGED_GAUGE.set(1)
                                except Exception:
                                    pass
                            
                            # Auto-trigger traceroute on route change
                            if stats["route_consecutive_changes"] >= ROUTE_SAVE_ON_CHANGE_CONSECUTIVE:
                                self.traceroute_service.trigger_traceroute(TARGET_IP)
                    
                    elif stats["route_consecutive_ok"] >= ROUTE_CHANGE_CONSECUTIVE:
                        if stats.get("route_changed"):
                            stats["route_changed"] = False
                            stats["route_last_change_time"] = datetime.now()
                            add_visual_alert(
                                self.stats_repo.lock,
                                stats,
                                f"[i] {t('route_stable')}",
                                "info"
                            )
                            if METRICS_AVAILABLE:
                                try:
                                    ROUTE_CHANGED_GAUGE.set(0)
                                except Exception:
                                    pass
                    
                    # Update route info
                    self.stats_repo.update_route(
                        hops,
                        analysis["problematic_hop"],
                        stats["route_changed"],
                        sig_count
                    )
                    
                    # Alert on problematic hop
                    if analysis["problematic_hop"]:
                        add_visual_alert(
                            self.stats_repo.lock,
                            stats,
                            f"[!] {t('problematic_hop')}: {analysis['problematic_hop']}",
                            "warning"
                        )
                
            except Exception as exc:
                logging.error(f"Route analysis failed: {exc}")
            
            await asyncio.sleep(ROUTE_ANALYSIS_INTERVAL)

    # ==================== Threshold Checking ====================

    def check_thresholds(self) -> None:
        """Check all thresholds and trigger alerts."""
        if not ENABLE_THRESHOLD_ALERTS:
            return
        
        snap = self.get_stats_snapshot()
        
        # Packet loss threshold
        loss30 = (
            snap["recent_results"].count(False) / len(snap["recent_results"]) * 100
            if snap["recent_results"]
            else 0.0
        )
        
        self._check_packet_loss_threshold(loss30, snap)
        self._check_avg_latency_threshold(snap)
        self._check_connection_lost_threshold(snap)
        self._check_jitter_threshold(snap)

    def _check_packet_loss_threshold(self, loss30: float, snap: dict) -> None:
        """Check packet loss threshold."""
        was_high = self.stats_repo.get_threshold_state("high_packet_loss")
        
        if loss30 > PACKET_LOSS_THRESHOLD:
            if not was_high:
                self.stats_repo.update_threshold_state("high_packet_loss", True)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[!] {t('alert_high_loss').format(val=loss30)}",
                    "warning",
                )
                logging.warning(f"Loss30 exceeded: {loss30:.1f}%")
                trigger_alert(self.stats_repo.lock, self.stats_repo.get_stats(), "loss")
        else:
            if was_high:
                self.stats_repo.update_threshold_state("high_packet_loss", False)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[+] {t('alert_loss_normalized')}",
                    "info"
                )

    def _check_avg_latency_threshold(self, snap: dict) -> None:
        """Check average latency threshold."""
        success = snap["success"]
        avg = (snap["total_latency_sum"] / success) if success else 0.0
        was_high = self.stats_repo.get_threshold_state("high_avg_latency")
        
        if avg > AVG_LATENCY_THRESHOLD:
            if not was_high:
                self.stats_repo.update_threshold_state("high_avg_latency", True)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[!] {t('alert_high_avg_latency').format(val=avg)}",
                    "warning",
                )
                logging.warning(f"Avg latency exceeded: {avg:.1f}ms")
        else:
            if was_high:
                self.stats_repo.update_threshold_state("high_avg_latency", False)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[+] {t('alert_latency_normalized')}",
                    "info"
                )

    def _check_connection_lost_threshold(self, snap: dict) -> None:
        """Check consecutive losses threshold."""
        cons_losses = snap["consecutive_losses"]
        was_lost = self.stats_repo.get_threshold_state("connection_lost")
        
        if cons_losses >= CONSECUTIVE_LOSS_THRESHOLD:
            if not was_lost:
                self.stats_repo.update_threshold_state("connection_lost", True)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[X] {t('alert_connection_lost').format(n=cons_losses)}",
                    "critical",
                )
                logging.critical(f"Connection lost: {cons_losses} consecutive")
                trigger_alert(self.stats_repo.lock, self.stats_repo.get_stats(), "lost")
        else:
            if was_lost:
                self.stats_repo.update_threshold_state("connection_lost", False)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[+] {t('alert_connection_restored')}",
                    "success"
                )
                logging.info("Connection restored")

    def _check_jitter_threshold(self, snap: dict) -> None:
        """Check jitter threshold."""
        jitter = snap["jitter"]
        was_high = self.stats_repo.get_threshold_state("high_jitter")
        
        if jitter > JITTER_THRESHOLD:
            if not was_high:
                self.stats_repo.update_threshold_state("high_jitter", True)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[!] {t('alert_high_jitter').format(val=jitter)}",
                    "warning",
                )
                logging.warning(f"Jitter exceeded: {jitter:.1f}ms")
        else:
            if was_high:
                self.stats_repo.update_threshold_state("high_jitter", False)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[+] {t('alert_jitter_normalized')}",
                    "info"
                )
