"""JWT authentication and password hashing utilities."""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from .config import settings

_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False
)


def _generate_salt() -> str:
    return os.urandom(32).hex()


def hash_password(plain: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    salt = _generate_salt()
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 600_000)
    return f"{salt}${dk.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its PBKDF2-HMAC-SHA256 hash."""
    try:
        salt, stored = hashed.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 600_000)
    return hmac.compare_digest(dk.hex(), stored)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.jwt_algorithm
    )


async def get_current_user(
    token: Optional[str] = Depends(_oauth2_scheme),
) -> Optional[str]:
    """Extract username from JWT. Returns None when no token is provided
    (public endpoints) and raises 401 on an invalid token."""
    if token is None:
        return None
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")
