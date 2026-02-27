"""
app/api/workflows.py — Workflow trigger, status, and graph endpoints.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_token_context, TokenContext
from app.models.base import get_db
from app.services.workflow_service import workflow_service
from app.mesh.router import workflow_router

router = APIRouter()


class TriggerWorkflowRequest(BaseModel):
    workflow_type: str = Field(..., description="Type of workflow (budget_approval, compliance_review, ...)")
    context: Dict[str, Any] = Field(default_factory=dict, description="Workflow input context")


class ConfigureRouteRequest(BaseModel):
    workflow_type: str
    agent_sequence: list


@router.post("", status_code=status.HTTP_202_ACCEPTED, summary="Trigger a new workflow")
async def trigger_workflow(
    body: TriggerWorkflowRequest,
    ctx: TokenContext = Depends(get_token_context),
    db: AsyncSession = Depends(get_db),
):
    result = await workflow_service.trigger(
        db=db,
        workflow_type=body.workflow_type,
        tenant_id=ctx.tenant_id,
        initiator=ctx.subject,
        context=body.context,
    )
    return {"status": "accepted", "workflow": result}


@router.get("", summary="List workflows for the current tenant")
async def list_workflows(
    limit: int = 50,
    ctx: TokenContext = Depends(get_token_context),
    db: AsyncSession = Depends(get_db),
):
    workflows = await workflow_service.list_workflows(db, ctx.tenant_id, limit)
    return {"tenant_id": ctx.tenant_id, "count": len(workflows), "workflows": workflows}


@router.get("/routes", summary="List configured workflow routes")
async def list_routes(ctx: TokenContext = Depends(get_token_context)):
    return {
        "tenant_id": ctx.tenant_id,
        "routes": workflow_router.list_routes(ctx.tenant_id),
    }


@router.post("/routes", summary="Configure a custom workflow route")
async def configure_route(
    body: ConfigureRouteRequest,
    ctx: TokenContext = Depends(get_token_context),
):
    workflow_router.configure(body.workflow_type, body.agent_sequence, ctx.tenant_id)
    return {"status": "configured", "workflow_type": body.workflow_type, "sequence": body.agent_sequence}


@router.get("/{workflow_id}", summary="Get workflow status and results")
async def get_workflow(
    workflow_id: str,
    ctx: TokenContext = Depends(get_token_context),
    db: AsyncSession = Depends(get_db),
):
    result = await workflow_service.get(db, workflow_id, ctx.tenant_id)
    if not result:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return result
