"""
app/core/security.py — FastAPI auth dependencies, scope enforcement.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.identity import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


# ── Current Token Context ─────────────────────────────────────────

class TokenContext:
    def __init__(self, payload: dict):
        self.subject: str = payload.get("sub", "")
        self.tenant_id: str = payload.get("tenant_id", "")
        self.scopes: List[str] = payload.get("scopes", [])
        self.role: Optional[str] = payload.get("role")
        self.agent_name: Optional[str] = payload.get("agent_name")
        self.jti: str = payload.get("jti", "")

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "*" in self.scopes


# ── FastAPI Dependencies ──────────────────────────────────────────

async def get_token_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> TokenContext:
    """Extract and validate JWT from Authorization header."""
    if credentials is None:
        from app.core.config import settings
        if settings.DEBUG_SKIP_AUTH:
            return TokenContext({
                "sub": "admin:default",
                "tenant_id": "default",
                "scopes": ["*"],
                "role": "admin",
                "jti": "dev-bypass"
            })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        return TokenContext(payload)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_scopes(*required_scopes: str):
    """
    Dependency factory that enforces one or more scopes.

    Usage:
        @router.post("/action", dependencies=[Depends(require_scopes("write:agents"))])
    """
    async def _check(ctx: TokenContext = Depends(get_token_context)):
        for scope in required_scopes:
            if not ctx.has_scope(scope):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required scope: {scope}",
                )
        return ctx

    return _check


def require_tenant(tenant_id: str):
    """Enforce that the token belongs to a specific tenant."""
    async def _check(ctx: TokenContext = Depends(get_token_context)):
        if ctx.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant mismatch.",
            )
        return ctx

    return _check
