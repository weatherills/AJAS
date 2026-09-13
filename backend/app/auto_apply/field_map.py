"""Per-site Auto-Apply field mapping overrides."""

from __future__ import annotations

DEFAULT_MAP = {
    "greenhouse": {"full_name": "full_name", "email": "email", "phone": "phone", "resume": "resume"},
    "lever": {"full_name": "name", "email": "email", "phone": "phone", "resume": "resume"},
}

_OVERRIDES: dict[str, dict[str, str]] = {}


def reset_overrides() -> None:
    _OVERRIDES.clear()


def set_override(site: str, mapping: dict[str, str]) -> dict[str, str]:
    key = (site or "").strip().lower()
    cleaned = {str(src): str(dest) for src, dest in mapping.items() if src and dest}
    _OVERRIDES[key] = cleaned
    return mapping_for(key)


def mapping_for(site: str) -> dict[str, str]:
    key = (site or "").strip().lower()
    base = dict(DEFAULT_MAP.get(key, DEFAULT_MAP["greenhouse"]))
    base.update(_OVERRIDES.get(key, {}))
    return base


def apply_mapping(site: str, profile: dict[str, str]) -> dict[str, str]:
    mapping = mapping_for(site)
    out: dict[str, str] = {}
    for src, dest in mapping.items():
        if src in profile and profile[src]:
            out[dest] = profile[src]
    return out
