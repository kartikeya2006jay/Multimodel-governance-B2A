"""
app/api/agents.py — Agent registration and management endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_token_context, TokenContext
from app.models.base import get_db
from app.services.agent_service import agent_service

router = APIRouter()


class RegisterAgentRequest(BaseModel):
    name: str = Field(..., description="Unique agent name within tenant")
    role: str = Field(..., description="Agent role (finance, legal, risk, devops, llm, ...)")
    scopes: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    cost_per_call: float = Field(default=0.01, ge=0)
    version: str = "1.0.0"


@router.get("", summary="List all agents for the current tenant")
async def list_agents(
    ctx: TokenContext = Depends(get_token_context),
    db: AsyncSession = Depends(get_db),
):
    db_agents = await agent_service.list_agents(db, ctx.tenant_id)
    runtime_agents = await agent_service.get_in_memory_agents(ctx.tenant_id)
    return {
        "tenant_id": ctx.tenant_id,
        "db_agents": [a.to_dict() for a in db_agents],
        "runtime_agents": runtime_agents,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Register a new agent")
async def register_agent(
    body: RegisterAgentRequest,
    ctx: TokenContext = Depends(get_token_context),
    db: AsyncSession = Depends(get_db),
):
    try:
        record = await agent_service.register(
            db=db,
            tenant_id=ctx.tenant_id,
            name=body.name,
            role=body.role,
            scopes=body.scopes,
            description=body.description or "",
            cost_per_call=body.cost_per_call,
            version=body.version,
        )
        return {"status": "registered", "agent": record.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/{agent_id}", summary="Get agent details")
async def get_agent(
    agent_id: str,
    ctx: TokenContext = Depends(get_token_context),
    db: AsyncSession = Depends(get_db),
):
    record = await agent_service.get(db, agent_id, ctx.tenant_id)
    if not record:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return record.to_dict()


@router.delete("/{agent_id}", summary="Deactivate an agent")
async def deactivate_agent(
    agent_id: str,
    ctx: TokenContext = Depends(get_token_context),
    db: AsyncSession = Depends(get_db),
):
    record = await agent_service.deactivate(db, agent_id, ctx.tenant_id)
    if not record:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return {"status": "deactivated", "agent_id": agent_id}
