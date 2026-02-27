"""
app/mesh/dispatcher.py — Core agent dispatcher.
Wraps agent.execute() with policy check, billing, audit logging, and observability.
All agent invocations MUST flow through this dispatcher.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import structlog

from app.core.audit_chain import audit_chain_registry
from app.core.billing_engine import billing_engine
from app.core.observability import (
    record_audit_event,
    record_billing_charge,
    record_error,
    record_policy_violation,
    track_agent_execution,
)
from app.core.policy_engine import PolicyContext, policy_engine
from app.core.workflow_engine import WorkflowContext
from app.mesh.message_bus import message_bus
from app.registry.agent_registry import agent_registry

log = structlog.get_logger(__name__)


class DispatchError(Exception):
    pass


class PolicyDeniedError(DispatchError):
    pass


class AgentDispatcher:
    """
    Dispatches workflow execution to the appropriate agents in sequence.
    Each call goes through:
      1. Policy validation
      2. Billing reserve/charge
      3. Audit log
      4. Agent execution
      5. Result recording
    """

    async def dispatch(
        self,
        workflow: WorkflowContext,
        agent_name: str,
    ) -> Dict[str, Any]:
        tenant_id = workflow.tenant_id
        workflow_id = workflow.workflow_id

        agent = agent_registry.get(agent_name, tenant_id)
        if agent is None:
            raise DispatchError(
                f"Agent '{agent_name}' not found for tenant '{tenant_id}'."
            )

        # ── 1. Policy Check ───────────────────────────────────────
        policy_ctx = PolicyContext(
            tenant_id=tenant_id,
            agent_name=agent_name,
            action="agent.execute",
            scopes=agent.scopes,
            role=agent.role,
            workflow_id=workflow_id,
            metadata=workflow.context,
        )
        policy_result = policy_engine.evaluate(policy_ctx)

        if not policy_result.allowed:
            record_policy_violation(tenant_id, agent_name, "agent.execute")
            audit_chain_registry.get_or_create(tenant_id).append(
                action=f"agent.{agent_name}.policy_denied",
                status="denied",
                payload={"reason": policy_result.reason, "violations": policy_result.violations},
                workflow_id=workflow_id,
                agent_name=agent_name,
            )
            record_audit_event(tenant_id)
            raise PolicyDeniedError(policy_result.reason)

        # ── 2. Billing: charge per agent call ─────────────────────
        from app.models.base import AsyncSessionLocal
        from app.services.billing_service import billing_service
        async with AsyncSessionLocal() as db:
            billed = await billing_service.charge_agent_call(
                db=db,
                tenant_id=tenant_id,
                agent_name=agent_name,
                workflow_id=workflow_id,
                cost_override=getattr(agent, "cost_per_call", None),
            )
            record_billing_charge(tenant_id, float(billed["amount"]))
            workflow.total_cost += float(billed["amount"])

        # ── 3. Pre-execution Audit ────────────────────────────────
        chain = audit_chain_registry.get_or_create(tenant_id)
        chain.append(
            action=f"agent.{agent_name}.start",
            status="running",
            payload={"context_keys": list(workflow.context.keys())},
            workflow_id=workflow_id,
            agent_name=agent_name,
        )
        record_audit_event(tenant_id)

        # ── 4. Execute ────────────────────────────────────────────
        result: Dict[str, Any] = {}
        error: Optional[Exception] = None
        start = time.perf_counter()

        try:
            with track_agent_execution(tenant_id, agent_name):  # type: ignore
                result = await agent.execute(workflow.context)
        except Exception as exc:
            error = exc
            record_error(tenant_id, f"agent.{agent_name}", type(exc).__name__)

        elapsed = time.perf_counter() - start

        # ── 5. Post-execution Audit ───────────────────────────────
        if error:
            chain.append(
                action=f"agent.{agent_name}.error",
                status="failed",
                payload={"error": str(error), "latency_ms": round(elapsed * 1000)},
                workflow_id=workflow_id,
                agent_name=agent_name,
            )
            record_audit_event(tenant_id)
            raise DispatchError(f"Agent '{agent_name}' failed: {error}") from error

        chain.append(
            action=f"agent.{agent_name}.complete",
            status="completed",
            payload={"result_keys": list(result.keys()), "latency_ms": round(elapsed * 1000)},
            workflow_id=workflow_id,
            agent_name=agent_name,
        )
        record_audit_event(tenant_id)

        # Record result in workflow context
        workflow.record_agent_result(agent_name, result)

        # Emit event to message bus
        await message_bus.emit(
            event_type="agent.completed",
            tenant_id=tenant_id,
            source=agent_name,
            payload={"agent": agent_name, "workflow_id": workflow_id, "result": result},
            correlation_id=workflow_id,
        )

        log.info(
            "dispatcher.agent_completed",
            agent=agent_name,
            workflow_id=workflow_id,
            latency_ms=round(elapsed * 1000),
        )
        return result

    async def run_workflow(self, workflow: WorkflowContext) -> WorkflowContext:
        """Execute full agent sequence defined by the router."""
        from app.core.workflow_engine import WorkflowStatus
        from app.mesh.router import workflow_router

        agent_sequence = workflow_router.resolve(
            workflow.workflow_type, workflow.tenant_id
        )

        log.info(
            "dispatcher.workflow_start",
            workflow_id=workflow.workflow_id,
            agents=agent_sequence,
        )

        workflow.context["_agent_sequence"] = agent_sequence
        workflow.transition(WorkflowStatus.RUNNING)

        for agent_name in agent_sequence:
            try:
                await self.dispatch(workflow, agent_name)
            except PolicyDeniedError as exc:
                workflow.error = str(exc)
                workflow.transition(WorkflowStatus.REJECTED)
                return workflow
            except DispatchError as exc:
                workflow.error = str(exc)
                workflow.transition(WorkflowStatus.FAILED)
                return workflow

        workflow.transition(WorkflowStatus.COMPLETED)
        return workflow


dispatcher = AgentDispatcher()
