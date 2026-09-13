from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.mail.scan import EICAR_SIGNATURE
from app.sprint12 import VERSION
from app.sprint12 import billing as billing_mod
from app.sprint12 import tenants as tenants_mod

FIXTURES = Path(__file__).parent / "fixtures"

def setup_function() -> None:
    tenants_mod.reset()
    billing_mod.reset()

def test_version_is_sprint12():
    from app.features.health import _status_payload

    assert VERSION == "sprint12"
    assert _status_payload()["version"] == "sprint12"

def test_multi_tenant_org_workspace_scoping():
    tenant = tenants_mod.create_tenant(name="Acme Labs", owner_id="ada")
    tenants_mod.add_workspace(tenant.id, "EU")
    records = [{"id": "j1", "tenant_id": tenant.id}, {"id": "j2", "tenant_id": "other"}]
    assert [row["id"] for row in tenants_mod.scoped(records, tenant_id=tenant.id, user_id="ada")] == ["j1"]
    assert tenants_mod.scoped(records, tenant_id=tenant.id, user_id="bob") == []

def test_tenant_onboarding_invite_email():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    invite = tenants_mod.invite_member(tenant_id=tenant.id, actor_id="ada", email="linus@example.test", role="admin")
    assert invite.status == "pending"
    assert tenants_mod.outbox()[0]["template"] == "tenant.invite"
    membership = tenants_mod.accept_invite(token=invite.token, user_id="linus")
    assert membership.role == "admin"

def test_rbac_owner_admin_member_readonly():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    invite = tenants_mod.invite_member(tenant_id=tenant.id, actor_id="ada", email="r@example.test", role="readonly")
    tenants_mod.accept_invite(token=invite.token, user_id="reader")
    assert tenants_mod.can(tenant.id, "ada", "tenant.admin") is True
    assert tenants_mod.can(tenant.id, "reader", "review.read") is True
    assert tenants_mod.can(tenant.id, "reader", "apply.write") is False

def test_access_control_require_permission():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    try:
        tenants_mod.require(tenant.id, "ghost", "tenant.invite")
        raise AssertionError("expected")
    except PermissionError:
        pass

def test_billing_usage_counters_and_plans():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    billing_mod.assign_plan(tenant.id, "free")
    snap = billing_mod.meter(tenant.id, "match", 100)
    assert snap["soft"] is False
    snap = billing_mod.meter(tenant.id, "match", 300)
    assert snap["soft"] is True
    assert snap["allowed"] is True
    snap = billing_mod.meter(tenant.id, "match", 100)
    assert snap["hard"] is True
    assert snap["allowed"] is False
    billing_mod.assign_plan(tenant.id, "pro")
    assert billing_mod.feature_allowed(tenant.id, "share_links") is True
    assert billing_mod.feature_allowed(tenant.id, "sso") is False

def test_sprint12_kanban_progress():
    from app.sprint12 import COMPLETED, VERSION
    assert VERSION == "sprint12"
    assert COMPLETED == 5
