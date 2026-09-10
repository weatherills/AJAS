"""Short-lived access tokens, rotating refresh tokens, and device records.

Dev Bearer user-ids (e.g. ``local-user``) keep working. Session tokens use the
``ajas.at.`` prefix so ``get_principal`` can tell them apart.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

ACCESS_TTL_SECONDS = 15 * 60
REFRESH_TTL_SECONDS = 7 * 24 * 60 * 60
PREFIX = "ajas.at."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _secret() -> bytes:
    return (os.environ.get("AJAS_SESSION_SECRET") or "dev-session-secret").encode("utf-8")


@dataclass
class DeviceSession:
    id: str
    user_id: str
    label: str
    refresh_hash: str
    created_at: str
    last_seen_at: str
    expires_at: str
    rotated_from: str | None = None
    revoked: bool = False
    user_agent: str = ""
    ip: str | None = None


_devices: dict[str, DeviceSession] = {}
_csrf: dict[str, str] = {}


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def issue_access_token(user_id: str, *, role: str = "user") -> tuple[str, int]:
    exp = int(_now().timestamp()) + ACCESS_TTL_SECONDS
    nonce = secrets.token_hex(8)
    body = f"{user_id}|{role}|{exp}|{nonce}"
    token = f"{PREFIX}{body}|{_sign(body)}"
    return token, ACCESS_TTL_SECONDS


def parse_access_token(token: str) -> tuple[str, str] | None:
    if not token.startswith(PREFIX):
        return None
    raw = token[len(PREFIX) :]
    try:
        user_id, role, exp_s, nonce, sig = raw.split("|", 4)
    except ValueError:
        return None
    body = f"{user_id}|{role}|{exp_s}|{nonce}"
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    if int(exp_s) < int(_now().timestamp()):
        return None
    return user_id, role


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(
    user_id: str,
    *,
    role: str = "user",
    label: str = "This device",
    user_agent: str = "",
    ip: str | None = None,
) -> dict[str, Any]:
    access, expires_in = issue_access_token(user_id, role=role)
    refresh = secrets.token_urlsafe(32)
    now = _now()
    device = DeviceSession(
        id=str(uuid4()),
        user_id=user_id,
        label=label[:80] or "This device",
        refresh_hash=_hash_refresh(refresh),
        created_at=_stamp(now),
        last_seen_at=_stamp(now),
        expires_at=_stamp(now + timedelta(seconds=REFRESH_TTL_SECONDS)),
        user_agent=user_agent[:200],
        ip=ip,
    )
    _devices[device.id] = device
    from app.cookies import new_csrf_token

    csrf = new_csrf_token()
    _csrf[user_id] = csrf
    return {
        "accessToken": access,
        "refreshToken": refresh,
        "csrfToken": csrf,
        "tokenType": "Bearer",
        "expiresIn": expires_in,
        "deviceId": device.id,
        "role": role,
        "userId": user_id,
    }


def rotate_refresh(refresh_token: str, *, user_agent: str = "", ip: str | None = None) -> dict[str, Any]:
    digest = _hash_refresh(refresh_token)
    device = next((row for row in _devices.values() if row.refresh_hash == digest and not row.revoked), None)
    if device is None:
        raise ValueError("invalid refresh token")
    if datetime.fromisoformat(device.expires_at.replace("Z", "+00:00")) < _now():
        device.revoked = True
        raise ValueError("refresh token expired")
    old_id = device.id
    device.revoked = True
    issued = create_session(
        device.user_id,
        role="user",
        label=device.label,
        user_agent=user_agent or device.user_agent,
        ip=ip or device.ip,
    )
    new_device = _devices[issued["deviceId"]]
    new_device.rotated_from = old_id
    return issued


def list_devices(user_id: str) -> list[dict[str, Any]]:
    rows = [row for row in _devices.values() if row.user_id == user_id and not row.revoked]
    return [
        {
            "id": row.id,
            "label": row.label,
            "createdAt": row.created_at,
            "lastSeenAt": row.last_seen_at,
            "expiresAt": row.expires_at,
            "userAgent": row.user_agent,
            "current": False,
        }
        for row in rows
    ]


def csrf_for(user_id: str) -> str | None:
    return _csrf.get(user_id)


def revoke_device(user_id: str, device_id: str) -> None:
    row = _devices.get(device_id)
    if row is None or row.user_id != user_id:
        raise KeyError(device_id)
    row.revoked = True
