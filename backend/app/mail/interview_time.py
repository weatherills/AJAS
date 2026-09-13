"""Parse interview times from recruiter mail and normalize to UTC."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.job_sources.timezone import infer_timezone

_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?::(\d{2}))?")
_US = re.compile(
    r"(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<year>\d{4})\s+"
    r"(?:at\s+)?(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>am|pm)?",
    re.I,
)

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _zone(location: str | None, explicit: str | None) -> str:
    if explicit:
        return explicit
    inferred = infer_timezone(location)
    return str(inferred.get("timezone") or "UTC")


def parse_interview_time(
    text: str,
    *,
    location: str | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    zone_name = _zone(location, timezone_name)
    try:
        zone = ZoneInfo(zone_name)
    except Exception:
        zone = ZoneInfo("UTC")
        zone_name = "UTC"
    blob = text or ""
    parsed: datetime | None = None
    iso = _ISO.search(blob)
    if iso:
        parsed = datetime(
            int(iso.group(1)[0:4]),
            int(iso.group(1)[5:7]),
            int(iso.group(1)[8:10]),
            int(iso.group(2)[0:2]),
            int(iso.group(2)[3:5]),
            int(iso.group(3) or 0),
            tzinfo=zone,
        )
    us = _US.search(blob)
    if us and parsed is None:
        month = _MONTHS[us.group("month")[:3].lower()]
        hour = int(us.group("hour"))
        ampm = (us.group("ampm") or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        parsed = datetime(
            int(us.group("year")),
            month,
            int(us.group("day")),
            hour,
            int(us.group("minute")),
            tzinfo=zone,
        )
    if parsed is None:
        return {"ok": False, "utc": None, "timezone": zone_name, "source": None}
    utc = parsed.astimezone(timezone.utc)
    return {
        "ok": True,
        "utc": utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "timezone": zone_name,
        "local": parsed.replace(microsecond=0).isoformat(),
        "source": "mail",
    }
