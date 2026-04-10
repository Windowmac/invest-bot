#!/usr/bin/env python3
"""Manual / scheduled weekly memory reset.

Usage:
  python scripts/weekly_reset.py          # run directly
  make reset                              # via Makefile
  docker-compose run --rm memory_reset    # via Docker
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.memory_reset import run_memory_reset

if __name__ == "__main__":
    run_memory_reset()
