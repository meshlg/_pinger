from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from typing import Optional


class MTUService:
    """Service for MTU monitoring and path MTU discovery."""

    def __init__(self) -> None:
        self._last_local_mtu: Optional[int] = None
        self._last_path_mtu: Optional[int] = None

    def get_local_mtu(self) -> int | None:
        """Get MTU of the primary network interface."""
        try:
            if sys.platform == "win32":
                return self._get_windows_mtu()
            else:
                return self._get_linux_mtu()
        except subprocess.TimeoutExpired:
            logging.warning("Timeout getting local MTU")
        except Exception as exc:
            logging.error(f"Failed to get local MTU: {exc}")
        return None

    def _get_windows_mtu(self) -> int | None:
        """Get MTU on Windows using netsh."""
        if not shutil.which("netsh"):
            logging.warning("Command 'netsh' not found, cannot get local MTU")
            return None
        
        result = subprocess.run(
            ["netsh", "interface", "ipv4", "show", "subinterface"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="oem",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        )
        for line in result.stdout.split("\n"):
            line = line.strip()
            if not line or line.startswith("-"):
                continue
            parts = line.split()
            if len(parts) >= 1:
                try:
                    mtu = int(parts[0])
                    if 500 <= mtu <= 9000:
                        return mtu
                except (ValueError, IndexError):
                    continue
        return None

    def _get_linux_mtu(self) -> int | None:
        """Get MTU on Linux using ip command."""
        import re
        
        if not shutil.which("ip"):
            logging.warning("Command 'ip' not found, cannot get local MTU")
            return None
        
        result = subprocess.run(
            ["ip", "link", "show"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.split("\n"):
            if mtu_match := re.search(r"mtu\s+(\d+)", line):
                return int(mtu_match.group(1))
        return None

    def discover_path_mtu(self, target: str, is_ipv6: bool = False) -> int | None:
        """Discover Path MTU using ping with varying packet sizes."""
        import re
        
        try:
            ping_cmd = shutil.which("ping")
            if not ping_cmd:
                logging.warning("Cannot discover Path MTU: ping command not available")
                return None

            low, high = 500, 1500

            while low <= high:
                mid = (low + high) // 2

                if sys.platform == "win32":
                    cmd = [ping_cmd, "-n", "1", "-f", "-l", str(mid), target]
                    encoding = "oem"
                else:
                    if is_ipv6:
                        cmd = [ping_cmd, "-6", "-c", "1", "-M", "do", "-s", str(mid), target]
                    else:
                        cmd = [ping_cmd, "-c", "1", "-M", "do", "-s", str(mid), target]
                    encoding = "utf-8"

                try:
                    # Use creationflags on Windows to prevent orphan processes
                    kwargs = {}
                    if sys.platform == "win32":
                        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        encoding=encoding,
                        errors="replace",
                        **kwargs,
                    )
                except subprocess.TimeoutExpired:
                    # Timeout means packet was too large
                    high = mid - 1
                    continue

                if result.returncode == 0:
                    low = mid + 1
                else:
                    high = mid - 1

            return high if high >= 500 else None
        except Exception as exc:
            logging.error(f"Path MTU discovery failed: {exc}")
        return None

    def check_mtu(self, target: str, is_ipv6: bool = False) -> dict:
        """Check local and path MTU, return status info."""
        local_mtu = self.get_local_mtu()
        path_mtu = self.discover_path_mtu(target, is_ipv6) if local_mtu else None
        
        return {
            "local_mtu": local_mtu,
            "path_mtu": path_mtu,
        }
