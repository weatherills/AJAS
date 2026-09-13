"""Infer IANA timezones from normalized job locations."""

from __future__ import annotations

from typing import Any

CITY_TZ = {
    "seattle": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles",
    "los angeles": "America/Los_Angeles",
    "portland": "America/Los_Angeles",
    "austin": "America/Chicago",
    "chicago": "America/Chicago",
    "dallas": "America/Chicago",
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "boston": "America/New_York",
    "dublin": "Europe/Dublin",
    "london": "Europe/London",
    "berlin": "Europe/Berlin",
    "remote": "UTC",
}

STATE_TZ = {
    "wa": "America/Los_Angeles",
    "ca": "America/Los_Angeles",
    "or": "America/Los_Angeles",
    "tx": "America/Chicago",
    "il": "America/Chicago",
    "ny": "America/New_York",
    "ma": "America/New_York",
}


def infer_timezone(location: str | None) -> dict[str, Any]:
    text = (location or "").strip().lower()
    if not text:
        return {"timezone": None, "source": None, "location": location or ""}
    for city, zone in CITY_TZ.items():
        if city in text:
            return {"timezone": zone, "source": "city", "location": location}
    if "," in text:
        tail = text.split(",")[-1].strip()
        if tail in STATE_TZ:
            return {"timezone": STATE_TZ[tail], "source": "region", "location": location}
    return {"timezone": None, "source": None, "location": location}
