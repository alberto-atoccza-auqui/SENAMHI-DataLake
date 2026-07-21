#!/usr/bin/env python
"""SENAMHI DataLake — dev server launcher.

Usage:
    python run_dev.py
"""
import sys
import os
from pathlib import Path

# ── Ensure the package is importable without `pip install -e .` ──
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = str(PROJECT_ROOT / "src")

# Add src to sys.path first so `senamhi_datalake` is found
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

if __name__ == "__main__":
    import uvicorn
    print(f"Project : {PROJECT_ROOT}")
    print(f"src     : {SRC_DIR}")
    print(f"Server  : http://localhost:8000")
    print(f"Docs    : http://localhost:8000/api/docs")
    print(f"Frontend: http://localhost:8000")
    uvicorn.run(
        "senamhi_datalake.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
