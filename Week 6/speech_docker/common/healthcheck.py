"""Check local HTTP liveness without using Azure or printing response bodies."""

import sys
from urllib.request import urlopen

try:
    with urlopen("http://127.0.0.1:8000/", timeout=3) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
