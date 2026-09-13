"""Metered usage, plan tiers, Stripe stubs, webhooks, and account caps."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.matching.keys import utc_now

METRICS = ("ingest", "match", "apply", "email")
PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "label": "Free",
        "priceCents": 0,
        "features": {"share_links": False, "recruiter_portal": False, "sso": False},
        "caps": {"ingest": 200, "match": 500, "apply": 10, "email": 50},
    },
    "pro": {
        "label": "Pro",
        "priceCents": 2900,
        "features": {"share_links": True, "recruiter_portal": False, "sso": False},
        "caps": {"ingest": 5000, "match": 20000, "apply": 200, "email": 2000},
    },
    "team": {
        "label": "Team",
        "priceCents": 9900,
        "features": {"share_links": True, "recruiter_portal": True, "sso": True},
        "caps": {"ingest": 50000, "match": 200000, "apply": 2000, "email": 20000},
    },
}

_USAGE: dict[str, dict[str, int]] = {}
_SUBSCRIPTIONS: dict[str, dict[str, Any]] = {}
_INVOICES: dict[str, dict[str, Any]] = {}


def reset() -> None:
    _USAGE.clear()
    _SUBSCRIPTIONS.clear()
    _INVOICES.clear()


def assign_plan(tenant_id: str, plan: str) -> dict[str, Any]:
    if plan not in PLANS:
        raise ValueError("unknown plan")
    row = {
        "tenantId": tenant_id,
        "plan": plan,
        "status": "active",
        "stripeCustomerId": f"cus_{tenant_id[:8]}",
        "stripeSubscriptionId": f"sub_{uuid4().hex[:12]}",
        "updatedAt": utc_now(),
    }
    _SUBSCRIPTIONS[tenant_id] = row
    return row


def plan_of(tenant_id: str) -> str:
    return (_SUBSCRIPTIONS.get(tenant_id) or {}).get("plan") or "free"


def feature_allowed(tenant_id: str, feature: str) -> bool:
    return bool(PLANS[plan_of(tenant_id)]["features"].get(feature))


def meter(tenant_id: str, metric: str, amount: int = 1) -> dict[str, Any]:
    if metric not in METRICS:
        raise ValueError("unknown metric")
    bucket = _USAGE.setdefault(tenant_id, {key: 0 for key in METRICS})
    bucket[metric] += int(amount)
    return check_caps(tenant_id, metric)


def usage_of(tenant_id: str) -> dict[str, int]:
    return dict(_USAGE.get(tenant_id) or {key: 0 for key in METRICS})


def check_caps(tenant_id: str, metric: str) -> dict[str, Any]:
    plan = plan_of(tenant_id)
    cap = int(PLANS[plan]["caps"][metric])
    used = usage_of(tenant_id)[metric]
    ratio = used / cap if cap else 1.0
    hard = used >= cap
    soft = used >= int(cap * 0.8)
    message = None
    if hard:
        message = f"{metric} hard cap reached for {plan} ({used}/{cap})"
    elif soft:
        message = f"{metric} approaching {plan} cap ({used}/{cap})"
    return {
        "tenantId": tenant_id,
        "metric": metric,
        "used": used,
        "cap": cap,
        "plan": plan,
        "soft": soft,
        "hard": hard,
        "allowed": not hard,
        "message": message,
    }


def stripe_checkout(tenant_id: str, plan: str) -> dict[str, Any]:
    if plan not in PLANS:
        raise ValueError("unknown plan")
    return {
        "id": f"cs_{uuid4().hex[:10]}",
        "url": f"https://checkout.stripe.test/ajas/{plan}",
        "tenantId": tenant_id,
        "plan": plan,
        "mode": "subscription",
    }


def handle_stripe_webhook(event: dict[str, Any]) -> dict[str, Any]:
    kind = event.get("type") or ""
    data = (event.get("data") or {}).get("object") or {}
    tenant_id = data.get("client_reference_id") or data.get("tenantId") or ""
    if not tenant_id:
        raise ValueError("missing tenant")
    if kind in {"checkout.session.completed", "customer.subscription.updated"}:
        plan = data.get("plan") or data.get("metadata", {}).get("plan") or "pro"
        assign_plan(tenant_id, plan)
    invoice_id = data.get("id") or str(uuid4())
    status = data.get("status") or ("paid" if "paid" in kind else "open")
    if "invoice" in kind or kind.endswith("paid"):
        _INVOICES[invoice_id] = {
            "id": invoice_id,
            "tenantId": tenant_id,
            "status": status if status != "open" or "paid" in kind else "paid",
            "amountCents": int(data.get("amount_paid") or PLANS[plan_of(tenant_id)]["priceCents"]),
            "updatedAt": utc_now(),
        }
    if kind == "invoice.paid":
        _INVOICES.setdefault(invoice_id, {})["status"] = "paid"
        _INVOICES[invoice_id]["tenantId"] = tenant_id
        _INVOICES[invoice_id]["updatedAt"] = utc_now()
        _INVOICES[invoice_id]["amountCents"] = int(data.get("amount_paid") or 0)
    return {"ok": True, "tenantId": tenant_id, "plan": plan_of(tenant_id), "invoices": list(_INVOICES.values())}


def invoices_for(tenant_id: str) -> list[dict[str, Any]]:
    return [row for row in _INVOICES.values() if row.get("tenantId") == tenant_id]
