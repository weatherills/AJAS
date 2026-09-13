"""CLI: rebuild the matching skills taxonomy dump."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.matching.taxonomy import rebuild_taxonomy  # noqa: E402


def main() -> None:
    print(json.dumps(rebuild_taxonomy(), indent=2))


if __name__ == "__main__":
    main()
