"""Access gate.

A shared code, exchanged for a signed token. Enough to keep an internal tool
off the open web; it is not per-user identity, so it tells you that someone
with a valid code acted, not who.

Enforcement is server-side. The static page is public — anyone can fetch the
HTML and JavaScript — but every API route requires a token, so no data is
reachable without a code.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from .config import settings

TOKEN_TTL_SECONDS = 60 * 60 * 12   # a working day; re-enter the code after that
HEADER = "x-venmito-token"


def _secret() -> bytes:
    """Sign with the configured secret, or derive one from the codes.

    Deriving means a deployment that only sets codes still gets stable
    signatures, and rotating a code invalidates the tokens issued from it.
    """
    if settings.secret_key:
        return settings.secret_key.encode()
    return hashlib.sha256(",".join(settings.access_codes).encode()).digest()


def _sign(payload: bytes) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(_secret(), payload, hashlib.sha256).digest()).decode().rstrip("=")


def code_is_valid(code: str) -> bool:
    candidate = (code or "").strip().upper()
    # compare_digest against each code: constant time, no early exit on a
    # partial match.
    return any(hmac.compare_digest(candidate, valid) for valid in settings.access_codes)


def issue_token(code: str) -> str:
    payload = json.dumps({"c": code.strip().upper(), "t": int(time.time())},
                         separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{body}.{_sign(payload)}"


def token_is_valid(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    body, _, signature = token.partition(".")
    try:
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    except Exception:
        return False
    if not hmac.compare_digest(signature, _sign(payload)):
        return False
    try:
        claims = json.loads(payload)
    except Exception:
        return False
    # A code removed from the configuration stops working immediately.
    if not code_is_valid(claims.get("c", "")):
        return False
    return (time.time() - claims.get("t", 0)) < TOKEN_TTL_SECONDS
