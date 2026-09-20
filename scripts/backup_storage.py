#!/usr/bin/env python3
"""Repo-root wrapper around backend/scripts/backup_storage.py."""

from __future__ import annotations

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parents[1] / "backend" / "scripts" / "backup_storage.py"), run_name="__main__")
