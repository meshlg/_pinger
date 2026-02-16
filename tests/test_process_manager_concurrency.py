import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.process_manager import ProcessManager

class TestProcessManagerConcurrency(unittest.IsolatedAsyncioTestCase):
    async def test_concurrency_limit(self):
        # Create manager with limit of 2
        pm = ProcessManager(max_concurrent=2)
        
        # Mock subprocess
        async def mock_create(*args, **kwargs):
            proc = MagicMock()
            proc.returncode = None
            return proc
            
        with patch('asyncio.create_subprocess_exec', side_effect=mock_create):
            # Start 2 processes (should succeed)
            p1 = await pm.create_process("echo", "1")
            p2 = await pm.create_process("echo", "2")
            
            # Start 3rd process (should block)
            # We'll use a timeout to verify it blocks
            try:
                await asyncio.wait_for(pm.create_process("echo", "3"), timeout=0.1)
                self.fail("Should have blocked")
            except asyncio.TimeoutError:
                pass # Expected behavior
            
            # Unregister one process
            await pm.unregister(p1)
            
            # Now 3rd process should succeed
            p3 = await asyncio.wait_for(pm.create_process("echo", "3"), timeout=1.0)
            self.assertIsNotNone(p3)
            
            # Cleanup
            await pm.unregister(p2)
            await pm.unregister(p3)

    async def test_unregister_idempotency(self):
        pm = ProcessManager(max_concurrent=1)
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_exec.return_value = MagicMock()
            p1 = await pm.create_process("echo")
            
            # Unregister once
            await pm.unregister(p1)
            
            # Unregister twice (should not raise error or release semaphore again)
            # If it released again, we could start 2 processes when limit is 1
            await pm.unregister(p1) 
            
            p2 = await pm.create_process("echo")
            
            # Should block if semaphore was released too many times? 
            # No, if it WAS released too many times, we could start p3.
            # But duplicate release on Semaphore raises ValueError in Python 3.10+? 
            # Or just increments counter beyond init value? 
            # asyncio.Semaphore does NOT have an upper bound limit unless BoundedSemaphore is used.
            # ProcessManager uses Semaphore. We rely on logic "if process in self._active_processes"
            # so duplicate unregister should NOT release semaphore.
            
            # Try to start p3 (should block because p2 is running)
            try:
                await asyncio.wait_for(pm.create_process("echo"), timeout=0.1)
                self.fail("Should have blocked")
            except asyncio.TimeoutError:
                pass

if __name__ == "__main__":
    unittest.main()
