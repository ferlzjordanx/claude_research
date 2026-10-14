"""Container health probe: `python -m app.healthcheck` (no curl in
the slim image). Exit code 0 = healthy."""

import sys
import urllib.request

try:
    with urllib.request.urlopen(
        "http://127.0.0.1:8000/health", timeout=3
    ) as response:
        sys.exit(0 if response.status == 200 else 1)
except OSError:
    sys.exit(1)
