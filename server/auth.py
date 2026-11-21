"""Autenticación JWT y RBAC."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import settings
from store import get_user_by_email

security = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS = {
    "admin": {"view", "export", "delete", "policy", "users", "audit"},
    "auditor": {"view", "export", "audit"},
    "viewer": {"view"},
}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, hexd = stored.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
        return hmac.compare_digest(digest.hex(), hexd)
    except ValueError:
        return False


def create_token(user: dict[str, Any]) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_HOURS)
    payload = {"sub": user["email"], "role": user["role"], "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="Token inválido") from e


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="No autenticado")
    data = decode_token(creds.credentials)
    user = get_user_by_email(data["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


def require_perm(perm: str):
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        role = user.get("role", "viewer")
        if perm not in ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(status_code=403, detail="Permiso denegado")
        return user

    return _dep


def audit_from_request(request: Request, user: dict, action: str, detail: str = "") -> None:
    from store import log_admin_action

    ip = request.client.host if request.client else "?"
    log_admin_action(user["email"], action, f"{detail} ip={ip}")
