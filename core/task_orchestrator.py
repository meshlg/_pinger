"""
Task orchestrator — registry for background monitoring tasks.

Provides register/start_all/stop_all lifecycle management.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.background_task import BackgroundTask


class TaskOrchestrator:
    """Manages registration and lifecycle of background tasks."""

    def __init__(self) -> None:
        self._tasks: list[BackgroundTask] = []
        self._running: list[asyncio.Task] = []

    def register(self, task: BackgroundTask) -> None:
        """Register a background task."""
        self._tasks.append(task)

    def register_all(self, tasks: list[BackgroundTask]) -> None:
        """Register multiple tasks at once."""
        self._tasks.extend(tasks)

    @property
    def registered_names(self) -> list[str]:
        """Names of all registered tasks."""
        return [t.name for t in self._tasks]

    def start_all(self) -> list[asyncio.Task]:
        """Create asyncio.Tasks for all registered background tasks.

        Returns list of asyncio.Task objects for external tracking.
        """
        self._running = [
            asyncio.create_task(task.run(), name=task.name)
            for task in self._tasks
        ]
        enabled = [t.name for t in self._tasks if t.enabled]
        logging.info(f"Started {len(enabled)} background tasks: {', '.join(enabled)}")
        return list(self._running)

    async def stop_all(self, timeout: float = 5.0) -> None:
        """Cancel all running tasks and wait for completion."""
        for task in self._running:
            if not task.done():
                task.cancel()

        if self._running:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._running, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logging.warning("Some background tasks did not terminate in time")

        self._running.clear()
