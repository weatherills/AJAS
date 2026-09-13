"""Multi-currency salary ranges and total-comp detection."""

from __future__ import annotations

import re

_CURRENCY = {
    "$": "USD",
    "usd": "USD",
    "us$": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "cad": "CAD",
    "c$": "CAD",
}
_SALARY_V2 = re.compile(
    r"(?i)(?P<cur>\$|usd|us\$|€|eur|£|gbp|cad|c\$)?\s*"
    r"(?P<min>\d{2,3}(?:,\d{3})?(?:\.\d+)?)\s*(?P<k1>k)?"
    r"\s*(?:-|–|to)\s*"
    r"(?P<cur2>\$|usd|us\$|€|eur|£|gbp|cad|c\$)?\s*"
    r"(?P<max>\d{2,3}(?:,\d{3})?(?:\.\d+)?)\s*(?P<k2>k)?"
)
_SINGLE_V2 = re.compile(
    r"(?i)(?P<cur>\$|usd|us\$|€|eur|£|gbp|cad|c\$)\s*"
    r"(?P<val>\d{2,3}(?:,\d{3})?(?:\.\d+)?)\s*(?P<k>k)?"
)
_TOTAL_COMP = re.compile(r"(?i)\b(total comp(?:ensation)?|tcc|on.?target earnings|ote|including equity)\b")


def _currency_code(raw: str | None) -> str:
    if not raw:
        return "USD"
    return _CURRENCY.get(raw.lower(), "USD")


def _to_annual_v2(raw: str, *, k_suffix: str | None) -> int:
    digits = raw.replace(",", "")
    value = float(digits)
    if k_suffix or value < 1000:
        value *= 1000
    return int(value)


def parse_salary_v2(text: str) -> dict[str, object]:
    from app.job_sources.enrich import parse_salary

    hay = text or ""
    total = bool(_TOTAL_COMP.search(hay))
    match = _SALARY_V2.search(hay)
    if match:
        currency = _currency_code(match.group("cur") or match.group("cur2"))
        k_flag = match.group("k1") or match.group("k2")
        return {
            "min": _to_annual_v2(match.group("min"), k_suffix=k_flag),
            "max": _to_annual_v2(match.group("max"), k_suffix=k_flag),
            "currency": currency,
            "totalComp": total,
        }
    single = _SINGLE_V2.search(hay)
    if single:
        value = _to_annual_v2(single.group("val"), k_suffix=single.group("k"))
        return {"min": value, "max": value, "currency": _currency_code(single.group("cur")), "totalComp": total}
    legacy = parse_salary(hay)
    return {"min": legacy["min"], "max": legacy["max"], "currency": "USD", "totalComp": total}
