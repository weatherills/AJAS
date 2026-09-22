"""Sealed LinkedIn session store: lifecycle, refresh, multi-account, rotation."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.job_sources.keys import utc_now

SESSION_POLICY: dict[str, Any] = {
    "ttlSeconds": 3600,
    "refreshIfRemainingSeconds": 300,
    "maxAccounts": 3,
    "storage": "sealed_memory",
    "rotation": "on_refresh_or_manual",
    "secretEnv": "LINKEDIN_SESSION_SECRET",
    "states": ("anonymous", "active", "expiring", "expired", "revoked"),
}

_FORBIDDEN_LOG_KEYS = frozenset({"token", "cookie", "cookies", "li_at", "session", "password", "secret"})


def _secret() -> bytes:
    raw = os.environ.get(str(SESSION_POLICY["secretEnv"])) or "ajas-dev-linkedin-session"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _xor(data: bytes, key: bytes) -> bytes:
    stream = hashlib.sha256(key).digest()
    while len(stream) < len(data):
        stream += hashlib.sha256(stream[-32:]).digest()
    return bytes(a ^ b for a, b in zip(data, stream, strict=False))


def seal_token(token: str) -> dict[str, str]:
    raw = (token or "").encode("utf-8")
    nonce = os.urandom(16)
    key = _secret()
    cipher = _xor(raw, key + nonce)
    mac = hmac.new(key, nonce + cipher, hashlib.sha256).hexdigest()
    return {
        "nonce": nonce.hex(),
        "cipher": cipher.hex(),
        "mac": mac,
        "tokenHash": hashlib.sha256(raw).hexdigest(),
    }


def unseal_token(envelope: dict[str, str]) -> str:
    key = _secret()
    nonce = bytes.fromhex(envelope["nonce"])
    cipher = bytes.fromhex(envelope["cipher"])
    mac = hmac.new(key, nonce + cipher, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, envelope.get("mac") or ""):
        raise ValueError("session envelope mac mismatch")
    return _xor(cipher, key + nonce).decode("utf-8")


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


class SealedSessionStore:
    """In-memory sealed sessions. Tokens are never returned by public APIs."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] = {}

    def reset(self) -> None:
        self._rows.clear()

    def put(self, account_id: str, token: str, *, ttl_seconds: int | None = None) -> dict[str, Any]:
        if len(self._rows) >= int(SESSION_POLICY["maxAccounts"]) and account_id not in self._rows:
            raise ValueError("max LinkedIn accounts reached")
        ttl = int(SESSION_POLICY["ttlSeconds"] if ttl_seconds is None else ttl_seconds)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl)
        envelope = seal_token(token)
        self._rows[account_id] = {
            "accountId": account_id,
            "createdAt": now.isoformat().replace("+00:00", "Z"),
            "expiresAt": expires.isoformat().replace("+00:00", "Z"),
            "rotatedAt": utc_now(),
            "status": "active",
            "version": int(self._rows.get(account_id, {}).get("version") or 0) + 1,
            "envelope": envelope,
        }
        return self.public(account_id)

    def public(self, account_id: str) -> dict[str, Any]:
        row = self._rows.get(account_id)
        if not row:
            return {"accountId": account_id, "status": "anonymous", "remainingSeconds": 0}
        remaining = max(0, int((_parse(row["expiresAt"]) - datetime.now(timezone.utc)).total_seconds()))
        status = row["status"]
        if status != "revoked":
            if remaining <= 0:
                status = "expired"
            elif remaining <= int(SESSION_POLICY["refreshIfRemainingSeconds"]):
                status = "expiring"
            else:
                status = "active"
            row["status"] = status
        out = {
            "accountId": account_id,
            "status": status,
            "createdAt": row["createdAt"],
            "expiresAt": row["expiresAt"],
            "rotatedAt": row["rotatedAt"],
            "version": row["version"],
            "remainingSeconds": remaining,
            "tokenHash": row["envelope"]["tokenHash"],
        }
        for key in _FORBIDDEN_LOG_KEYS:
            out.pop(key, None)
        return out

    def list_accounts(self) -> list[dict[str, Any]]:
        return [self.public(account_id) for account_id in self._rows]

    def refresh(self, account_id: str, token: str | None = None) -> dict[str, Any]:
        row = self._rows.get(account_id)
        if not row or row["status"] == "revoked":
            raise ValueError("session missing or revoked")
        current = token or unseal_token(row["envelope"])
        return self.put(account_id, current)

    def rotate(self, account_id: str, token: str) -> dict[str, Any]:
        if account_id not in self._rows:
            raise ValueError("session missing")
        return self.put(account_id, token)

    def revoke(self, account_id: str) -> dict[str, Any]:
        row = self._rows.get(account_id)
        if not row:
            return {"accountId": account_id, "status": "anonymous"}
        row["status"] = "revoked"
        row["envelope"] = seal_token(f"revoked:{uuid4().hex}")
        return self.public(account_id)

    def unlock(self, account_id: str) -> str:
        """Runtime-only. Callers must not log the return value."""
        row = self._rows.get(account_id)
        if not row or row["status"] == "revoked":
            raise ValueError("session missing or revoked")
        if self.public(account_id)["status"] == "expired":
            raise ValueError("session expired")
        return unseal_token(row["envelope"])


STORE = SealedSessionStore()


def reset() -> None:
    STORE.reset()
