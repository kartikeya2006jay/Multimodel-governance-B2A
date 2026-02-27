"""
app/services/workflow_service.py — Workflow lifecycle management.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import structlog

from app.core.billing_engine import billing_engine
from app.core.workflow_engine import WorkflowStatus, workflow_engine
from app.mesh.dispatcher import dispatcher
from app.mesh.workflow_state import workflow_state_manager
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


class WorkflowService:

    async def trigger(
        self,
        db: AsyncSession,
        workflow_type: str,
        tenant_id: str,
        initiator: str,
        context: Dict[str, Any],
    ) -> dict:
        """
        Full workflow lifecycle:
        1. Create workflow context
        2. Reserve billing
        3. Approve (auto) and run through agent mesh
        4. Persist final state
        5. Commit or void billing reserve
        """
        # Inject meta into context for agent use
        context["_tenant_id"] = tenant_id

        wf = workflow_engine.create(
            workflow_type=workflow_type,
            tenant_id=tenant_id,
            initiator=initiator,
            context=context,
        )
        context["_workflow_id"] = wf.workflow_id

        # Reserve billing
        reserve_id = billing_engine.reserve_workflow_cost(
            tenant_id=tenant_id,
            workflow_id=wf.workflow_id,
        )
        wf.reserve_id = reserve_id

        # Auto-approve (governance layer can intercept here for human-in-loop)
        wf.transition(WorkflowStatus.APPROVED)

        # Persist initial state
        await workflow_state_manager.save(db, wf)

        # Execute in background task
        asyncio.create_task(self._run_and_persist(db, wf))

        return wf.to_dict()

    async def _run_and_persist(self, db: AsyncSession, wf) -> None:
        try:
            await dispatcher.run_workflow(wf)
        except Exception as exc:
            log.error("workflow_service.execution_error", error=str(exc))
            wf.error = str(exc)
            wf.status = WorkflowStatus.FAILED

        # Commit or void billing reserve
        if wf.reserve_id:
            if wf.status == WorkflowStatus.COMPLETED:
                billing_engine.commit_reserve(wf.reserve_id)
            else:
                billing_engine.void_reserve(wf.reserve_id)

        # Persist final state
        from app.models.base import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await workflow_state_manager.save(session, wf)

    async def get(
        self, db: AsyncSession, workflow_id: str, tenant_id: str
    ) -> Optional[dict]:
        # Try in-memory first (fastest)
        wf = workflow_engine.get(workflow_id)
        if wf and wf.tenant_id == tenant_id:
            return wf.to_dict()
        # Fallback to DB
        record = await workflow_state_manager.load(db, workflow_id, tenant_id)
        return record.to_dict() if record else None

    async def list_workflows(
        self, db: AsyncSession, tenant_id: str, limit: int = 50
    ) -> List[dict]:
        records = await workflow_state_manager.list_by_tenant(db, tenant_id, limit)
        return [r.to_dict() for r in records]


workflow_service = WorkflowService()
