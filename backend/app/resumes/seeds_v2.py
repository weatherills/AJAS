"""Varied resume seeds: junior, mid, senior, remote-only."""

from __future__ import annotations

SEEDS = {
    "junior": """Skills: python, sql
Experience:
- Intern on internal tools
Projects
- Shipped a class project dashboard
""",
    "mid": """Skills: python, azure, react
Experience:
- Software engineer, 4 years
Projects
- Launched matching v1 and increased interview rate 18%
""",
    "senior": """Skills: python, azure, kubernetes, matching
Experience:
- Staff engineer, 10 years, remote
Projects
- Led ingestion rewrite and reduced crawl errors 40%
""",
    "remote-only": """Skills: python, distributed systems
Location: Remote
Experience:
- Senior engineer, remote-first
Projects
- Owned timezone-friendly on-call
""",
}


def seed_resumes() -> dict[str, str]:
    return dict(SEEDS)
