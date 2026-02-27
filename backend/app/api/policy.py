"""
app/api/policy.py — Policy rule management and evaluation endpoints.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_token_context, TokenContext
from app.models.base import get_db
from app.services.policy_service import policy_service

router = APIRouter()


class PolicyRule(BaseModel):
    name: str
    required_scopes: List[str] = Field(default_factory=list)
    allowed_roles: List[str] = Field(default_factory=list)
    blocked_actions: List[str] = Field(default_factory=list)


class LoadRulesRequest(BaseModel):
    rules: List[Dict[str, Any]]


class EvaluateRequest(BaseModel):
    agent_name: str
    action: str
    scopes: List[str]
    role: Optional[str] = None
    workflow_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/rules", summary="Get policy rules for tenant")
async def get_rules(ctx: TokenContext = Depends(get_token_context)):
    return {"tenant_id": ctx.tenant_id, "rules": policy_service.get_rules(ctx.tenant_id)}


@router.post("/rules", summary="Add a policy rule")
async def add_rule(
    rule: PolicyRule,
    ctx: TokenContext = Depends(get_token_context),
):
    return policy_service.add_rule(ctx.tenant_id, rule.model_dump())


@router.put("/rules", summary="Load (replace) all policy rules")
async def load_rules(
    body: LoadRulesRequest,
    ctx: TokenContext = Depends(get_token_context),
):
    return policy_service.load_rules(ctx.tenant_id, body.rules)


@router.delete("/rules", summary="Clear all policy rules for tenant")
async def clear_rules(ctx: TokenContext = Depends(get_token_context)):
    return policy_service.clear_rules(ctx.tenant_id)


@router.post("/evaluate", summary="Evaluate a policy check on demand")
async def evaluate_policy(
    body: EvaluateRequest,
    ctx: TokenContext = Depends(get_token_context),
):
    return policy_service.evaluate(
        tenant_id=ctx.tenant_id,
        agent_name=body.agent_name,
        action=body.action,
        scopes=body.scopes,
        role=body.role,
        workflow_id=body.workflow_id,
        metadata=body.metadata,
    )
