"""Annotate employment gaps from a rebuilt timeline."""

from __future__ import annotations

from app.resumes.timeline import rebuild_timeline


def annotate_gaps(bullets: list[str], *, notes: dict[str, str] | None = None) -> dict[str, object]:
    timeline = rebuild_timeline(bullets)
    remarks = notes or {}
    gaps = []
    for gap in timeline.get("gaps") or []:
        key = f"{gap.get('after')}|{gap.get('before')}"
        gaps.append({**gap, "note": remarks.get(key) or remarks.get(str(gap.get("after")), "")})
    return {"roles": timeline.get("roles") or [], "gaps": gaps}
