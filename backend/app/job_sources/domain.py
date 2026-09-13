"""Resolve a company name to a website domain via MX, then WHOIS fallbacks."""

from __future__ import annotations

import re
from typing import Callable

_SLUG = re.compile(r"[^a-z0-9]+")

Lookup = Callable[[str], str | None]


def company_slug(name: str) -> str:
    return _SLUG.sub("", (name or "").lower())


def guess_domain(company: str) -> str:
    slug = company_slug(company)
    return f"{slug}.com" if slug else ""


def _mx_lookup_stub(domain: str) -> str | None:
    """Offline MX probe. Real DNS is not used in tests or default ingest."""
    if domain.endswith(".com") and len(domain) > 4:
        return domain
    return None


def _whois_lookup_stub(company: str) -> str | None:
    """Offline WHOIS fallback. Does not call the public WHOIS network."""
    slug = company_slug(company)
    if not slug:
        return None
    return f"{slug}.com"


def resolve_company_domain(
    company: str,
    *,
    hint: str | None = None,
    mx_lookup: Lookup | None = None,
    whois_lookup: Lookup | None = None,
) -> dict[str, str | None]:
    if hint:
        host = hint.lower().strip().removeprefix("https://").removeprefix("http://").split("/")[0]
        host = host.removeprefix("www.")
        if "." in host:
            return {"domain": host, "method": "hint", "company": company}
    guessed = guess_domain(company)
    mx = (mx_lookup or _mx_lookup_stub)(guessed) if guessed else None
    if mx:
        return {"domain": mx, "method": "mx", "company": company}
    whois = (whois_lookup or _whois_lookup_stub)(company)
    if whois:
        return {"domain": whois, "method": "whois", "company": company}
    return {"domain": guessed or None, "method": "guess", "company": company}
