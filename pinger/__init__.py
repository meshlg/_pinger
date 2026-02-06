"""
Module for checking project dependencies.
"""

import sys

def check_project_dependencies() -> None:
    """
    Check all project dependencies before importing external packages.
    """
    required_packages = ["rich", "requests", "pythonping"]
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