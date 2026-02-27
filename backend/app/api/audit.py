"""
app/api/audit.py — Audit chain query and verification endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_token_context, TokenContext
from app.models.base import get_db
from app.services.audit_service import audit_service

router = APIRouter()


@router.get("/events", summary="Get audit events for tenant")
async def get_audit_events(
    limit: int = Query(default=100, ge=1, le=1000),
    workflow_id: Optional[str] = Query(default=None),
    ctx: TokenContext = Depends(get_token_context),
    db: AsyncSession = Depends(get_db),
):
    events = await audit_service.get_events(db, ctx.tenant_id, workflow_id, limit)
    return {
        "tenant_id": ctx.tenant_id,
        "count": len(events),
        "events": events,
    }


@router.get("/verify", summary="Verify audit chain integrity")
async def verify_audit_chain(ctx: TokenContext = Depends(get_token_context)):
    return await audit_service.verify_chain(ctx.tenant_id)


@router.get("/replay", summary="Replay all audit events for tenant")
async def replay_audit(ctx: TokenContext = Depends(get_token_context)):
    events = await audit_service.replay(ctx.tenant_id)
    return {"tenant_id": ctx.tenant_id, "count": len(events), "events": events}
