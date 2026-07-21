#!/usr/bin/env python
"""Process queued SENAMHI extraction tasks outside the FastAPI process.

Usage:
    python scripts/run_extraction_worker.py --once
    python scripts/run_extraction_worker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from senamhi_datalake.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
