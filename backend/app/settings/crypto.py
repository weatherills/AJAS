"""Seal OAuth tokens before they are persisted. Never log plaintext."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os


def seal_token(plain: str | None, secret: str) -> str | None:
    if plain is None:
        return None
    if plain.startswith("enc."):
        return plain
    key = hashlib.sha256((secret or "dev-settings-token-key").encode()).digest()
    nonce = os.urandom(16)
    raw = plain.encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    tag = hmac.new(key, nonce + xored, hashlib.sha256).digest()[:16]
    return "enc." + base64.urlsafe_b64encode(nonce + tag + xored).decode("ascii")


def open_token(sealed: str | None, secret: str) -> str | None:
    if sealed is None:
        return None
    if not sealed.startswith("enc."):
        return sealed
    key = hashlib.sha256((secret or "dev-settings-token-key").encode()).digest()
    blob = base64.urlsafe_b64decode(sealed[4:].encode("ascii"))
    nonce, tag, xored = blob[:16], blob[16:32], blob[32:]
    expected = hmac.new(key, nonce + xored, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected):
        raise ValueError("token mac mismatch")
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(xored)).decode("utf-8")
