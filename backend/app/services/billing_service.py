"""
app/services/billing_service.py — Billing query and management service.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.billing_engine import billing_engine
from app.models.ledger import LedgerRecord


class BillingService:
    async def get_balance(self, tenant_id: str) -> dict:
        balance = billing_engine.get_balance(tenant_id)
        return {
            "tenant_id": tenant_id,
            "balance_usd": str(balance),
            "currency": "USD",
        }

    async def get_ledger(
        self,
        db: AsyncSession,
        tenant_id: str,
        limit: int = 100,
        workflow_id: Optional[str] = None,
    ) -> List[dict]:
        query = (
            select(LedgerRecord)
            .where(LedgerRecord.tenant_id == tenant_id)
            .order_by(LedgerRecord.created_at.desc())
            .limit(limit)
        )
        if workflow_id:
            query = query.where(LedgerRecord.workflow_id == workflow_id)
        result = await db.execute(query)
        return [r.to_dict() for r in result.scalars().all()]

    async def get_summary(
        self, db: AsyncSession, tenant_id: str
    ) -> dict:
        # Aggregates
        stats = await db.execute(
            select(
                func.count(LedgerRecord.id).label("total_entries"),
                func.sum(LedgerRecord.amount).label("total_amount"),
                func.count(LedgerRecord.workflow_id.distinct()).label("total_workflows"),
            ).where(LedgerRecord.tenant_id == tenant_id)
        )
        row = stats.one()
        
        # Recent entries for the UI
        entries = await self.get_ledger(db, tenant_id, limit=20)
        
        in_memory_balance = billing_engine.get_balance(tenant_id)
        
        # Simulated Business Tracking Metrics
        budget = 500.0  # Monthly budget for demo
        actual_spend = float(row.total_amount or 0)
        efficiency = 98.4 if actual_spend > 0 else 100.0
        forecast = actual_spend * 1.5 # Simple forecasting
        
        return {
            "tenant_id": tenant_id,
            "total_billed": actual_spend,
            "audit_count": row.total_entries or 0,
            "entries": entries,
            "current_balance_usd": float(in_memory_balance),
            "total_workflows": row.total_workflows or 0,
            # Business Track Extensions
            "budget_limit": budget,
            "efficiency_score": efficiency,
            "forecast_spend": forecast,
            "status": "healthy" if actual_spend < budget else "over_budget"
        }

    async def charge_agent_call(
        self,
        db: AsyncSession,
        tenant_id: str,
        agent_name: str,
        workflow_id: Optional[str] = None,
        cost_override: Optional[float] = None,
    ) -> dict:
        entry = billing_engine.charge_agent_call(
            tenant_id=tenant_id,
            agent_name=agent_name,
            workflow_id=workflow_id,
            cost_override=cost_override,
        )
        record = await self.persist_entry(db, entry)
        return record.to_dict()

    async def charge_llm_tokens(
        self,
        db: AsyncSession,
        tenant_id: str,
        agent_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        workflow_id: Optional[str] = None,
        cost_per_1k_override: Optional[float] = None,
    ) -> dict:
        entry = billing_engine.charge_llm_tokens(
            tenant_id=tenant_id,
            agent_name=agent_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
            workflow_id=workflow_id,
            cost_per_1k_override=cost_per_1k_override,
        )
        record = await self.persist_entry(db, entry)
        return record.to_dict()

    async def reserve_workflow_cost(
        self,
        db: AsyncSession,
        tenant_id: str,
        workflow_id: str,
        estimated_cost: Optional[float] = None,
    ) -> str:
        reserve_id = billing_engine.reserve_workflow_cost(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            estimated_cost=estimated_cost,
        )
        # Find the entry in engine to persist it
        entry = billing_engine._reserves.get(reserve_id)
        if entry:
            await self.persist_entry(db, entry)
        return reserve_id

    async def commit_reserve(self, db: AsyncSession, reserve_id: str) -> None:
        entry = billing_engine.commit_reserve(reserve_id)
        if entry:
            await self.persist_entry(db, entry)

    async def void_reserve(self, db: AsyncSession, reserve_id: str) -> None:
        entry = billing_engine.void_reserve(reserve_id)
        if entry:
            await self.persist_entry(db, entry)

    async def persist_entry(
        self, db: AsyncSession, entry
    ) -> LedgerRecord:
        record = LedgerRecord(
            tenant_id=entry.tenant_id,
            workflow_id=entry.workflow_id,
            agent_name=entry.agent_name,
            entry_type=entry.entry_type.value,
            amount=float(entry.amount),
            currency=entry.currency,
            description=entry.description,
            reference=entry.reference,
            metadata_=entry.metadata,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record


billing_service = BillingService()
