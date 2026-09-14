#!/usr/bin/env python3
"""Create-or-complete a Sprint 15 CodeSpring Kanban card by exact title."""

from __future__ import annotations

import json
import subprocess
import sys

ROOT = "/workspace"


def _cs(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["codespring", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _load() -> list[dict]:
    proc = _cs(["tasks", "--json"])
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout or "codespring tasks failed\n")
        raise SystemExit(proc.returncode or 1)
    raw = proc.stdout
    tasks = json.loads(raw[raw.find("[") :])
    return tasks if isinstance(tasks, list) else tasks.get("data") or []


def main() -> int:
    title = sys.argv[1] if len(sys.argv) > 1 else ""
    sha = sys.argv[2] if len(sys.argv) > 2 else ""
    number = sys.argv[3] if len(sys.argv) > 3 else ""
    if not title:
        print("usage: s15_kanban.py '<title>' [sha] [nnn]", file=sys.stderr)
        return 2
    wanted = {title, title.replace("[S15] ", "[Sprint 15] ", 1)}
    if number.isdigit():
        wanted.add(f"[S15] Task {int(number):03d}")
    tasks = _load()
    match = next((t for t in tasks if t.get("title") in wanted), None)
    if match is None:
        created = _cs(["task", "create", "--title", title, "--priority", "medium", "--json"])
        if created.returncode != 0:
            sys.stderr.write(created.stderr or created.stdout or "create failed\n")
            return created.returncode or 1
        match = json.loads(created.stdout[created.stdout.find("{") :])
        if isinstance(match, list):
            match = match[0]
    tid = match["id"]
    if match.get("title") != title:
        _cs(["task", "update", tid, "--title", title])
    if match.get("status") == "todo":
        _cs(["task", "start", tid])
    if match.get("status") != "done":
        done = _cs(["task", "done", tid])
        if done.returncode != 0:
            sys.stderr.write(done.stderr or done.stdout or "task done failed\n")
            return done.returncode or 1
    desc = f"Landed on main as `{sha}`.\n\n{title}" if sha else title
    _cs(["task", "update", tid, "--description", desc])
    print(tid, "done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
