from __future__ import annotations

import sys
import asyncio
import logging
import signal
from datetime import datetime
from typing import Any, TYPE_CHECKING

from rich.console import Console
from rich.live import Live

if TYPE_CHECKING:
    from .monitor import Monitor
    from .ui import MonitorUI

try:  # pragma: no cover - fallback when run outside package context
    from .config import INTERVAL, TARGET_IP, t, SHUTDOWN_TIMEOUT_SECONDS
    from .monitor import Monitor
    from .ui import MonitorUI
except ImportError:  # pragma: no cover
    from config import INTERVAL, TARGET_IP, t, SHUTDOWN_TIMEOUT_SECONDS
    from monitor import Monitor
    from ui import MonitorUI


class PingerApp:
    def __init__(self) -> None:
        self.console = Console()
        self.monitor: Monitor = Monitor()
        self.ui: MonitorUI = MonitorUI(self.console, self.monitor)

    def _install_signal_handlers(self) -> None:
        def handler(sig: int, frame: Any) -> None:
            self.console.print(f"\n[bold red]{t('stop')}[/bold red]")
            snap = self.monitor.get_stats_snapshot()
            if snap["start_time"]:
                uptime_txt = self.ui._fmt_uptime(snap["start_time"])
                self.console.print(f"[dim]{t('uptime_label')}: {uptime_txt}[/dim]")
            self.monitor.stop_event.set()
            # Graceful shutdown
            self.monitor.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handler)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, handler)  # Terminal closed (x button)  # type: ignore[attr-defined]

    async def run(self) -> None:
        self._install_signal_handlers()
        self.console.print(
            f"\n[bold green]>>> {t('start').format(target=TARGET_IP)} <<<[/bold green]"  # TARGET_IP from config (env-overridable)
        )
        self.console.print(f"[dim]{t('press')}[/dim]\n")
        self.monitor.stats_repo.set_start_time(datetime.now())

        tasks = [
            asyncio.create_task(self.monitor.background_ip_updater()),
            asyncio.create_task(self.monitor.background_dns_monitor()),
            asyncio.create_task(self.monitor.background_mtu_monitor()),
            asyncio.create_task(self.monitor.background_ttl_monitor()),
            asyncio.create_task(self.monitor.background_problem_analyzer()),
            asyncio.create_task(self.monitor.background_route_analyzer()),
            asyncio.create_task(self.monitor.background_hop_monitor()),
            asyncio.create_task(self.monitor.background_version_checker()),
        ]

        try:
            with Live(
                self.ui.generate_layout(),
                refresh_per_second=1,
                screen=True,
                transient=False,
            ) as live:
                while not self.monitor.stop_event.is_set():
                    await self.monitor.ping_once()
                    self.monitor.check_thresholds()
                    live.update(self.ui.generate_layout())
                    await asyncio.sleep(INTERVAL)
        except Exception as exc:  # pragma: no cover - runtime logging
            logging.error(f"Main loop error: {exc}")
        finally:
            self.monitor.stop_event.set()
            
            # Cancel all background tasks with timeout
            for task in tasks:
                task.cancel()
            
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=SHUTDOWN_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                logging.warning("Some background tasks did not terminate in time")
            
            self.monitor.shutdown()
            self.console.print(f"[dim]{t('bg_stopped')}[/dim]")


def main() -> None:
    asyncio.run(run_async_main())


async def run_async_main() -> None:
    app = PingerApp()
    await app.run()


__all__ = ["main", "run_async_main"]
