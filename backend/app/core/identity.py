"""
app/core/identity.py — Agent & user identity, JWT token management.
Issues signed tokens with embedded scopes and tenant context.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Token Payloads ────────────────────────────────────────────────

class TokenPayload:
    def __init__(
        self,
        sub: str,
        tenant_id: str,
        scopes: List[str],
        agent_name: Optional[str] = None,
        role: Optional[str] = None,
        exp: Optional[datetime] = None,
        jti: Optional[str] = None,
    ):
        self.sub = sub
        self.tenant_id = tenant_id
        self.scopes = scopes
        self.agent_name = agent_name
        self.role = role
        self.exp = exp or (
            datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        )
        self.jti = jti or str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sub": self.sub,
            "tenant_id": self.tenant_id,
            "scopes": self.scopes,
            "agent_name": self.agent_name,
            "role": self.role,
            "exp": self.exp,
            "jti": self.jti,
            "iat": datetime.now(timezone.utc),
        }


# ── Token Operations ─────────────────────────────────────────────

def create_access_token(
    subject: str,
    tenant_id: str,
    scopes: List[str],
    role: Optional[str] = None,
    agent_name: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token."""
    payload = TokenPayload(
        sub=subject,
        tenant_id=tenant_id,
        scopes=scopes,
        role=role,
        agent_name=agent_name,
    )
    if expires_delta:
        payload.exp = datetime.now(timezone.utc) + expires_delta

    return jwt.encode(
        payload.to_dict(),
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT token. Raises JWTError on failure."""
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def create_agent_identity_token(
    agent_name: str,
    tenant_id: str,
    role: str,
    scopes: List[str],
) -> str:
    """Issue a long-lived identity token for a registered agent."""
    return create_access_token(
        subject=f"agent:{agent_name}",
        tenant_id=tenant_id,
        scopes=scopes,
        role=role,
        agent_name=agent_name,
        expires_delta=timedelta(days=365),
    )


# ── Password Utilities ────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def generate_api_key() -> str:
    """Generate a cryptographically random API key."""
    import secrets
    return f"b2a_{secrets.token_urlsafe(40)}"
