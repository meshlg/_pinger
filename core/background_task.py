"""
Abstract base class for background monitoring tasks.

Provides the shared while/try/sleep loop pattern, eliminating duplication
across all 8 background monitors.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from stats_repository import StatsRepository


class BackgroundTask(ABC):
    """Base class for all background monitoring tasks.

    Subclasses implement ``execute()`` with their single-iteration logic.
    The shared ``run()`` method handles the while/sleep/error loop.
    """

    def __init__(
        self,
        *,
        name: str,
        interval: float,
        enabled: bool,
        stats_repo: StatsRepository,
        stop_event: asyncio.Event,
        executor: ThreadPoolExecutor,
    ) -> None:
        self.name = name
        self.interval = interval
        self.enabled = enabled
        self.stats_repo = stats_repo
        self.stop_event = stop_event
        self.executor = executor

    # ── helpers available to subclasses ──────────────────────────────────

    async def run_blocking(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run a blocking function in the thread-pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: func(*args, **kwargs),
        )

    # ── lifecycle ────────────────────────────────────────────────────────

    @abstractmethod
    async def execute(self) -> None:
        """Single iteration of the task — implemented by subclasses."""

    async def setup(self) -> None:
        """Optional one-time setup before the loop starts.

        Override in subclasses that need initialization (e.g. hop discovery).
        """

    async def run(self) -> None:
        """Main loop: setup → (execute → sleep) until stopped."""
        if not self.enabled:
            return

        await self.setup()

        while not self.stop_event.is_set():
            try:
                await self.execute()
            except Exception as exc:
                logging.error(f"{self.name} failed: {exc}")
            await asyncio.sleep(self.interval)
