from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.mail.scan import EICAR_SIGNATURE
from app.sprint12 import VERSION
from app.sprint12 import billing as billing_mod
from app.sprint12 import platform as platform_mod
from app.sprint12 import product as product_mod
from app.sprint12 import ranking as ranking_mod
from app.sprint12 import sharing as sharing_mod
from app.sprint12 import tenants as tenants_mod

FIXTURES = Path(__file__).parent / "fixtures"

def setup_function() -> None:
    tenants_mod.reset()
    billing_mod.reset()
    sharing_mod.reset()
    ranking_mod.reset()
    product_mod.reset()
    platform_mod.reset()

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

def test_stripe_checkout_and_invoice_webhook():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    session = billing_mod.stripe_checkout(tenant.id, "team")
    assert session["url"].startswith("https://checkout.stripe.test/")
    billing_mod.handle_stripe_webhook(
        {
            "type": "checkout.session.completed",
            "data": {"object": {"client_reference_id": tenant.id, "plan": "team", "status": "complete"}},
        }
    )
    billing_mod.handle_stripe_webhook(
        {
            "type": "invoice.paid",
            "data": {"object": {"id": "in_1", "tenantId": tenant.id, "amount_paid": 9900, "status": "paid"}},
        }
    )
    assert billing_mod.plan_of(tenant.id) == "team"
    assert billing_mod.invoices_for(tenant.id)[0]["status"] == "paid"

def test_account_limits_soft_hard_messages():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    billing_mod.assign_plan(tenant.id, "free")
    billing_mod.meter(tenant.id, "apply", 8)
    soft = billing_mod.check_caps(tenant.id, "apply")
    assert "approaching" in (soft["message"] or "")
    billing_mod.meter(tenant.id, "apply", 2)
    hard = billing_mod.check_caps(tenant.id, "apply")
    assert "hard cap" in (hard["message"] or "")

def test_admin_tenant_usage_dashboard():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    dash = tenants_mod.usage_dashboard(tenant.id, "ada")
    assert dash["memberCount"] == 1
    assert dash["roles"]["owner"] == 1

def test_gdpr_bundle_json_and_csv():
    bundle = platform_mod.gdpr_bundle(
        user_id="ada",
        tenant_id="t1",
        records={"jobs": [{"id": "j1"}], "emails": [], "matches": [{"id": "m1"}], "resumes": [], "logs": []},
    )
    assert bundle["format"] == "ajas.gdpr.v2"
    assert "jobs,j1" in bundle["csv"]

def test_resume_library_import_queue():
    row = product_mod.enqueue_resume_import(user_id="ada", filename="cv.pdf")
    assert row["status"] == "queued"
    assert product_mod.import_queue("ada")[0]["filename"] == "cv.pdf"

def test_shareable_links_and_recruiter_portal():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    billing_mod.assign_plan(tenant.id, "team")
    link = sharing_mod.create_link(tenant_id=tenant.id, actor_id="ada", target_type="match", target_id="m1", ttl_hours=1)
    view = sharing_mod.recruiter_view(link["token"], match={"score": 88, "summary": "Strong Python", "highlights": ["azure"]})
    assert view["limited"] is True
    assert view["match"]["score"] == 88
    expired = sharing_mod.resolve(link["token"], now=datetime.now(timezone.utc) + timedelta(hours=2))
    assert expired is None

def test_feedback_loop_and_weight_training():
    ranking_mod.record_feedback(user_id="ada", job_id="j1", vote="up")
    ranking_mod.record_feedback(user_id="ada", job_id="j2", vote="up")
    weights = ranking_mod.weights_for("ada")
    assert weights["semantic"] > 0.6
    assert abs(weights["keyword"] + weights["semantic"] - 1.0) < 1e-6

def test_ranking_v3_feature_store_and_offline_harness():
    for i in range(4):
        ranking_mod.log_feature_row(user_id="ada", job_id=f"j{i}", features={"kw": float(i), "sem": 1.0 - i * 0.1}, label=1 if i > 1 else 0)
    fitted = ranking_mod.train_offline()
    assert fitted["status"] == "fitted"
    assert "kw" in fitted["weights"]

def test_ab_framework_and_explanation_styles():
    ranking_mod.upsert_experiment("explain.style", ["bullet", "narrative"])
    style = ranking_mod.explanation_style("ada")
    assert style in {"bullet", "narrative"}
    ranking_mod.track_metric("explain.style", style, 1.0)
    bullets = ranking_mod.format_explanation("bullet", ["Python", "Azure"])
    narrative = ranking_mod.format_explanation("narrative", ["Python", "Azure"])
    assert bullets.startswith("• ")
    assert "and Azure" in narrative

def test_skill_graph_cooccurrence_synonyms():
    ranking_mod.observe_skills(["python", "django", "flask"])
    ranking_mod.observe_skills(["python", "django"])
    assert "django" in ranking_mod.expand_synonyms("python", min_count=2)

def test_sprint12_kanban_progress():
    from app.sprint12 import COMPLETED, VERSION
    assert VERSION == "sprint12"
    assert COMPLETED == 20

def test_plan_tiers_feature_gates():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    billing_mod.assign_plan(tenant.id, "free")
    assert billing_mod.feature_allowed(tenant.id, "share_links") is False
    billing_mod.assign_plan(tenant.id, "pro")
    assert billing_mod.feature_allowed(tenant.id, "share_links") is True
    assert billing_mod.feature_allowed(tenant.id, "recruiter_portal") is False
    billing_mod.assign_plan(tenant.id, "team")
    assert billing_mod.feature_allowed(tenant.id, "recruiter_portal") is True
    assert billing_mod.feature_allowed(tenant.id, "sso") is True

def test_invoice_webhook_status_sync_only():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    billing_mod.assign_plan(tenant.id, "pro")
    billing_mod.handle_stripe_webhook(
        {"type": "invoice.paid", "data": {"object": {"id": "in_s12", "tenantId": tenant.id, "amount_paid": 2900, "status": "paid"}}}
    )
    assert billing_mod.invoices_for(tenant.id)[0]["id"] == "in_s12"

def test_share_link_expires_independently():
    tenant = tenants_mod.create_tenant(name="Acme", owner_id="ada")
    billing_mod.assign_plan(tenant.id, "pro")
    link = sharing_mod.create_link(tenant_id=tenant.id, actor_id="ada", target_type="job", target_id="j9", ttl_hours=1)
    assert sharing_mod.resolve(link["token"]) is not None
    assert sharing_mod.resolve(link["token"], now=datetime.now(timezone.utc) + timedelta(hours=3)) is None

def test_thumbs_down_cancels_semantic_boost():
    ranking_mod.record_feedback(user_id="ada", job_id="j1", vote="up")
    ranking_mod.record_feedback(user_id="ada", job_id="j1", vote="down")
    weights = ranking_mod.weights_for("ada")
    assert abs(weights["semantic"] - 0.6) < 1e-6

def test_explanation_style_narrative_variant():
    ranking_mod.upsert_experiment("explain.style", ["bullet", "narrative"])
            text = ranking_mod.format_explanation("narrative", ["Python", "Azure", "Cosmos"])
    assert "Python" in text and "and Cosmos" in text
