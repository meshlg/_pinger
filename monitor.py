from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from config import (
    ALERT_ON_HIGH_LATENCY,
    ALERT_ON_PACKET_LOSS,
    AVG_LATENCY_THRESHOLD,
    CONSECUTIVE_LOSS_THRESHOLD,
    ENABLE_AUTO_TRACEROUTE,
    ENABLE_HEALTH_ENDPOINT,
    ENABLE_IP_CHANGE_ALERT,
    ENABLE_METRICS,
    ENABLE_THRESHOLD_ALERTS,
    HEALTH_ADDR,
    HEALTH_PORT,
    HIGH_LATENCY_THRESHOLD,
    JITTER_THRESHOLD,
    MAX_WORKER_THREADS,
    METRICS_ADDR,
    METRICS_PORT,
    PACKET_LOSS_THRESHOLD,
    SHUTDOWN_TIMEOUT_SECONDS,
    TARGET_IP,
    TRACEROUTE_TRIGGER_LOSSES,
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
    # Memory monitoring
    ENABLE_MEMORY_MONITORING,
    MAX_MEMORY_MB,
    t,
)

# Core handlers (refactored from ping_once)
from core import PingHandler, AlertHandler, MetricsHandler
from core.task_orchestrator import TaskOrchestrator
from core.ip_updater_task import IPUpdaterTask
from core.dns_monitor_task import DNSMonitorTask
from core.mtu_monitor_task import MTUMonitorTask
from core.ttl_monitor_task import TTLMonitorTask
from core.problem_analyzer_task import ProblemAnalyzerTask
from core.hop_monitor_task import HopMonitorTask
from core.route_analyzer_task import RouteAnalyzerTask
from core.version_checker_task import VersionCheckerTask

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
from infrastructure import (
    METRICS_AVAILABLE,
    start_metrics_server,
    HealthServer,
    start_health_server,
    get_process_manager,
)


