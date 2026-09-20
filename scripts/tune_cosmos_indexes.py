#!/usr/bin/env python3
"""Print composite-index proposals and estimated RU savings."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.storage.index_tuner import tune_all  # noqa: E402

print(json.dumps(tune_all(), indent=2))
