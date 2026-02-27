"""
app/services/agent_service.py — Agent CRUD and execution via dispatcher.
Services are the ONLY layer that touch DB and business logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.core.identity import create_agent_identity_token
from app.mesh.dispatcher import dispatcher
from app.models.agent import AgentRecord
from app.registry.agent_registry import agent_registry

log = structlog.get_logger(__name__)


class AgentService:

    async def register(
        self,
        db: AsyncSession,
        tenant_id: str,
        name: str,
        role: str,
        scopes: List[str],
        description: str = "",
        cost_per_call: float = 0.01,
        version: str = "1.0.0",
    ) -> AgentRecord:
        # Check name uniqueness per tenant
        existing = await db.execute(
            select(AgentRecord).where(
                AgentRecord.tenant_id == tenant_id,
                AgentRecord.name == name,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Agent '{name}' already registered for tenant '{tenant_id}'.")

        identity_token = create_agent_identity_token(
            agent_name=name, tenant_id=tenant_id, role=role, scopes=scopes
        )

        record = AgentRecord(
            tenant_id=tenant_id,
            name=name,
            role=role,
            scopes=scopes,
            description=description,
            version=version,
            cost_per_call=cost_per_call,
            identity_token=identity_token,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        log.info("agent_service.registered", agent=name, tenant=tenant_id)
        return record

    async def get(
        self, db: AsyncSession, agent_id: str, tenant_id: str
    ) -> Optional[AgentRecord]:
        result = await db.execute(
            select(AgentRecord).where(
                AgentRecord.id == agent_id,
                AgentRecord.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_agents(
        self, db: AsyncSession, tenant_id: str, active_only: bool = True
    ) -> List[AgentRecord]:
        query = select(AgentRecord).where(AgentRecord.tenant_id == tenant_id)
        if active_only:
            query = query.where(AgentRecord.is_active == True)
        result = await db.execute(query.order_by(AgentRecord.created_at.desc()))
        return list(result.scalars().all())

    async def deactivate(
        self, db: AsyncSession, agent_id: str, tenant_id: str
    ) -> Optional[AgentRecord]:
        record = await self.get(db, agent_id, tenant_id)
        if record:
            record.is_active = False
            await db.commit()
            await db.refresh(record)
        return record

    async def get_in_memory_agents(self, tenant_id: str) -> List[dict]:
        """Return agents registered in-memory (runtime registry)."""
        return [
            {
                "name": a.name,
                "role": a.role,
                "scopes": a.scopes,
                "description": a.description,
                "version": a.version,
            }
            for a in agent_registry.list_all(tenant_id)
        ]


agent_service = AgentService()
