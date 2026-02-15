#!/usr/bin/env python3
import re
import sys
import os
import datetime
from pathlib import Path

# Paths relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

FILE_PATTERNS = [
    {
        "path": PROJECT_ROOT / "config" / "settings_model.py",
        "regex": r'(VERSION: str = ")([^"]+)(")',
        "name": "config/settings_model.py"
    },
    {
        "path": PROJECT_ROOT / "pyproject.toml",
        "regex": r'(version = ")([^"]+)(")',
        "name": "pyproject.toml"
    },
    {
        "path": PROJECT_ROOT / "charts" / "pinger" / "Chart.yaml",
        "regex": r'(appVersion: ")([^"]+)(")',
        "name": "charts/pinger/Chart.yaml"
    }
]

def get_current_version():
    """Extract current version from settings_model.py"""
    params = FILE_PATTERNS[0]
    if not params["path"].exists():
        return None
    content = params["path"].read_text(encoding="utf-8")
    match = re.search(params["regex"], content)
    if match:
        return match.group(2)
    return None

def calculate_next_version(current_version):
    """
    Calculate next version based on logic:
    - Increment last digit of X.Y.Z
    - Carry over if > 9 (2.4.9 -> 2.5.0, 2.9.9 -> 3.0.0)
    - Append current time HHMM as build number
    """
    # Parse X.Y.Z
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)', current_version)
    if not match:
        print(f"[!] Could not parse semantic version from '{current_version}'")
        return None
        
    major, minor, patch = map(int, match.groups())
    
    # Increment logic
    patch += 1
    if patch > 9:
        patch = 0
        minor += 1
        if minor > 9:
            minor = 0
            major += 1
            
    # Timestamp HHMM
    now = datetime.datetime.now()
    build = now.strftime("%H%M")
    
    return f"{major}.{minor}.{patch}.{build}"

def bump_version(new_version, dry_run=False):
    """Update version string in all defined files."""
    print(f"Bump version to: {new_version}")
    
    if dry_run:
        print("[DRY RUN] No files will be modified.")
    
    for item in FILE_PATTERNS:
        file_path = item["path"]
        name = item["name"]
        
        if not file_path.exists():
            print(f"[X] File not found: {name}")
            continue
            
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Check if version pattern exists
            if not re.search(item["regex"], content):
                print(f"[!] Version pattern not found in {name}")
                continue
                
            # Replace version
            new_content = re.sub(item["regex"], f"\\g<1>{new_version}\\g<3>", content, count=1)
            
            if new_content != content:
                if not dry_run:
                    file_path.write_text(new_content, encoding="utf-8")
                    print(f"[OK] Updated {name}")
                else:
                    print(f"[DRY RUN] Would update {name}")
            else:
                print(f"[i] No changes needed for {name} (already matches)")
                
        except Exception as e:
            print(f"[X] Error updating {name}: {e}")

def main():
    dry_run = "--dry-run" in sys.argv
    new_version = None

    # Check for manual version argument
    for arg in sys.argv[1:]:
        if arg != "--dry-run":
            new_version = arg
            break
            
    if not new_version:
        current = get_current_version()
        if not current:
            print("[X] Could not detect current version.")
            sys.exit(1)
            
        print(f"Current version: {current}")
        new_version = calculate_next_version(current)
        if not new_version:
            sys.exit(1)
            
        print(f"Suggested next version: {new_version}")
        if not dry_run:
            confirm = input("Bind to this version? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Aborted.")
                sys.exit(0)
    
    # Simple semantic version validation (lenient)
    if not re.match(r'^\d+\.\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?$', new_version):
        print(f"[!] Warning: Version '{new_version}' does not look like a standard semantic version.")
        if not dry_run:
            confirm = input("Continue anyway? (y/n): ").strip().lower()
            if confirm != 'y':
                sys.exit(0)
            
    bump_version(new_version, dry_run=dry_run)
    print("\nDon't forget to update CHANGELOG.md!")

if __name__ == "__main__":
    main()
