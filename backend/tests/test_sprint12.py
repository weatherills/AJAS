from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.mail.scan import EICAR_SIGNATURE
from app.sprint12 import VERSION
from app.sprint12 import tenants as tenants_mod

FIXTURES = Path(__file__).parent / "fixtures"

def setup_function() -> None:
    tenants_mod.reset()

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

def test_sprint12_kanban_progress():
    from app.sprint12 import COMPLETED, VERSION
    assert VERSION == "sprint12"
    assert COMPLETED == 1
