"""Quantitative LinkedIn success targets and QA acceptance checks."""

from __future__ import annotations

from statistics import median
from typing import Any

from app.integrations.linkedin_spec import SUCCESS_TARGETS
from app.job_sources.constants import SOURCE_TYPES


def _pct(num: float, den: float) -> float:
    if den <= 0:
        return 100.0
    return round((num / den) * 100.0, 2)


def evaluate(sample: dict[str, Any]) -> dict[str, Any]:
    """Score a run against SUCCESS_TARGETS.

    ``dedupeRatePct`` is the share of seen listings that were duplicates
    (skipped because they already existed). Target is a *minimum* catch rate
    when duplicates were present, otherwise the check is skipped.
    """
    fetched_ok = float(sample.get("ingested") or 0) + float(sample.get("updated") or 0)
    fetched_fail = float(sample.get("failed") or 0)
    fetch_pct = _pct(fetched_ok, fetched_ok + fetched_fail)

    skipped = float(sample.get("skipped") or 0)
    seen = fetched_ok + skipped
    dupes_present = bool(sample.get("duplicatesPresent"))
    dedupe_pct = _pct(skipped, seen) if dupes_present else 100.0

    submitted = float(sample.get("submitted") or 0)
    attempts = float(sample.get("applyAttempts") or 0)
    apply_pct = _pct(submitted, attempts) if attempts else 100.0

    runtimes = [int(ms) for ms in (sample.get("runtimesMs") or []) if isinstance(ms, (int, float))]
    median_ms = int(median(runtimes)) if runtimes else 0

    checks = {
        "fetchSuccessPct": fetch_pct >= float(SUCCESS_TARGETS["fetchSuccessPct"]),
        "dedupeRatePct": (not dupes_present) or dedupe_pct >= float(SUCCESS_TARGETS["dedupeRatePct"]),
        "easyApplyCompletionPct": apply_pct >= float(SUCCESS_TARGETS["easyApplyCompletionPct"]),
        "medianRuntimeMs": median_ms <= int(SUCCESS_TARGETS["medianRuntimeMs"]) if runtimes else True,
    }
    return {
        "targets": SUCCESS_TARGETS,
        "measured": {
            "fetchSuccessPct": fetch_pct,
            "dedupeRatePct": dedupe_pct,
            "easyApplyCompletionPct": apply_pct,
            "medianRuntimeMs": median_ms,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def qa_acceptance(*, flags: dict[str, Any], captcha_bypass: bool, receipts: int, attempts: int, audit_safe: bool) -> dict[str, Any]:
    checks = {
        "flag_default_off": flags.get("linkedin_adapter") is False and flags.get("linkedin_easy_apply") is False,
        "source_types_unchanged": SOURCE_TYPES == frozenset({"greenhouse", "lever"}),
        "captcha_never_bypassed": captcha_bypass is False,
        "receipt_on_every_attempt": receipts >= attempts,
        "pii_redacted_in_audit": audit_safe,
    }
    return {"checks": checks, "passed": all(checks.values()), "qa": list(SUCCESS_TARGETS["qa"])}
