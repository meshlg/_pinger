#!/usr/bin/env python3
"""
Standalone health check script for Docker/Kubernetes.
Performs an HTTP GET request to the health endpoint.
Handles Basic Auth and Token Auth using credentials from environment or secrets files.
"""

import sys
import os
import urllib.request
import base64
import time

def read_secret(name: str) -> str | None:
    """Read secret from file (via _FILE env var) or direct env var."""
    # Try _FILE variant first (Docker Secrets)
    file_path = os.environ.get(f"{name}_FILE")
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    
    # Fallback to direct env var
    return os.environ.get(name)

def main():
    # Load configuration
    port = os.environ.get("HEALTH_PORT", "8001")
    path = os.environ.get("HEALTH_PATH", "/health")
    addr = os.environ.get("HEALTH_ADDR_CHECK", "localhost")  # Use localhost for internal check
    
    url = f"http://{addr}:{port}{path}"
    
    # Load credentials securely
    user = read_secret("HEALTH_AUTH_USER")
    password = read_secret("HEALTH_AUTH_PASS")
    token = read_secret("HEALTH_TOKEN")
    token_header = os.environ.get("HEALTH_TOKEN_HEADER", "X-Health-Token")
    
    req = urllib.request.Request(url)
    
    # Add authentication headers
    if user and password:
        # Basic Auth
        auth_str = f"{user}:{password}"
        encoded = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        req.add_header("Authorization", f"Basic {encoded}")
    elif token:
        # Token Auth
        req.add_header(token_header, token)
        
    # Perform request
    try:
        start_time = time.time()
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                # Optional: Read body to ensure it's not partial
                response.read()
                print(f"Health check passed in {time.time() - start_time:.3f}s")
                sys.exit(0)
            else:
                print(f"Health check failed with status: {response.status}")
                sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"Health check failed: HTTP {e.code}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Health check failed: Connection error {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"Health check failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
