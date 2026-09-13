"""Equity and bonus extraction alongside cash salary ranges."""

from __future__ import annotations

import re
from typing import Any

from app.job_sources.salary import parse_salary_v2

_EQUITY = re.compile(
    r"(?i)(?P<eq>\d+(?:\.\d+)?)\s*%\s*(?:equity|options?|rsus?)\b"
)
_EQUITY_USD = re.compile(r"(?i)(?:equity|rsus?)\s*(?:of|:)?\s*\$?\s*(?P<amt>\d{2,3}(?:,\d{3})?)\s*(?P<k>k)?")
_BONUS = re.compile(r"(?i)(?P<pct>\d{1,3})\s*%\s*(?:annual\s+)?bonus")
_SIGNING = re.compile(r"(?i)signing bonus\s*(?:of|:)?\s*\$?\s*(?P<amt>\d{2,3}(?:,\d{3})?)\s*(?P<k>k)?")


def _money(raw: str, k: str | None) -> int:
    value = float(raw.replace(",", ""))
    if k or value < 1000:
        value *= 1000
    return int(value)


def parse_comp(text: str) -> dict[str, Any]:
    cash = parse_salary_v2(text)
    equity_pct = None
    equity_usd = None
    bonus_pct = None
    signing = None
    eq = _EQUITY.search(text or "")
    if eq:
        equity_pct = float(eq.group("eq"))
    eq_usd = _EQUITY_USD.search(text or "")
    if eq_usd:
        equity_usd = _money(eq_usd.group("amt"), eq_usd.group("k"))
    bonus = _BONUS.search(text or "")
    if bonus:
        bonus_pct = int(bonus.group("pct"))
    sign = _SIGNING.search(text or "")
    if sign:
        signing = _money(sign.group("amt"), sign.group("k"))
    return {
        **cash,
        "equityPercent": equity_pct,
        "equityUsd": equity_usd,
        "bonusPercent": bonus_pct,
        "signingBonus": signing,
    }
