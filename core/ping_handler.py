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
    
    # Removed synchronous execute() to enforce async usage.

    
    async def execute_async(self, executor) -> PingResult:
        """Execute ping asynchronously."""
        # Use new async method directly
        success, latency = await self.ping_service.ping_host_async(self.target_ip)
        
        return PingResult(
            success=success,
            latency=latency,
            target=self.target_ip,
        )
