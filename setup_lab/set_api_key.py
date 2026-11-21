"""Compatibility entry point for the session-only API checker."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nhap_api_key import main


if __name__ == "__main__":
    raise SystemExit(main())
