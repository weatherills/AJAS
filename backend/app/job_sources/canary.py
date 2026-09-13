"""HTML snapshot canaries for optional board fixtures.

Compares SHA-256 of checked-in HTML against the current file. Drift is a
canary failure, not a trigger to live-scrape.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "job_boards"

GOLDEN = {
    "greenhouse_career.html": None,
    "lever_career.html": None,
    "workday_career.html": None,
    "glassdoor.html": None,
    "wellfound.html": None,
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_digest(name: str, root: Path | None = None) -> str:
    folder = root or DEFAULT_DIR
    sidecar = folder / f"{name}.sha256"
    if sidecar.exists():
        return sidecar.read_text().strip().split()[0]
    return digest(folder / name)


def check_snapshot(name: str, root: Path | None = None) -> dict[str, object]:
    folder = root or DEFAULT_DIR
    path = folder / name
    current = digest(path) if path.exists() else ""
    golden = expected_digest(name, folder) if path.exists() else ""
    return {
        "name": name,
        "ok": bool(current) and current == golden,
        "digest": current,
        "expected": golden,
        "missing": not path.exists(),
    }


def run_canaries(names: list[str] | None = None, root: Path | None = None) -> dict[str, object]:
    targets = names or list(GOLDEN)
    results = [check_snapshot(name, root) for name in targets]
    return {
        "ok": all(item["ok"] for item in results),
        "checked": len(results),
        "failed": [item["name"] for item in results if not item["ok"]],
        "results": results,
    }
