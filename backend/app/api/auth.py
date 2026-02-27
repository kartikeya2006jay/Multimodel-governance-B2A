"""
app/api/auth.py — Authentication: issue tokens for users/admin.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import List, Optional

from app.core.identity import create_access_token, hash_password, verify_password
from app.registry.role_registry import role_registry

from app.models.base import get_db
from app.services.user_service import user_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
    tenant_id: str = "default"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    tenant_id: str
    role: str
    scopes: List[str]


@router.post("/signup", response_model=TokenResponse, summary="Register a new admin user")
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    existing = await user_service.get_by_username(db, body.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken.")

    user = await user_service.create_user(
        db, 
        username=body.username, 
        email=body.email, 
        password=body.password, 
        tenant_id=body.tenant_id
    )
    
    scopes = role_registry.get_scopes(user.role, user.tenant_id)
    token = create_access_token(
        subject=user.username,
        tenant_id=user.tenant_id,
        scopes=scopes,
        role=user.role,
    )
    
    return TokenResponse(
        access_token=token,
        username=user.username,
        tenant_id=user.tenant_id,
        role=user.role,
        scopes=scopes,
    )


@router.post("/login", response_model=TokenResponse, summary="Log in and get token")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await user_service.authenticate(db, body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    scopes = role_registry.get_scopes(user.role, user.tenant_id)
    token = create_access_token(
        subject=user.username,
        tenant_id=user.tenant_id,
        scopes=scopes,
        role=user.role,
    )
    
    return TokenResponse(
        access_token=token,
        username=user.username,
        tenant_id=user.tenant_id,
        role=user.role,
        scopes=scopes,
    )


@router.get("/roles", summary="List available roles and scopes")
async def list_roles():
    return role_registry.list_roles()
