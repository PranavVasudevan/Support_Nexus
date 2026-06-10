"""
Authentication — password hashing (bcrypt) + JWT tokens.
═════════════════════════════════════════════════════════
Login/register return a signed JWT carrying {sub, username, role}. Protected
endpoints use the FastAPI dependencies below to validate the token and (for
admin routes) enforce the role — server-side, not just hidden in the UI.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import settings

_ALGO = "HS256"
_bearer = HTTPBearer(auto_error=False)


# ── Passwords ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ── Tokens ────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, username: str, role: str,
                        department: str = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "department": department,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGO)


def _decode(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGO])


# ── FastAPI dependencies ────────────────────────────────────────────────────────

async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Require a valid token; return {id, username, role}."""
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated")
    try:
        data = _decode(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"id": data.get("sub"), "username": data.get("username"),
            "role": data.get("role", "client"), "department": data.get("department")}


async def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict]:
    """Return the user if a valid token is present, else None (no error)."""
    if creds is None:
        return None
    try:
        data = _decode(creds.credentials)
    except Exception:
        return None
    return {"id": data.get("sub"), "username": data.get("username"),
            "role": data.get("role", "client"), "department": data.get("department")}


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admin access required")
    return user


async def require_staff(user: dict = Depends(get_current_user)) -> dict:
    """Admin OR a department agent. Department agents are scoped to their
    own categories by the endpoint that uses this dependency."""
    if user.get("role") not in ("admin", "department"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Staff access required")
    return user
