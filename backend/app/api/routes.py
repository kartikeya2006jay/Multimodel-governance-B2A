"""
app/api/routes.py — Master API router mounts all sub-routers.
"""

from fastapi import APIRouter

from app.api.agents import router as agents_router
from app.api.workflows import router as workflows_router
from app.api.billing import router as billing_router
from app.api.audit import router as audit_router
from app.api.policy import router as policy_router
from app.api.auth import router as auth_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(agents_router, prefix="/agents", tags=["Agents"])
api_router.include_router(workflows_router, prefix="/workflows", tags=["Workflows"])
api_router.include_router(billing_router, prefix="/billing", tags=["Billing"])
api_router.include_router(audit_router, prefix="/audit", tags=["Audit"])
api_router.include_router(policy_router, prefix="/policy", tags=["Policy"])
