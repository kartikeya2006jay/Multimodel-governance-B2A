"""
app/core/workflow_engine.py — Async workflow state machine.
Supports: pending → approved → running → completed | failed | rejected
Orchestrates agent execution sequence via the dispatcher.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


# Valid state transitions
TRANSITIONS: Dict[WorkflowStatus, List[WorkflowStatus]] = {
    WorkflowStatus.PENDING: [WorkflowStatus.APPROVED, WorkflowStatus.REJECTED],
    WorkflowStatus.APPROVED: [WorkflowStatus.RUNNING, WorkflowStatus.REJECTED],
    WorkflowStatus.RUNNING: [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED],
    WorkflowStatus.COMPLETED: [],
    WorkflowStatus.FAILED: [],
    WorkflowStatus.REJECTED: [],
}


class WorkflowStateError(Exception):
    pass


class WorkflowContext:
    """Mutable state container passed through the agent execution chain."""

    def __init__(
        self,
        workflow_id: str,
        workflow_type: str,
        tenant_id: str,
        initiator: str,
        initial_context: Dict[str, Any],
    ):
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type
        self.tenant_id = tenant_id
        self.initiator = initiator
        self.status = WorkflowStatus.PENDING
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.context: Dict[str, Any] = dict(initial_context)
        self.agent_results: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
        self.reserve_id: Optional[str] = None
        self.total_cost: float = 0.0

    def transition(self, new_status: WorkflowStatus) -> None:
        allowed = TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise WorkflowStateError(
                f"Invalid transition: {self.status} → {new_status}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        log.info(
            "workflow.transition",
            workflow_id=self.workflow_id,
            from_status=self.status.value,
            to_status=new_status.value,
        )
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def record_agent_result(self, agent_name: str, result: dict) -> None:
        self.agent_results.append(
            {
                "agent_name": agent_name,
                "result": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        # Merge result into shared context for next agent
        self.context.update(result)

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type,
            "tenant_id": self.tenant_id,
            "initiator": self.initiator,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "context": self.context,
            "agent_results": self.agent_results,
            "error": self.error,
            "total_cost": self.total_cost,
        }


class WorkflowEngine:
    """
    Creates and manages workflow contexts.
    Actual orchestration (routing + agent execution) is handled
    by the Dispatcher in the mesh layer.
    """

    def __init__(self):
        self._workflows: Dict[str, WorkflowContext] = {}

    def create(
        self,
        workflow_type: str,
        tenant_id: str,
        initiator: str,
        context: Dict[str, Any],
        workflow_id: Optional[str] = None,
    ) -> WorkflowContext:
        wf_id = workflow_id or str(uuid.uuid4())
        wf = WorkflowContext(
            workflow_id=wf_id,
            workflow_type=workflow_type,
            tenant_id=tenant_id,
            initiator=initiator,
            initial_context=context,
        )
        self._workflows[wf_id] = wf
        log.info("workflow.created", workflow_id=wf_id, type=workflow_type, tenant=tenant_id)
        return wf

    def get(self, workflow_id: str) -> Optional[WorkflowContext]:
        return self._workflows.get(workflow_id)

    def list_by_tenant(self, tenant_id: str) -> List[WorkflowContext]:
        return [wf for wf in self._workflows.values() if wf.tenant_id == tenant_id]

    def list_all(self) -> List[WorkflowContext]:
        return list(self._workflows.values())

    def transition(self, workflow_id: str, new_status: WorkflowStatus) -> WorkflowContext:
        wf = self._workflows.get(workflow_id)
        if not wf:
            raise KeyError(f"Workflow {workflow_id} not found.")
        wf.transition(new_status)
        return wf


workflow_engine = WorkflowEngine()
