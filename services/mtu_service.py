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

    def get_local_mtu(self, target: str = "8.8.8.8") -> int | None:
        """Get MTU of the network interface used to reach target."""
        try:
            if sys.platform == "win32":
                return self._get_windows_mtu(target)
            else:
                return self._get_linux_mtu()
        except subprocess.TimeoutExpired:
            logging.warning("Timeout getting local MTU")
        except Exception as exc:
            logging.error(f"Failed to get local MTU: {exc}")
        return None

    def _get_windows_mtu(self, target: str) -> int | None:
        """Get MTU on Windows using PowerShell (active route) or netsh (fallback)."""
        # Try PowerShell first to get MTU of the specific interface used for target
        mtu = self._get_windows_mtu_powershell(target)
        if mtu:
            return mtu
            
        # Fallback to netsh (legacy behavior)
        return self._get_windows_mtu_netsh()

    def _get_windows_mtu_powershell(self, target: str) -> int | None:
        """Get MTU of the interface used for target via PowerShell."""
        if not shutil.which("powershell"):
            return None

        # Command to get MTU of the interface routing to target
        # Find-NetRoute -RemoteIPAddress "TARGET" | Select -First 1 | Get-NetIPInterface | Select -ExpandProperty NlMtu
        # Note: Find-NetRoute is available on Windows 8.1+ / Server 2012 R2+
        ps_cmd = (
            f'Find-NetRoute -RemoteIPAddress "{target}" | '
            'Select-Object -First 1 | '
            'Get-NetIPInterface | '
            'Select-Object -ExpandProperty NlMtu'
        )
        
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    mtu = int(result.stdout.strip())
                    if 500 <= mtu <= 9000:
                        return mtu
                except ValueError:
                    pass
        except Exception as exc:
            logging.debug(f"PowerShell MTU check failed: {exc}")
            
        return None

    def _get_windows_mtu_netsh(self) -> int | None:
        """Get MTU on Windows using netsh (fallback)."""
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

    def discover_path_mtu(self, target: str, is_ipv6: bool = False, limit: int = 1500) -> int | None:
        """Discover Path MTU using ping with varying packet sizes.
        
        Args:
            target: Target IP address
            is_ipv6: Whether to use IPv6
            limit: Upper bound for MTU search (usually local MTU)
        """
        import re
        
        try:
            ping_cmd = shutil.which("ping")
            if not ping_cmd:
                logging.warning("Cannot discover Path MTU: ping command not available")
                return None

            # Define overhead constants
            # IPv4: 20 bytes IP  + 8 bytes ICMP = 28 bytes
            # IPv6: 40 bytes IP  + 8 bytes ICMP = 48 bytes
            HEADER_OVERHEAD = 48 if is_ipv6 else 28

            low = 500
            high = limit

            # Helper to calculate payload size from desired total MTU
            def get_payload_size(total_mtu: int) -> int:
                return total_mtu - HEADER_OVERHEAD

            # Adjust high limit if we passed a target greater than 1500 (e.g. from local MTU)
            # Currently discover_path_mtu interface only takes target, but maybe we should
            # allow upper bound? For now, keep 1500 but logic is prepared.
            
            # Binary search for largest working payload
            # We search for payload size, but return total MTU
            
            # Start binary search
            search_low = get_payload_size(low)
            search_high = get_payload_size(high)

            while search_low <= search_high:
                mid = (search_low + search_high) // 2

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
                    # Timeout means packet was too large or lost
                    search_high = mid - 1
                    continue

                if result.returncode == 0:
                    search_low = mid + 1
                else:
                    search_high = mid - 1

            # The largest working payload is search_high
            # Total MTU = payload + overhead
            final_mtu = search_high + HEADER_OVERHEAD
            
            return final_mtu if final_mtu >= 500 else None
        except Exception as exc:
            logging.error(f"Path MTU discovery failed: {exc}")
        return None

    def check_mtu(self, target: str, is_ipv6: bool = False, discover_path: bool = True) -> dict:
        """Check local and path MTU, return status info.
        
        Args:
            target: Target IP address
            is_ipv6: Whether to use IPv6
            discover_path: If True, perform path MTU discovery (expensive).
                           If False, returns None for path_mtu.
        """
        local_mtu = self.get_local_mtu(target)
        path_mtu = None
        
        if discover_path and local_mtu:
            # Use local MTU as the search limit to support Jumbo Frames
            path_mtu = self.discover_path_mtu(target, is_ipv6, limit=local_mtu)
        
        return {
            "local_mtu": local_mtu,
            "path_mtu": path_mtu,
        }
