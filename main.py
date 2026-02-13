from __future__ import annotations

import atexit
import os
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
        self._shutdown_called = False

    def _install_signal_handlers(self) -> None:
        def handler(sig: int, frame: Any) -> None:
            self.console.print(f"\n[bold red]{t('stop')}[/bold red]")
            snap = self.monitor.get_stats_snapshot()
            if snap["start_time"]:
                uptime_txt = self.ui._fmt_uptime(snap["start_time"])
                self.console.print(f"[dim]{t('uptime_label')}: {uptime_txt}[/dim]")
            # Signal the event loop to stop — let the finally block handle cleanup
            self.monitor.stop_event.set()

        signal.signal(signal.SIGINT, handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handler)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, handler)  # type: ignore[attr-defined]

        # Windows: catch console close (X button) and logoff events
        if sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

                @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)  # type: ignore[misc]
                def console_ctrl_handler(event: int) -> bool:
                    # CTRL_CLOSE_EVENT=2, CTRL_LOGOFF_EVENT=5, CTRL_SHUTDOWN_EVENT=6
                    if event in (2, 5, 6):
                        self._force_shutdown()
                        return True
                    return False

                kernel32.SetConsoleCtrlHandler(console_ctrl_handler, True)
            except Exception as exc:
                logging.debug(f"Could not set Windows console handler: {exc}")

    def _force_shutdown(self) -> None:
        """Force shutdown — kill all children and exit gracefully."""
        if self._shutdown_called:
            return
        self._shutdown_called = True
        
        # Flush logging handlers before shutdown
        for handler in logging.root.handlers:
            try:
                handler.flush()
            except Exception:
                pass
        
        try:
            self.monitor.shutdown()
        except Exception as exc:
            logging.warning(f"Error during forced shutdown: {exc}")
        
        # Use sys.exit() instead of os._exit() to allow atexit handlers to run
        # This ensures lock files are released and buffers are flushed
        logging.info("Forced shutdown complete, exiting gracefully")
        sys.exit(0)

    async def run(self) -> None:
        self._install_signal_handlers()

        # Register atexit as safety net
        atexit.register(self._atexit_cleanup)

        self.console.print(
            f"\n[bold green]>>> {t('start').format(target=TARGET_IP)} <<<[/bold green]"
        )
        self.console.print(f"[dim]{t('press')}[/dim]\n")
        self.monitor.stats_repo.set_start_time(datetime.now())

        tasks = self.monitor.start_tasks()

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
            await self.monitor.stop_tasks()
            self.monitor.shutdown()
            self.console.print(f"[dim]{t('bg_stopped')}[/dim]")

    def _atexit_cleanup(self) -> None:
        """Safety net: ensure shutdown is called on process exit."""
        if self._shutdown_called:
            return
        self._shutdown_called = True
        try:
            self.monitor.stop_event.set()
            self.monitor.shutdown()
        except Exception:
            pass


def main() -> None:
    asyncio.run(run_async_main())


async def run_async_main() -> None:
    app = PingerApp()
    await app.run()


__all__ = ["main", "run_async_main"]
