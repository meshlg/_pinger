"""
Module for checking project dependencies and enforcing single instance.
"""

import sys
import os
import atexit

from single_instance import SingleInstance

# Global reference for atexit cleanup
_instance_lock: SingleInstance | None = None

def _cleanup_on_exit():
    """Cleanup function registered with atexit to ensure resources are released."""
    global _instance_lock
    if _instance_lock is not None:
        try:
            _instance_lock.release()
        except Exception:
            pass

def check_project_dependencies() -> None:
    """
    Check all project dependencies before importing external packages.
    """
    required_packages = ["rich", "requests", "dns"]
    missing_packages = []
    
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing_packages.append(pkg)
    
    if missing_packages:
        # Import t() here to avoid circular imports — config only needs stdlib
        from config import t
        print(t("err_missing_deps"))
        for pkg in missing_packages:
            print(f"  - {pkg}")
        print(f"\n{t('install_deps_hint')}")
        print("  pip install -r requirements.txt")
        sys.exit(1)


def enforce_single_instance() -> SingleInstance | None:
    """
    Check if another instance is already running.
    
    Returns:
        SingleInstance lock object if acquired, None if another instance running.
    """
    from config import ENABLE_SINGLE_INSTANCE, t
    global _instance_lock
    
    if not ENABLE_SINGLE_INSTANCE:
        return None
    
    locker = SingleInstance()
    if not locker.acquire():
        print(t("err_another_instance_running"))
        # Notify the running instance about this attempt
        try:
            from single_instance_notifications import _notify_running_instance
            from datetime import datetime, timezone
            msg = t("alert_second_instance_attempt").format(time=datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"))
            _notify_running_instance(msg)
        except Exception:
            pass
        sys.exit(1)
    
    _instance_lock = locker
    # Register cleanup for normal program termination
    atexit.register(_cleanup_on_exit)
    return locker


def main() -> None:
    """CLI entry point for the pinger application."""
    import argparse
    import asyncio
    import logging
    import shutil
    import os

    # Parse CLI args BEFORE config is imported so env var overrides take effect
    parser = argparse.ArgumentParser(
        description="Network Pinger - Network monitoring and diagnostics tool",
        prog="pinger"
    )
    parser.add_argument(
        "--target",
        "-t",
        type=str,
        help="Target IP or hostname to monitor (default: 1.1.1.1)",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        help="Ping interval in seconds (default: 1)",
    )
    args = parser.parse_args()

    # Set env vars BEFORE config module is imported by other modules
    if args.target:
        os.environ["TARGET_IP"] = args.target
    if args.interval is not None:
        os.environ["INTERVAL"] = str(args.interval)

    from config import (
        t,
        LOG_FILE,
        LOG_LEVEL,
        LOG_TRUNCATE_ON_START,
        LOG_DIR,
        TARGET_IP,
        INTERVAL,
        ENABLE_AUTO_TRACEROUTE,
        ENABLE_HOP_MONITORING,
        ENABLE_ROUTE_ANALYSIS,
    )

    # Check single instance BEFORE anything else
    instance_lock = enforce_single_instance()

    # Check dependencies
    check_project_dependencies()

    missing_commands = []
    if shutil.which("ping") is None:
        missing_commands.append("ping")

    traceroute_required = any((
        ENABLE_AUTO_TRACEROUTE,
        ENABLE_HOP_MONITORING,
        ENABLE_ROUTE_ANALYSIS,
    ))
    if traceroute_required and not (shutil.which("traceroute") or shutil.which("tracert")):
        missing_commands.append("traceroute/tracert")

    if missing_commands:
        print(t("err_missing_commands").format(cmds=", ".join(missing_commands)))
        print(f"\n{t('install_commands_hint')}")
        if sys.platform == "win32":
            print(t("win_ping_hint"))
            print(t("win_tracert_hint"))
        else:
            print("  Debian/Ubuntu: sudo apt-get install iputils-ping traceroute")
            print("  RHEL/CentOS: sudo yum install iputils traceroute")
            print("  Alpine: sudo apk add iputils-traceroute")
        sys.exit(1)

    from main import run_async_main

    # Create log directory if it doesn't exist
    os.makedirs(LOG_DIR, exist_ok=True)

    logging.basicConfig(
        filename=LOG_FILE,
        filemode='w' if LOG_TRUNCATE_ON_START else 'a',
        level=getattr(logging, LOG_LEVEL.upper()),
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )

    # Check psutil if memory monitoring is enabled
    from config import ENABLE_MEMORY_MONITORING
    if ENABLE_MEMORY_MONITORING:
        try:
            __import__("psutil")
        except ImportError:
            logging.warning("psutil not installed, memory monitoring disabled. Install: pip install psutil")

    asyncio.run(run_async_main())