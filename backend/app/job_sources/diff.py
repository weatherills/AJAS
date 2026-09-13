"""Diff successive job-description versions."""

from __future__ import annotations

from difflib import SequenceMatcher, unified_diff


def diff_job_description(previous: str, current: str) -> dict[str, object]:
    left = (previous or "").splitlines()
    right = (current or "").splitlines()
    matcher = SequenceMatcher(a=left, b=right)
    hunks: list[dict[str, object]] = []
    added = 0
    removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        hunks.append(
            {
                "op": tag,
                "before": left[i1:i2],
                "after": right[j1:j2],
            }
        )
        if tag in {"replace", "delete"}:
            removed += i2 - i1
        if tag in {"replace", "insert"}:
            added += j2 - j1
    unified = "\n".join(unified_diff(left, right, fromfile="previous", tofile="current", lineterm=""))
    return {
        "changed": bool(hunks),
        "added": added,
        "removed": removed,
        "hunks": hunks[:40],
        "unified": unified,
    }
