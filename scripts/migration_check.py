#!/usr/bin/env python3
"""Fail if Cosmos container helpers look like destructive rebuilds."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend" / "app"
FORBIDDEN = ("delete_container", "delete_database", "DropContainer")
REQUIRED = "create_container_if_not_exists"


def main() -> int:
    hits = []
    has_expand = False
    for path in ROOT.rglob("containers.py"):
        text = path.read_text(encoding="utf-8")
        if REQUIRED in text:
            has_expand = True
        for needle in FORBIDDEN:
            if needle in text:
                hits.append(f"{path}: {needle}")
    if hits:
        print("Unsafe migration pattern:")
        print("\n".join(hits))
        return 1
    if not has_expand:
        print("No expand-only create_container_if_not_exists helpers found")
        return 1
    print("Migration safety check passed (expand-only container create)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
