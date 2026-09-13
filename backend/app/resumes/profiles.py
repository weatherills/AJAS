"""Multiple resume profiles with tags."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResumeProfile:
    profile_id: str
    resume_id: str
    label: str
    tags: list[str] = field(default_factory=list)


_PROFILES: dict[str, list[ResumeProfile]] = {}


def reset_profiles() -> None:
    _PROFILES.clear()


def upsert_profile(user_id: str, profile: ResumeProfile) -> ResumeProfile:
    rows = _PROFILES.setdefault(user_id, [])
    tags = sorted({tag.strip().lower() for tag in profile.tags if tag.strip()})
    stored = ResumeProfile(profile.profile_id, profile.resume_id, profile.label, tags)
    rows[:] = [row for row in rows if row.profile_id != stored.profile_id] + [stored]
    return stored


def list_profiles(user_id: str, *, tag: str | None = None) -> list[ResumeProfile]:
    rows = list(_PROFILES.get(user_id, []))
    if tag:
        needle = tag.strip().lower()
        rows = [row for row in rows if needle in row.tags]
    return rows
