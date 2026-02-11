from __future__ import annotations

import asyncio
import logging
import os
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
    DNS_RECORD_TYPES,
    ENABLE_AUTO_TRACEROUTE,
    ENABLE_DNS_MONITORING,
    ENABLE_IP_CHANGE_ALERT,
    ENABLE_MTU_MONITORING,
    ENABLE_PROBLEM_ANALYSIS,
    ENABLE_ROUTE_ANALYSIS,
    ENABLE_THRESHOLD_ALERTS,
    ENABLE_HOP_MONITORING,
    ENABLE_VERSION_CHECK,
    VERSION_CHECK_INTERVAL,
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
    ENABLE_METRICS,
    METRICS_ADDR,
    METRICS_PORT,
    ENABLE_HEALTH_ENDPOINT,
    HEALTH_ADDR,
    HEALTH_PORT,
    MAX_WORKER_THREADS,
    SHUTDOWN_TIMEOUT_SECONDS,
    # Smart alert settings
    ENABLE_SMART_ALERTS,
    ALERT_DEDUP_WINDOW_SECONDS,
    ALERT_GROUP_WINDOW_SECONDS,
    ALERT_RATE_LIMIT_PER_MINUTE,
    ALERT_BURST_LIMIT,
    ALERT_ESCALATION_TIME_MINUTES,
    ENABLE_ALERT_DEDUPLICATION,
    ENABLE_ALERT_GROUPING,
    ENABLE_DYNAMIC_PRIORITY,
    ENABLE_ADAPTIVE_THRESHOLDS,
    t,
)

