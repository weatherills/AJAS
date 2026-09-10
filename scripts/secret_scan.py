#!/usr/bin/env python3
"""Fail CI when high-confidence secrets appear in the tree. Suppressions live in .secret-allowlist."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / ".secret-allowlist"

PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    re.compile(r"ghp_[0-9A-Za-z]{36}"),
    re.compile(r"azure_client_secret\s*=\s*['\"][^'\"]{8,}['\"]", re.I),
]


def allowed() -> set[str]:
    if not ALLOWLIST.exists():
        return set()
    return {line.strip() for line in ALLOWLIST.read_text().splitlines() if line.strip() and not line.startswith("#")}


def main() -> int:
    skip_dirs = {".git", "node_modules", ".venv", "dist", "__pycache__", ".codespring"}
    hits: list[str] = []
    allow = allowed()
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".webp", ".mp4", ".pdf", ".zip"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(path.relative_to(ROOT))
        if rel in allow:
            continue
        for pattern in PATTERNS:
            if pattern.search(text):
                hits.append(f"{rel}: {pattern.pattern}")
                break
    if hits:
        print("Secret scan failed:")
        print("\n".join(hits))
        print("Add a relative path to .secret-allowlist to suppress a known false positive.")
        return 1
    print("Secret scan clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
