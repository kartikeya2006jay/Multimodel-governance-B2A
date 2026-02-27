"""
app/api/billing.py — Billing ledger and summary endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_token_context, TokenContext
from app.models.base import get_db
from app.services.billing_service import billing_service

router = APIRouter()


@router.get("/summary", summary="Get billing summary for tenant")
async def billing_summary(
    ctx: TokenContext = Depends(get_token_context),
    db: AsyncSession = Depends(get_db),
):
    return await billing_service.get_summary(db, ctx.tenant_id)


@router.get("/balance", summary="Get current balance for tenant")
async def billing_balance(ctx: TokenContext = Depends(get_token_context)):
    return await billing_service.get_balance(ctx.tenant_id)


@router.get("/ledger", summary="Get ledger entries for tenant")
async def billing_ledger(
    limit: int = Query(default=100, ge=1, le=1000),
    workflow_id: Optional[str] = Query(default=None),
    ctx: TokenContext = Depends(get_token_context),
    db: AsyncSession = Depends(get_db),
):
    entries = await billing_service.get_ledger(db, ctx.tenant_id, limit, workflow_id)
    return {
        "tenant_id": ctx.tenant_id,
        "count": len(entries),
        "entries": entries,
    }
