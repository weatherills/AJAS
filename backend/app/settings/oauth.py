"""Microsoft identity OAuth (authorization code + PKCE)."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol

REQUIRED_SCOPES = ["offline_access", "Mail.Read"]


class GraphError(Exception):
    def __init__(self, message: str, *, status_code: int = 502, code: str = "GRAPH_ERROR"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str
    tenant_id: str | None = None
    account_id: str | None = None


class TokenExchanger(Protocol):
    def exchange(self, *, code: str, redirect_uri: str, code_verifier: str) -> TokenSet: ...


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def new_state() -> str:
    return secrets.token_urlsafe(24)


def authorize_url(
    *,
    tenant: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    scopes: list[str] | None = None,
) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": " ".join(scopes or REQUIRED_SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return (
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?"
        + urllib.parse.urlencode(params)
    )


class MicrosoftTokenExchanger:
    def __init__(self, *, tenant: str, client_id: str, client_secret: str):
        self.tenant = tenant
        self.client_id = client_id
        self.client_secret = client_secret

    def exchange(self, *, code: str, redirect_uri: str, code_verifier: str) -> TokenSet:
        body = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
        ).encode()
        url = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise GraphError("Microsoft token exchange failed", status_code=502, code="GRAPH_ERROR") from exc
        except urllib.error.URLError as exc:
            raise GraphError("Microsoft token endpoint unreachable", status_code=502, code="GRAPH_ERROR") from exc
        if not payload.get("refresh_token"):
            raise GraphError("Token response missing refresh_token", status_code=502, code="GRAPH_ERROR")
        claims = jwt_claims(payload.get("id_token"))
        return TokenSet(
            access_token=payload.get("access_token") or "",
            refresh_token=payload["refresh_token"],
            expires_in=int(payload.get("expires_in") or 3600),
            scope=payload.get("scope") or " ".join(REQUIRED_SCOPES),
            tenant_id=payload.get("tenant_id") or claims.get("tid"),
            account_id=(
                claims.get("preferred_username")
                or claims.get("upn")
                or claims.get("oid")
            ),
        )


def jwt_claims(token: str | None) -> dict:
    """Decode a JWT payload without verifying the signature (already issued to us)."""
    if not token or token.count(".") < 2:
        return {}
    payload = token.split(".")[1]
    padded = payload + "=" * (-len(payload) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
