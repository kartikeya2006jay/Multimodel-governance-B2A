"""
app/mesh/router.py — Determines agent execution sequence for a workflow.
Routes are configurable per workflow_type; no hardcoded sequences.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)

# Workflow type → ordered list of agent names
# This can be loaded from DB/config at runtime; zero hardcoding
DEFAULT_WORKFLOW_ROUTES: Dict[str, List[str]] = {
    "budget_approval": ["risk", "finance", "llm"],
    "compliance_review": ["legal", "risk", "llm"],
    "deployment_review": ["devops", "risk", "llm"],
    "procurement": ["finance", "legal", "risk"],
    "generic": ["llm"],
}


class WorkflowRouter:
    def __init__(self):
        # tenant_id -> workflow_type -> agent sequence
        self._routes: Dict[str, Dict[str, List[str]]] = {}
        # Global default routes (copied from DEFAULT_WORKFLOW_ROUTES)
        self._global_routes: Dict[str, List[str]] = dict(DEFAULT_WORKFLOW_ROUTES)

    def configure(
        self,
        workflow_type: str,
        agent_sequence: List[str],
        tenant_id: Optional[str] = None,
    ) -> None:
        """Set custom routing for a workflow type (globally or per tenant)."""
        if tenant_id:
            if tenant_id not in self._routes:
                self._routes[tenant_id] = {}
            self._routes[tenant_id][workflow_type] = agent_sequence
        else:
            self._global_routes[workflow_type] = agent_sequence

        log.info(
            "router.configured",
            workflow_type=workflow_type,
            agent_sequence=agent_sequence,
            tenant=tenant_id or "global",
        )

    def resolve(
        self,
        workflow_type: str,
        tenant_id: Optional[str] = None,
    ) -> List[str]:
        """Resolve agent sequence for a workflow type."""
        # Tenant-specific route takes priority
        if tenant_id and tenant_id in self._routes:
            route = self._routes[tenant_id].get(workflow_type)
            if route:
                return list(route)
        # Fall back to global routes
        route = self._global_routes.get(workflow_type)
        if route:
            return list(route)
        # Last resort: generic single-LLM route
        log.warning(
            "router.fallback_to_generic",
            workflow_type=workflow_type,
            tenant=tenant_id,
        )
        return list(self._global_routes.get("generic", ["llm"]))

    def list_routes(self, tenant_id: Optional[str] = None) -> dict:
        base = dict(self._global_routes)
        if tenant_id and tenant_id in self._routes:
            base.update(self._routes[tenant_id])
        return base


workflow_router = WorkflowRouter()
