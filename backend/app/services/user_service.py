"""
app/services/user_service.py — User management and authentication logic.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.user import User
from app.core.identity import hash_password, verify_password

log = structlog.get_logger(__name__)

class UserService:
    async def create_user(
        self, 
        db: AsyncSession, 
        username: str, 
        email: str, 
        password: str, 
        tenant_id: str,
        role: str = "admin"
    ) -> User:
        hashed = hash_password(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed,
            tenant_id=tenant_id,
            role=role
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        log.info("user_service.created", username=username, tenant=tenant_id)
        return user

    async def authenticate(
        self, 
        db: AsyncSession, 
        username: str, 
        password: str
    ) -> Optional[User]:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user:
            return None
        if verify_password(password, user.hashed_password):
            return user
        return None

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

user_service = UserService()
