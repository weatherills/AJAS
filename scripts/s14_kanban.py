#!/usr/bin/env python3
"""Create-or-complete a Sprint 14 CodeSpring Kanban card by exact title."""

from __future__ import annotations

import json
import subprocess
import sys


ROOT = "/workspace"


def _cs(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["codespring", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _load() -> list[dict]:
    raw = _cs(["tasks", "--json"]).stdout
    tasks = json.loads(raw[raw.find("[") :])
    return tasks if isinstance(tasks, list) else tasks.get("data") or []


def main() -> int:
    title = sys.argv[1] if len(sys.argv) > 1 else ""
    sha = sys.argv[2] if len(sys.argv) > 2 else ""
    if not title:
        print("usage: s14_kanban.py '<title>' [sha]", file=sys.stderr)
        return 2
    alt = title.replace("[S14] ", "[Sprint 14] ", 1)
    tasks = _load()
    match = next((t for t in tasks if t.get("title") in {title, alt}), None)
    if match is None:
        created = _cs(["task", "create", "--title", title, "--priority", "medium", "--json"]).stdout
        match = json.loads(created[created.find("{") :])
        if isinstance(match, list):
            match = match[0]
    tid = match["id"]
    if match.get("title") != title:
        _cs(["task", "update", tid, "--title", title], check=False)
    if match.get("status") == "todo":
        _cs(["task", "start", tid], check=False)
    if match.get("status") != "done":
        _cs(["task", "done", tid], check=True)
    desc = f"Landed on main as `{sha}`.\n\n{title}" if sha else title
    _cs(["task", "update", tid, "--description", desc], check=False)
    print(tid, "done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
