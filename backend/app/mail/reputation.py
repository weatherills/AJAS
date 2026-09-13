"""Daily send cap and warm-up curve for outbound recruiter mail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class ReputationState:
    day: date
    sent: int
    age_days: int


def daily_cap(*, age_days: int, max_cap: int = 80) -> int:
    if age_days <= 0:
        return 5
    # Warm-up: 5, 8, 12, 18, ... approaching max_cap
    cap = int(5 * (1.4 ** min(age_days, 21)))
    return min(max_cap, max(5, cap))


def can_send(state: ReputationState, *, max_cap: int = 80) -> dict[str, object]:
    cap = daily_cap(age_days=state.age_days, max_cap=max_cap)
    remaining = max(0, cap - state.sent)
    return {
        "allowed": remaining > 0,
        "cap": cap,
        "sent": state.sent,
        "remaining": remaining,
        "ageDays": state.age_days,
    }


def advance_day(state: ReputationState, *, today: date | None = None) -> ReputationState:
    today = today or date.today()
    if state.day == today:
        return state
    delta = (today - state.day).days
    return ReputationState(day=today, sent=0, age_days=state.age_days + max(1, delta))
