"""Model usage budgets / cost guardrails for embeddings and chat."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Budget:
    tokens: int = 0
    calls: int = 0
    token_cap: int = 50_000
    call_cap: int = 200


_BUDGETS: dict[str, Budget] = {}


def budget_for(tenant: str) -> Budget:
    return _BUDGETS.setdefault(tenant, Budget())


def consume(tenant: str, tokens: int) -> dict[str, object]:
    row = budget_for(tenant)
    row.tokens += max(0, int(tokens))
    row.calls += 1
    allowed = row.tokens <= row.token_cap and row.calls <= row.call_cap
    return {
        "tenant": tenant,
        "tokens": row.tokens,
        "calls": row.calls,
        "allowed": allowed,
        "remaining": max(0, row.token_cap - row.tokens),
    }


def reset() -> None:
    _BUDGETS.clear()
