"""Container HEALTHCHECK without curl (slim images do not ship it).

Exit code 0 = healthy, 1 = unhealthy. Usage: python -m app.healthcheck
"""

from __future__ import annotations

import sys
import urllib.request

URL = "http://127.0.0.1:8000/health/live"


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=2) as response:
            return 0 if response.status == 200 else 1
    except OSError:
        return 1


if __name__ == "__main__":
    sys.exit(main())
