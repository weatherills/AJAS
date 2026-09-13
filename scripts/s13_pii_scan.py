#!/usr/bin/env python3
"""CI hook: scan text files for email-shaped PII leaks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="AJAS PII scan")
    parser.add_argument("paths", nargs="*", default=["backend/app", "frontend/src"])
    args = parser.parse_args()
    from app.sprint13.security import pii_scan_text

    leaks = []
    for raw in args.paths:
        path = Path(raw)
        files = [path] if path.is_file() else list(path.rglob("*"))
        for file in files:
            if not file.is_file() or file.suffix.lower() not in {".py", ".ts", ".tsx", ".md", ".json"}:
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            result = pii_scan_text(text)
            if not result["clean"]:
                leaks.append({"path": str(file), "leaks": result["leaks"][:8]})
    print(json.dumps({"clean": not leaks, "hits": leaks[:50], "engine": "ajas.pii.ci.v1"}))
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
