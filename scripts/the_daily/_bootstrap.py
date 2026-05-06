"""Bootstrap: ensure /root/ha/scripts and /root/ha/scripts/the_daily are on
sys.path so absolute imports (`import ha_api`, `import sources`) work whether
this package is run as `python file.py` or `python -m scripts.the_daily.foo`.
Also load /root/ha/.env without requiring python-dotenv."""

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent           # /root/ha/scripts
_ROOT = _SCRIPTS.parent            # /root/ha

for _p in (str(_HERE), str(_SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Minimal .env loader (no python-dotenv dependency)
_env_path = _ROOT / ".env"
if _env_path.exists():
    for raw in _env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        os.environ.setdefault(k, v)
