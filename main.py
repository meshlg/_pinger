from __future__ import annotations

import atexit
import os
import sys
import asyncio
import logging
import signal
from datetime import datetime, timezone
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
        """Force shutdown — signal event loop to stop and allow graceful exit."""
        if self._shutdown_called:
            return
        self._shutdown_called = True
        
        logging.info("Initiating graceful shutdown from console event...")
        self.monitor.stop_event.set()
        
        # Flush logging handlers
        for handler in logging.root.handlers:
            try:
                handler.flush()
            except Exception:
                pass
        
        # We don't call sys.exit(0) or self.monitor.shutdown() here. 
        # By setting stop_event, the main loop's `finally` block will handle 
        # graceful cleanup (awaiting tasks, closing servers etc).

    async def run(self) -> None:
        self._install_signal_handlers()

        # Register atexit as safety net
        atexit.register(self._atexit_cleanup)

        self.console.print(
            f"\n[bold green]>>> {t('start').format(target=TARGET_IP)} <<<[/bold green]"
        )
        self.console.print(f"[dim]{t('press')}[/dim]\n")
        self.monitor.stats_repo.set_start_time(datetime.now(timezone.utc))

        # Security check: Warn if running as root/admin
        try:
            is_admin = False
            if sys.platform == "win32":
                import ctypes
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                is_admin = os.geteuid() == 0

            if is_admin:
                self.console.print(
                    "\n[bold red on yellow] WARN [/bold red on yellow] [yellow]Running as root/admin is NOT recommended since v2.5.0[/yellow]"
                )
                self.console.print(
                    "[yellow]System commands do not require privileges. Please run as normal user to minimize security risks.[/yellow]\n"
                )
                logging.warning("Security: Application detected running with elevated privileges (root/admin). Not recommended.")
        except Exception as e:
            logging.debug(f"Failed to check privileges: {e}")

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