# Core handlers (refactored from ping_once)
from core import PingHandler, AlertHandler, MetricsHandler
from stats_repository import StatsRepository, StatsSnapshot
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
    Uses core handlers for ping cycle operations (SRP-compliant).
    """

    def __init__(self) -> None:
        # Core infrastructure - use configured max workers
        self.executor = ThreadPoolExecutor(
            max_workers=MAX_WORKER_THREADS,
            thread_name_prefix="pinger_"
        )
        self._executor_tasks: set[asyncio.Task] = set()
        self.stop_event = asyncio.Event()
        self._shutdown_complete = asyncio.Event()
        self._active_subprocesses: set[subprocess.Popen] = set()
        self._subprocess_lock = __import__('threading').Lock()
        
        # Memory monitoring counter (check every N pings)
        self._ping_counter = 0
        self._memory_check_interval = 10
        
        # Data repository
        self.stats_repo = StatsRepository()
        
        # Services
        self.ping_service = PingService()
        self.dns_service = DNSService()
        self.mtu_service = MTUService()
        self.ip_service = IPService()
        self.traceroute_service = TracerouteService(
            stats_repo=self.stats_repo,
            executor=self.executor,
        )
        
        # Hop monitor
        self.hop_monitor_service = HopMonitorService(executor=self.executor)
        
        # Analyzers
        self.problem_analyzer = ProblemAnalyzer(stats_repo=self.stats_repo)
        self.route_analyzer = RouteAnalyzer()
        
        # Smart Alert Manager (if enabled)
        self.smart_alert_manager = None
        if ENABLE_SMART_ALERTS:
            from core import SmartAlertManager
            self.smart_alert_manager = SmartAlertManager(
                stats_repo=self.stats_repo,
                dedup_window_seconds=ALERT_DEDUP_WINDOW_SECONDS,
                group_window_seconds=ALERT_GROUP_WINDOW_SECONDS,
                rate_limit_per_minute=ALERT_RATE_LIMIT_PER_MINUTE,
                rate_limit_burst=ALERT_BURST_LIMIT,
                escalation_threshold_minutes=ALERT_ESCALATION_TIME_MINUTES,
                enable_deduplication=ENABLE_ALERT_DEDUPLICATION,
                enable_grouping=ENABLE_ALERT_GROUPING,
                enable_dynamic_priority=ENABLE_DYNAMIC_PRIORITY,
                enable_adaptive_thresholds=ENABLE_ADAPTIVE_THRESHOLDS,
            )
        
        # Core handlers (SRP-compliant)
        self._ping_handler = PingHandler(self.ping_service, TARGET_IP)
        self._alert_handler = AlertHandler(
            self.stats_repo,
            self.traceroute_service,
            smart_alert_manager=self.smart_alert_manager,
        )
        self._metrics_handler = MetricsHandler(self.stats_repo)
        
        # Infrastructure
        self.metrics_server = None
        if ENABLE_METRICS:
            self.metrics_server = start_metrics_server(addr=METRICS_ADDR, port=METRICS_PORT)
        self.health_server = None
        if ENABLE_HEALTH_ENDPOINT:
            self.health_server = start_health_server(addr=HEALTH_ADDR, port=HEALTH_PORT, stats_repo=self.stats_repo)

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

    def get_stats_snapshot(self) -> StatsSnapshot:
        """Get immutable snapshot for UI."""
        return self.stats_repo.get_snapshot()

    def register_subprocess(self, proc: subprocess.Popen) -> None:
        """Register a child subprocess for tracking."""
        with self._subprocess_lock:
            self._active_subprocesses.add(proc)

    def unregister_subprocess(self, proc: subprocess.Popen) -> None:
        """Unregister a completed subprocess."""
        with self._subprocess_lock:
            self._active_subprocesses.discard(proc)

    def _kill_all_subprocesses(self) -> None:
        """Kill all tracked child subprocesses."""
        with self._subprocess_lock:
            procs = list(self._active_subprocesses)
            self._active_subprocesses.clear()
        for proc in procs:
            try:
                proc.kill()
                logging.debug(f"Killed subprocess pid={proc.pid}")
            except Exception:
                pass
        # Also ask services to kill their tracked processes
        try:
            self.hop_monitor_service.kill_active_processes()
        except Exception:
            pass

    def shutdown(self) -> None:
        """Shutdown the monitor gracefully with timeout and force kill fallback."""
        logging.info("Monitor shutdown initiated...")
        
        # Signal all background tasks to stop
        self.stop_event.set()
        
        # Kill all tracked child subprocesses FIRST
        self._kill_all_subprocesses()
        
        # Cancel any pending executor tasks
        for task in list(self._executor_tasks):
            if not task.done():
                task.cancel()
        
        # Shutdown executor with manual timeout (shutdown() has no timeout param)
        try:
            import threading as _threading
            _shutdown_done = _threading.Event()
            
            def _do_executor_shutdown():
                try:
                    if sys.version_info >= (3, 9):
                        self.executor.shutdown(wait=True, cancel_futures=True)
                    else:
                        self.executor.shutdown(wait=True)
                finally:
                    _shutdown_done.set()
            
            _t = _threading.Thread(target=_do_executor_shutdown, daemon=True)
            _t.start()
            
            if _shutdown_done.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS):
                logging.info("Executor shutdown completed gracefully")
            else:
                logging.warning(f"Executor shutdown timed out after {SHUTDOWN_TIMEOUT_SECONDS}s, forcing close")
                try:
                    if sys.version_info >= (3, 9):
                        self.executor.shutdown(wait=False, cancel_futures=True)
                    else:
                        self.executor.shutdown(wait=False)
                except Exception:
                    pass
        except Exception as exc:
            logging.warning(f"Executor shutdown error: {exc}")
        
        # Stop metrics server
        if self.metrics_server:
            try:
                self.metrics_server.stop()
                logging.info("Metrics server stopped")
            except Exception as exc:
                logging.warning(f"Metrics server shutdown error: {exc}")
        
        # Stop health server
        if self.health_server:
            try:
                self.health_server.stop()
                logging.info("Health server stopped")
            except Exception as exc:
                logging.warning(f"Health server shutdown error: {exc}")
        
        self._shutdown_complete.set()
        logging.info("Monitor shutdown complete")
        
        # Force exit if threads are still hanging
        import threading as _threading
        alive = [t for t in _threading.enumerate()
                 if t.is_alive() and not t.daemon and t != _threading.main_thread()]
        if alive:
            logging.warning(f"Force exiting: {len(alive)} non-daemon threads still alive")
            os._exit(0)

    async def run_blocking(self, func, *args, **kwargs) -> Any:
        """Run blocking function in executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: func(*args, **kwargs)
        )

    # ==================== Main Loop ====================

    async def ping_once(self) -> tuple[bool, float | None]:
        """
        Single ping cycle using SRP-compliant handlers.
        
        Delegates to:
        - PingHandler: Execute ping
        - StatsRepository: Update statistics
        - AlertHandler: Process alerts
        - MetricsHandler: Update Prometheus metrics
        """
        # 1. Execute ping (PingHandler - SRP)
        result = await self._ping_handler.execute_async(self.executor)
        
        # 2. Update statistics (StatsRepository)
        high_lat, loss = self.stats_repo.update_after_ping(
            result.success,
            result.latency,
            alert_on_high_latency=ALERT_ON_HIGH_LATENCY,
            high_latency_threshold=HIGH_LATENCY_THRESHOLD,
            alert_on_packet_loss=ALERT_ON_PACKET_LOSS,
        )
        
        # 3. Handle alerts (AlertHandler - SRP)
        self._alert_handler.process_alerts(result, high_lat, loss)
        
        # 4. Update metrics (MetricsHandler - SRP)
        self._metrics_handler.update_metrics(result)
        
        # 5. Periodic maintenance (every N pings)
        self._ping_counter += 1
        if self._ping_counter >= self._memory_check_interval:
            self._ping_counter = 0
            self._check_memory_and_cleanup()
            self._check_instance_notifications()
        
        return result.success, result.latency

    def _check_memory_and_cleanup(self) -> None:
        """Check memory usage, cleanup old data, and shutdown if limit exceeded."""
        from config import ENABLE_MEMORY_MONITORING, MAX_MEMORY_MB
        
        if not ENABLE_MEMORY_MONITORING:
            return
        
        try:
            # Cleanup old data first to free memory
            cleaned = self.stats_repo.cleanup_old_data()
            if cleaned:
                logging.debug(f"Cleaned up old data: {cleaned}")
            
            # Check memory limit
            exceeded, current_mb = self.stats_repo.check_memory_limit()
            if exceeded and current_mb is not None:
                # Memory limit exceeded - trigger graceful shutdown
                msg = t('alert_memory_exceeded_shutdown').format(current=f"{current_mb:.0f}", limit=MAX_MEMORY_MB)
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    f"[X] {msg}",
                    "critical"
                )
                logging.critical(
                    f"Memory limit exceeded: {current_mb:.0f}MB > {MAX_MEMORY_MB}MB. Initiating shutdown."
                )
                # Trigger shutdown
                self.stop_event.set()
        except Exception as exc:
            logging.warning(f"Memory check failed: {exc}")

    def _check_instance_notifications(self) -> None:
        """Check for notifications from other instances trying to start."""
        try:
            from single_instance_notifications import check_instance_notification
            
            notification = check_instance_notification()
            if notification:
                add_visual_alert(
                    self.stats_repo.lock,
                    self.stats_repo.get_stats(),
                    notification,
                    "warning"
                )
                logging.info(f"Instance notification: {notification}")
        except Exception:
            pass  # Silently ignore if notification system fails

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
                    # Trigger immediate hop re-discovery on IP change
                    if ENABLE_HOP_MONITORING:
                        self.hop_monitor_service.request_rediscovery()
                
                # Update stats
                self.stats_repo.update_public_ip(ip, country, code)
                
            except Exception as exc:
                logging.error(f"IP update failed: {exc}")
            
            await asyncio.sleep(IP_CHECK_INTERVAL)

    async def background_dns_monitor(self) -> None:
        """Monitor DNS resolution with multiple record types and benchmark tests."""
        if not ENABLE_DNS_MONITORING:
            return

        while not self.stop_event.is_set():
            try:
                # Run detailed DNS check with configured record types
                results = await self.run_blocking(
                    self.dns_service.check_dns_resolve,
                    None,  # Use default domain
                    DNS_RECORD_TYPES
                )

                # Convert results to dict format for storage
                results_dict = [
                    {
                        "record_type": r.record_type,
                        "success": r.success,
                        "response_time_ms": r.response_time_ms,
                        "status": r.status,
                        "ttl": r.ttl,
                        "records": r.records,
                        "error": r.error,
                    }
                    for r in results
                ]

                self.stats_repo.update_dns_detailed(results_dict)

                # Run benchmark tests (Cached/Uncached/DotCom)
                from config import ENABLE_DNS_BENCHMARK, DNS_BENCHMARK_DOTCOM_DOMAIN, DNS_BENCHMARK_SERVERS
                if ENABLE_DNS_BENCHMARK:
                    benchmark_results = await self.run_blocking(
                        self.dns_service.run_benchmark_tests,
                        DNS_BENCHMARK_DOTCOM_DOMAIN,
                        DNS_BENCHMARK_SERVERS
                    )
                    
                    # Convert benchmark results to dict format
                    benchmark_dict = [
                        {
                            "server": r.server,
                            "test_type": r.test_type,
                            "domain": r.domain,
                            "queries": r.queries,
                            "min_ms": r.min_ms,
                            "avg_ms": r.avg_ms,
                            "max_ms": r.max_ms,
                            "std_dev": r.std_dev,
                            "reliability": r.reliability,
                            "response_time_ms": r.response_time_ms,
                            "success": r.success,
                            "status": r.status,
                            "error": r.error,
                        }
                        for r in benchmark_results
                    ]
                    
                    self.stats_repo.update_dns_benchmark(benchmark_dict)

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
                
                # Update hysteresis counters via repository
                is_issue = status in [t("mtu_low"), t("mtu_fragmented")]
                cons_issues, cons_ok = self.stats_repo.update_mtu_hysteresis(is_issue)
                current = self.stats_repo.get_mtu_status()
                
                # Apply hysteresis
                if is_issue:
                    if cons_issues >= MTU_ISSUE_CONSECUTIVE and current != status:
                        self.stats_repo.update_mtu(local_mtu, path_mtu, status)
                        self.stats_repo.set_mtu_status_change_time()
                        logging.info(f"MTU problem: {status}")
                        if METRICS_AVAILABLE:
                            try:
                                MTU_PROBLEMS_TOTAL.inc()
                                MTU_STATUS_GAUGE.set(1 if status == t("mtu_low") else 2)
                            except Exception:
                                pass
                else:
                    if cons_ok >= MTU_CLEAR_CONSECUTIVE and current != t("mtu_ok"):
                        self.stats_repo.update_mtu(local_mtu, path_mtu, t("mtu_ok"))
                        self.stats_repo.set_mtu_status_change_time()
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
            
            # Use creationflags on Windows to prevent orphan processes
            kwargs: dict[str, Any] = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2,
                encoding=encoding,
                errors="replace",
                **kwargs,
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

        # Set up streaming callback — UI updates as each hop is discovered
        def _on_hop_discovered(snapshot):
            self.stats_repo.update_hop_monitor(snapshot, discovering=True)

        self.hop_monitor_service.set_on_hop_callback(_on_hop_discovered)

        # Initial discovery (streaming — hops appear one by one)
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
                # Check if IP change triggered immediate re-discovery
                need_rediscovery = (
                    self.hop_monitor_service.rediscovery_requested
                    or _time.time() - last_discovery > HOP_REDISCOVER_INTERVAL
                )

                if need_rediscovery:
                    self.hop_monitor_service.clear_rediscovery()
                    self.stats_repo.update_hop_monitor([], discovering=True)
                    await self.run_blocking(
                        self.hop_monitor_service.discover_hops, TARGET_IP
                    )
                    self.stats_repo.update_hop_monitor(
                        self.hop_monitor_service.get_hops_snapshot(), discovering=False
                    )
                    last_discovery = _time.time()
                else:
                    # Ping all hops
                    await self.run_blocking(self.hop_monitor_service.ping_all_hops)
                    self.stats_repo.update_hop_monitor(
                        self.hop_monitor_service.get_hops_snapshot(), discovering=False
                    )

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
                
                # Update hysteresis counters via repository
                is_significant = sig_count >= ROUTE_CHANGE_HOP_DIFF
                cons_changes, cons_ok = self.stats_repo.update_route_hysteresis(is_significant)
                
                # Update route status
                if cons_changes >= ROUTE_CHANGE_CONSECUTIVE:
                    if not self.stats_repo.is_route_changed():
                        self.stats_repo.set_route_changed(True)
                        add_visual_alert(
                            self.stats_repo.lock,
                            self.stats_repo.get_stats(),
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
                        if cons_changes >= ROUTE_SAVE_ON_CHANGE_CONSECUTIVE:
                            self.traceroute_service.trigger_traceroute(TARGET_IP)
                
                elif cons_ok >= ROUTE_CHANGE_CONSECUTIVE:
                    if self.stats_repo.is_route_changed():
                        self.stats_repo.set_route_changed(False)
                        add_visual_alert(
                            self.stats_repo.lock,
                            self.stats_repo.get_stats(),
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
                    self.stats_repo.is_route_changed(),
                    sig_count
                )
                
                # Alert on problematic hop
                if analysis["problematic_hop"]:
                    add_visual_alert(
                        self.stats_repo.lock,
                        self.stats_repo.get_stats(),
                        f"[!] {t('problematic_hop')}: {analysis['problematic_hop']}",
                        "warning"
                    )
                
            except Exception as exc:
                logging.error(f"Route analysis failed: {exc}")
            
            await asyncio.sleep(ROUTE_ANALYSIS_INTERVAL)

    async def background_version_checker(self) -> None:
        """Check for updates periodically."""
        if not ENABLE_VERSION_CHECK:
            return
        
        while not self.stop_event.is_set():
            try:
                from services.version_service import check_update_available
                update_available, current, latest = check_update_available()
                
                if latest:
                    if update_available:
                        # Update version info only if new version available
                        self.stats_repo.set_latest_version(latest, False)
                        logging.info(f"Update available: {current} → {latest}")
                        # Add visual alert for new version
                        add_visual_alert(
                            self.stats_repo.lock,
                            self.stats_repo.get_stats(),
                            f"[i] {t('update_available').format(current=current, latest=latest)}",
                            "info"
                        )
                    else:
                        # Version is current - clear any previous version info
                        self.stats_repo.set_latest_version(None, True)
                        logging.debug(f"Version check: current version {current} is up to date")
                else:
                    logging.debug("Version check: unable to fetch latest version")
                    
            except Exception as exc:
                logging.error(f"Version check failed: {exc}")
            
            await asyncio.sleep(VERSION_CHECK_INTERVAL)

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

    def _check_packet_loss_threshold(self, loss30: float, snap: StatsSnapshot) -> None:
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

    def _check_avg_latency_threshold(self, snap: StatsSnapshot) -> None:
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

    def _check_connection_lost_threshold(self, snap: StatsSnapshot) -> None:
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

    def _check_jitter_threshold(self, snap: StatsSnapshot) -> None:
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
