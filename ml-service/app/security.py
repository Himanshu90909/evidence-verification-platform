"""API-key authentication between the web API layer and this ML service."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Header, HTTPException, status

import app.config as config


def _key_matches(provided: str, expected: str) -> bool:
    """Constant-time comparison; keys may be long so hash first."""
    return hmac.compare_digest(
        hashlib.sha256(provided.encode()).digest(), hashlib.sha256(expected.encode()).digest()
    )


async def require_api_key(
    x_api_key: str = Header(default="", alias="X-API-Key"),
    authorization: str = Header(default=""),
) -> str:
    """FastAPI dependency: enforce service authentication on every route."""
    settings = config.get_settings()
    if settings.allow_unauthenticated:
        return "anonymous"
    token = x_api_key
    if not token and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    if token and _key_matches(token, settings.ml_api_key):
        return "service"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )


def generate_api_key() -> str:
    """Helper to generate a strong service key for deployment guides."""
    return "evp_" + secrets.token_urlsafe(32)
