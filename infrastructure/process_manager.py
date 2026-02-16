import asyncio
import logging
from typing import Set, Tuple, List, Optional
import sys

class ProcessManager:
    """
    Centralized manager for child processes to ensure proper cleanup.
    """
    def __init__(self, max_concurrent: int = 50) -> None:
        self._active_processes: Set[asyncio.subprocess.Process] = set()
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def create_process(self, *args, **kwargs) -> asyncio.subprocess.Process:
        """
        Create a subprocess and register it for cleanup.
        Wraps asyncio.create_subprocess_exec.
        Blocks if concurrency limit is reached.
        """
        # Acquire semaphore before creating process
        await self._semaphore.acquire()
        
        try:
            process = await asyncio.create_subprocess_exec(*args, **kwargs)
        except Exception:
            self._semaphore.release()
            raise

        async with self._lock:
            self._active_processes.add(process)
        return process

    async def unregister(self, process: asyncio.subprocess.Process) -> None:
        """Unregister a process that has completed and release semaphore."""
        async with self._lock:
            if process in self._active_processes:
                self._active_processes.discard(process)
                self._semaphore.release()

    async def run_command(
        self, 
        cmd: List[str], 
        timeout: float | None = None, 
        encoding: str | None = None,
        errors: str = 'strict',
        **kwargs
    ) -> Tuple[str | bytes, str | bytes, int]:
        """
        Run a command asynchronously and return (stdout, stderr, returncode).
        
        Args:
            cmd: Command and arguments list
            timeout: Timeout in seconds
            encoding: If set, decode stdout/stderr using this encoding. If None, return bytes.
            errors: Error handling for decoding
            **kwargs: Additional arguments passed to create_subprocess_exec
        
        Returns:
            Tuple of (stdout, stderr, returncode)
        
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        if 'stdout' not in kwargs:
            kwargs['stdout'] = asyncio.subprocess.PIPE
        if 'stderr' not in kwargs:
            kwargs['stderr'] = asyncio.subprocess.PIPE

        process = await self.create_process(*cmd, **kwargs)

        try:
            if timeout:
                stdout_data, stderr_data = await asyncio.wait_for(process.communicate(), timeout=timeout)
            else:
                stdout_data, stderr_data = await process.communicate()
            
            returncode = process.returncode if process.returncode is not None else -1
            
            if encoding:
                stdout_str = stdout_data.decode(encoding, errors=errors) if stdout_data else ""
                stderr_str = stderr_data.decode(encoding, errors=errors) if stderr_data else ""
                return stdout_str, stderr_str, returncode
            
            return stdout_data, stderr_data, returncode

        except asyncio.TimeoutError:
            logging.warning(f"Command timed out: {' '.join(cmd)}")
            try:
                process.kill()
            except Exception:
                pass
            # Wait for the process to terminate to avoid zombies
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except Exception:
                logging.error(f"Failed to reap timed-out process: {process.pid}")
            raise
        finally:
            await self.unregister(process)

    async def cleanup(self) -> None:
        """Terminate all tracked processes."""
        async with self._lock:
            if not self._active_processes:
                return
            
            count = len(self._active_processes)
            logging.info(f"Cleaning up {count} active subprocesses...")
            processes = list(self._active_processes)
            self._active_processes.clear()

        for proc in processes:
            try:
                if proc.returncode is None:
                    proc.terminate()
            except Exception as e:
                logging.warning(f"Failed to terminate process {proc.pid}: {e}")

        # Give them a chance to terminate gracefully
        await asyncio.sleep(0.1)

        for proc in processes:
            try:
                if proc.returncode is None:
                    logging.warning(f"Process {proc.pid} did not terminate, killing...")
                    proc.kill()
            except Exception as e:
                logging.warning(f"Failed to kill process {proc.pid}: {e}")

    def cleanup_sync(self) -> None:
        """
        Synchronously terminate all tracked processes.
        Use this for atexit or signal handlers where async execution is not possible.
        """
        # We can't use the lock here.
        processes = list(self._active_processes)
        
        if processes:
            logging.info(f"Sync cleanup: terminating {len(processes)} active subprocesses...")
        
        for proc in processes:
            try:
                # Iterate and kill
                if proc.returncode is None:
                    try:
                        proc.terminate()
                    except Exception:
                        # Fallback to os.kill if terminate fails or loop is closed
                        try:
                            import os
                            import signal
                            os.kill(proc.pid, signal.SIGTERM)
                        except Exception:
                            pass
            except Exception as e:
                logging.warning(f"Failed to sync terminate process {proc.pid}: {e}")

# Global instance
_global_manager = ProcessManager()

def get_process_manager() -> ProcessManager:
    return _global_manager
