"""
Ping handler - executes ping and returns results.

Single Responsibility: Execute ping operation and return structured result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services import PingService


@dataclass
class PingResult:
    """Result of a ping operation."""
    success: bool
    latency: float | None
    target: str
    
    @property
    def is_timeout(self) -> bool:
        """Check if ping timed out (no latency)."""
        return not self.success and self.latency is None


class PingHandler:
    """
    Handles ping execution.
    
    Single Responsibility: Execute ping and return structured result.
    """
    
    def __init__(self, ping_service: PingService, target_ip: str) -> None:
        self.ping_service = ping_service
        self.target_ip = target_ip
    
    def execute(self) -> PingResult:
        """Execute ping and return result."""
        success, latency = self.ping_service.ping_host(self.target_ip)
        return PingResult(
            success=success,
            latency=latency,
            target=self.target_ip,
        )
    
    async def execute_async(self, executor) -> PingResult:
        """Execute ping in thread pool (for async contexts)."""
        import asyncio
        loop = asyncio.get_running_loop()
        success, latency = await loop.run_in_executor(
            executor,
            self.ping_service.ping_host,
            self.target_ip,
        )
        return PingResult(
            success=success,
            latency=latency,
            target=self.target_ip,
        )