class Monitor:
    """
    Main monitoring orchestrator.
    
    Uses service layer for operations and StatsRepository for data.
    Uses core handlers for ping cycle operations (SRP-compliant).
    Background monitoring is delegated to BackgroundTask subclasses
    managed by a TaskOrchestrator.
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
        self._subprocess_lock = threading.Lock()
        
        # Memory monitoring counter (check every N pings)
        self._ping_counter = 0
        self._memory_check_interval = 10
        self._ping_lock = threading.Lock()
        
        # Data repository
        self.stats_repo = StatsRepository()
        
        # Process Manager
        self.process_manager = get_process_manager()
        
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
        # Enable geolocation for hop monitoring (requires requests library)
        self.hop_monitor_service.enable_geo()
        
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
        
        # ── Background Task Orchestrator ────────────────────────────────
        self._orchestrator = TaskOrchestrator()
        common = dict(
            stats_repo=self.stats_repo,
            stop_event=self.stop_event,
            executor=self.executor,
        )
        self._orchestrator.register_all([
            IPUpdaterTask(
                ip_service=self.ip_service,
                hop_monitor_service=self.hop_monitor_service,
                **common,
            ),
            DNSMonitorTask(dns_service=self.dns_service, **common),
            MTUMonitorTask(mtu_service=self.mtu_service, **common),
            TTLMonitorTask(ping_service=self.ping_service, **common),
            ProblemAnalyzerTask(problem_analyzer=self.problem_analyzer, **common),
            HopMonitorTask(hop_monitor_service=self.hop_monitor_service, **common),
            RouteAnalyzerTask(
                route_analyzer=self.route_analyzer,
                traceroute_service=self.traceroute_service,
                **common,
            ),
            VersionCheckerTask(**common),
        ])

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


    def shutdown(self) -> None:
        """Shutdown the monitor gracefully with timeout and force kill fallback."""
        logging.info("Monitor shutdown initiated...")
        
        # Signal all background tasks to stop
        self.stop_event.set()
        
        # Kill all tracked child subprocesses FIRST
        self._kill_all_subprocesses()
        
        # Kill any async processes managed by ProcessManager
        try:
            self.process_manager.cleanup_sync()
        except Exception:
            pass
        
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
        
        # Check for hanging threads and warn, but allow graceful exit
        import threading as _threading
        alive = [t for t in _threading.enumerate()
                 if t.is_alive() and not t.daemon and t != _threading.main_thread()]
        if alive:
            thread_names = [t.name for t in alive]
            logging.warning(
                f"Shutdown complete with {len(alive)} non-daemon threads still alive: {thread_names}. "
                f"Attempting to join them..."
            )
            # Flush all logging handlers before exit
            for handler in logging.root.handlers:
                try:
                    handler.flush()
                except Exception:
                    pass
            
            # Attempt to join remaining threads with a short timeout
            for t in alive:
                t.join(timeout=1.0)
                if t.is_alive():
                    logging.error(f"Thread {t.name} did not terminate.")

    async def run_blocking(self, func, *args, **kwargs) -> Any:
        """Run blocking function in executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: func(*args, **kwargs)
        )

    # ==================== Task Orchestrator ====================

    def start_tasks(self) -> list[asyncio.Task]:
        """Start all registered background tasks via the orchestrator."""
        return self._orchestrator.start_all()

    async def stop_tasks(self, timeout: float | None = None) -> None:
        """Stop all background tasks."""
        await self._orchestrator.stop_all(timeout or SHUTDOWN_TIMEOUT_SECONDS)

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
        
        # 5. Clean up old visual alerts
        self.cleanup_alerts()
        
        # 6. Periodic maintenance (every N pings)
        with self._ping_lock:
            self._ping_counter += 1
            if self._ping_counter >= self._memory_check_interval:
                self._ping_counter = 0
                self._check_memory_and_cleanup()
                self._check_instance_notifications()
        
        return result.success, result.latency

    def _check_memory_and_cleanup(self) -> None:
        """Check memory usage, cleanup old data, and shutdown if limit exceeded."""
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
                self.stats_repo.add_alert(f"[X] {msg}", "critical")
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
                self.stats_repo.add_alert(notification, "warning")
                logging.info(f"Instance notification: {notification}")
        except Exception:
            pass  # Silently ignore if notification system fails

    def cleanup_alerts(self) -> None:
        """Clean old visual alerts."""
        self.stats_repo.clean_old_alerts()

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
                self.stats_repo.add_alert(f"[!] {t('alert_high_loss').format(val=loss30)}", "warning")
                logging.warning(f"Loss30 exceeded: {loss30:.1f}%")
                self.stats_repo.trigger_alert_sound("loss")
        else:
            if was_high:
                self.stats_repo.update_threshold_state("high_packet_loss", False)
                self.stats_repo.add_alert(f"[+] {t('alert_loss_normalized')}", "info")

    def _check_avg_latency_threshold(self, snap: StatsSnapshot) -> None:
        """Check average latency threshold."""
        success = snap["success"]
        avg = (snap["total_latency_sum"] / success) if success else 0.0
        was_high = self.stats_repo.get_threshold_state("high_avg_latency")
        
        if avg > AVG_LATENCY_THRESHOLD:
            if not was_high:
                self.stats_repo.update_threshold_state("high_avg_latency", True)
                self.stats_repo.add_alert(f"[!] {t('alert_high_avg_latency').format(val=avg)}", "warning")
                logging.warning(f"Avg latency exceeded: {avg:.1f}ms")
        else:
            if was_high:
                self.stats_repo.update_threshold_state("high_avg_latency", False)
                self.stats_repo.add_alert(f"[+] {t('alert_latency_normalized')}", "info")

    def _check_connection_lost_threshold(self, snap: StatsSnapshot) -> None:
        """Check consecutive losses threshold."""
        cons_losses = snap["consecutive_losses"]
        was_lost = self.stats_repo.get_threshold_state("connection_lost")
        
        if cons_losses >= CONSECUTIVE_LOSS_THRESHOLD:
            if not was_lost:
                self.stats_repo.update_threshold_state("connection_lost", True)
                self.stats_repo.add_alert(f"[X] {t('alert_connection_lost').format(n=cons_losses)}", "critical")
                logging.critical(f"Connection lost: {cons_losses} consecutive")
                self.stats_repo.trigger_alert_sound("lost")
        else:
            if was_lost:
                self.stats_repo.update_threshold_state("connection_lost", False)
                self.stats_repo.add_alert(f"[+] {t('alert_connection_restored')}", "success")
                logging.info("Connection restored")

    def _check_jitter_threshold(self, snap: StatsSnapshot) -> None:
        """Check jitter threshold."""
        jitter = snap["jitter"]
        was_high = self.stats_repo.get_threshold_state("high_jitter")
        
        if jitter > JITTER_THRESHOLD:
            if not was_high:
                self.stats_repo.update_threshold_state("high_jitter", True)
                self.stats_repo.add_alert(f"[!] {t('alert_high_jitter').format(val=jitter)}", "warning")
                logging.warning(f"Jitter exceeded: {jitter:.1f}ms")
        else:
            if was_high:
                self.stats_repo.update_threshold_state("high_jitter", False)
                self.stats_repo.add_alert(f"[+] {t('alert_jitter_normalized')}", "info")
