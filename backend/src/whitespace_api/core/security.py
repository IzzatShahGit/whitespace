"""Password hashing and token primitives. No database access here."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from whitespace_api.core.config import Settings

_hasher = PasswordHash.recommended()  # Argon2id
# Verified against when an email is unknown, so login takes the same time either way.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> uuid.UUID | None:
    """User id from a valid access token, or None if invalid or expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=[_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def new_refresh_token() -> str:
    """Opaque random token. Only its hash is stored."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
