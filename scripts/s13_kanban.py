#!/usr/bin/env python3
"""Create-or-complete a Sprint 13 CodeSpring Kanban card by exact title."""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    title = sys.argv[1] if len(sys.argv) > 1 else ""
    if not title:
        print("usage: s13_kanban.py '<title>'", file=sys.stderr)
        return 2
    raw = subprocess.check_output(["codespring", "tasks", "--json"], text=True)
    tasks = json.loads(raw)
    if isinstance(tasks, dict):
        tasks = tasks.get("data") or []
    match = next((t for t in tasks if t.get("title") == title), None)
    if match is None:
        created = subprocess.check_output(
            ["codespring", "task", "create", "--title", title, "--priority", "medium", "--json"],
            text=True,
        )
        match = json.loads(created)
        if isinstance(match, list):
            match = match[0]
    tid = match["id"]
    if match.get("status") == "todo":
        subprocess.run(["codespring", "task", "start", tid], check=False, capture_output=True)
    if match.get("status") != "done":
        subprocess.run(["codespring", "task", "done", tid], check=True)
    print(tid, "done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
