"""
app/services/audit_service.py — Audit chain query and persistence service.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_chain import AuditEvent, audit_chain_registry
from app.models.audit import AuditRecord


class AuditService:

    async def append(
        self,
        db: AsyncSession,
        tenant_id: str,
        action: str,
        status: str,
        payload: Dict[str, Any],
        workflow_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> dict:
        """Append event to in-memory chain and persist to DB."""
        chain = audit_chain_registry.get_or_create(tenant_id)
        event = chain.append(
            action=action,
            status=status,
            payload=payload,
            workflow_id=workflow_id,
            agent_name=agent_name,
        )

        # Persist to DB
        record = AuditRecord(
            id=event.event_id,
            tenant_id=event.tenant_id,
            workflow_id=event.workflow_id,
            agent_name=event.agent_name,
            action=event.action,
            status=event.status,
            payload=event.payload,
            sequence=event.sequence,
            prev_hash=event.prev_hash,
            event_hash=event.event_hash,
        )
        db.add(record)
        await db.commit()
        return event.to_dict()

    async def get_events(
        self,
        db: AsyncSession,
        tenant_id: str,
        workflow_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        query = (
            select(AuditRecord)
            .where(AuditRecord.tenant_id == tenant_id)
            .order_by(AuditRecord.sequence.asc())
            .limit(limit)
        )
        if workflow_id:
            query = query.where(AuditRecord.workflow_id == workflow_id)

        result = await db.execute(query)
        return [r.to_dict() for r in result.scalars().all()]

    async def verify_chain(self, tenant_id: str) -> dict:
        """Verify the in-memory hash chain for tamper detection."""
        intact = audit_chain_registry.verify_tenant(tenant_id)
        return {
            "tenant_id": tenant_id,
            "chain_intact": intact,
            "status": "ok" if intact else "TAMPER_DETECTED",
        }

    async def replay(self, tenant_id: str) -> List[dict]:
        chain = audit_chain_registry.get_or_create(tenant_id)
        return chain.replay()


audit_service = AuditService()
