"""Org/workspace tenancy, invites, and RBAC (Owner / Admin / Member / Read-only)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.matching.keys import utc_now

ROLES = ("owner", "admin", "member", "readonly")
ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER, ROLE_READONLY = ROLES

PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_OWNER: frozenset(
        {
            "tenant.admin",
            "tenant.invite",
            "tenant.billing",
            "ops.write",
            "review.write",
            "apply.write",
            "settings.write",
            "review.read",
        }
    ),
    ROLE_ADMIN: frozenset(
        {
            "tenant.invite",
            "tenant.billing",
            "ops.write",
            "review.write",
            "apply.write",
            "settings.write",
            "review.read",
        }
    ),
    ROLE_MEMBER: frozenset({"review.write", "apply.write", "settings.write", "review.read"}),
    ROLE_READONLY: frozenset({"review.read"}),
}


@dataclass
class Tenant:
    id: str
    name: str
    slug: str
    created_at: str
    workspaces: list[str] = field(default_factory=list)


@dataclass
class Workspace:
    id: str
    tenant_id: str
    name: str


@dataclass
class Membership:
    tenant_id: str
    user_id: str
    role: str
    workspace_ids: list[str]


@dataclass
class Invite:
    id: str
    tenant_id: str
    email: str
    role: str
    token: str
    status: str
    sent_at: str


_TENANTS: dict[str, Tenant] = {}
_WORKSPACES: dict[str, Workspace] = {}
_MEMBERS: dict[tuple[str, str], Membership] = {}
_INVITES: dict[str, Invite] = {}
_OUTBOX: list[dict[str, Any]] = []


def reset() -> None:
    _TENANTS.clear()
    _WORKSPACES.clear()
    _MEMBERS.clear()
    _INVITES.clear()
    _OUTBOX.clear()


def _slug(name: str) -> str:
    raw = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    return raw or "tenant"


def create_tenant(*, name: str, owner_id: str, workspace_name: str = "Default") -> Tenant:
    tenant = Tenant(id=str(uuid4()), name=name.strip(), slug=_slug(name), created_at=utc_now())
    workspace = Workspace(id=str(uuid4()), tenant_id=tenant.id, name=workspace_name)
    tenant.workspaces.append(workspace.id)
    _TENANTS[tenant.id] = tenant
    _WORKSPACES[workspace.id] = workspace
    _MEMBERS[(tenant.id, owner_id)] = Membership(
        tenant_id=tenant.id, user_id=owner_id, role=ROLE_OWNER, workspace_ids=[workspace.id]
    )
    return tenant


def add_workspace(tenant_id: str, name: str) -> Workspace:
    tenant = _TENANTS[tenant_id]
    workspace = Workspace(id=str(uuid4()), tenant_id=tenant_id, name=name.strip())
    tenant.workspaces.append(workspace.id)
    _WORKSPACES[workspace.id] = workspace
    return workspace


def role_of(tenant_id: str, user_id: str) -> str | None:
    member = _MEMBERS.get((tenant_id, user_id))
    return member.role if member else None


def can(tenant_id: str, user_id: str, permission: str) -> bool:
    role = role_of(tenant_id, user_id)
    if not role:
        return False
    return permission in PERMISSIONS[role]


def require(tenant_id: str, user_id: str, permission: str) -> None:
    if not can(tenant_id, user_id, permission):
        raise PermissionError(f"missing permission {permission}")


def invite_member(*, tenant_id: str, actor_id: str, email: str, role: str = ROLE_MEMBER) -> Invite:
    require(tenant_id, actor_id, "tenant.invite")
    if role not in ROLES or role == ROLE_OWNER:
        raise ValueError("invalid invite role")
    token = hashlib.sha256(f"{tenant_id}:{email}:{uuid4()}".encode()).hexdigest()[:24]
    invite = Invite(
        id=str(uuid4()),
        tenant_id=tenant_id,
        email=email.strip().lower(),
        role=role,
        token=token,
        status="pending",
        sent_at=utc_now(),
    )
    _INVITES[invite.id] = invite
    _OUTBOX.append(
        {
            "to": invite.email,
            "template": "tenant.invite",
            "tenantId": tenant_id,
            "token": token,
            "role": role,
        }
    )
    return invite


def accept_invite(*, token: str, user_id: str) -> Membership:
    invite = next((item for item in _INVITES.values() if item.token == token and item.status == "pending"), None)
    if invite is None:
        raise KeyError("invite not found")
    tenant = _TENANTS[invite.tenant_id]
    membership = Membership(
        tenant_id=invite.tenant_id, user_id=user_id, role=invite.role, workspace_ids=list(tenant.workspaces)
    )
    _MEMBERS[(invite.tenant_id, user_id)] = membership
    invite.status = "accepted"
    return membership


def scoped(records: list[dict[str, Any]], *, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
    if not role_of(tenant_id, user_id):
        return []
    return [row for row in records if row.get("tenant_id") == tenant_id or row.get("tenantId") == tenant_id]


def outbox() -> list[dict[str, Any]]:
    return list(_OUTBOX)


def list_tenants_for(user_id: str) -> list[dict[str, Any]]:
    rows = []
    for (tenant_id, member_id), membership in _MEMBERS.items():
        if member_id != user_id:
            continue
        tenant = _TENANTS[tenant_id]
        rows.append(
            {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "role": membership.role,
                "workspaces": [ _WORKSPACES[wid].name for wid in tenant.workspaces if wid in _WORKSPACES ],
            }
        )
    return rows


def usage_dashboard(tenant_id: str, actor_id: str) -> dict[str, Any]:
    require(tenant_id, actor_id, "tenant.billing")
    members = [m for (tid, _), m in _MEMBERS.items() if tid == tenant_id]
    return {
        "tenantId": tenant_id,
        "memberCount": len(members),
        "roles": {role: sum(1 for m in members if m.role == role) for role in ROLES},
        "workspaceCount": len(_TENANTS[tenant_id].workspaces),
        "pendingInvites": sum(1 for inv in _INVITES.values() if inv.tenant_id == tenant_id and inv.status == "pending"),
    }
