"""
app/mesh/workflow_state.py — Persists and restores workflow state to/from DB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.workflow_engine import WorkflowContext, WorkflowStatus
from app.models.workflow import WorkflowRecord


class WorkflowStateManager:

    async def save(self, db: AsyncSession, workflow: WorkflowContext) -> WorkflowRecord:
        """Create or update a workflow DB record."""
        result = await db.execute(
            select(WorkflowRecord).where(WorkflowRecord.id == workflow.workflow_id)
        )
        record = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if record is None:
            record = WorkflowRecord(
                id=workflow.workflow_id,
                tenant_id=workflow.tenant_id,
                workflow_type=workflow.workflow_type,
                initiator=workflow.initiator,
                status=workflow.status.value,
                context=workflow.context,
                agent_results=workflow.agent_results,
                error=workflow.error,
                total_cost=workflow.total_cost,
                reserve_id=workflow.reserve_id,
            )
            db.add(record)
        else:
            record.status = workflow.status.value
            record.context = workflow.context
            record.agent_results = workflow.agent_results
            record.error = workflow.error
            record.total_cost = workflow.total_cost
            record.updated_at = now

            if workflow.status in (
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.REJECTED,
            ):
                record.completed_at = now

        await db.commit()
        await db.refresh(record)
        return record

    async def load(
        self, db: AsyncSession, workflow_id: str, tenant_id: str
    ) -> Optional[WorkflowRecord]:
        result = await db.execute(
            select(WorkflowRecord).where(
                WorkflowRecord.id == workflow_id,
                WorkflowRecord.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self, db: AsyncSession, tenant_id: str, limit: int = 50
    ):
        result = await db.execute(
            select(WorkflowRecord)
            .where(WorkflowRecord.tenant_id == tenant_id)
            .order_by(WorkflowRecord.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


workflow_state_manager = WorkflowStateManager()
