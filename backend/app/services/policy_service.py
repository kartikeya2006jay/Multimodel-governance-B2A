"""
app/services/policy_service.py — Policy CRUD and evaluation service.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from app.core.policy_engine import PolicyContext, PolicyResult, policy_engine

log = structlog.get_logger(__name__)


class PolicyService:

    def load_rules(self, tenant_id: str, rules: List[dict]) -> dict:
        policy_engine.load_rules(tenant_id, rules)
        log.info("policy_service.rules_loaded", tenant_id=tenant_id, count=len(rules))
        return {"tenant_id": tenant_id, "rules_loaded": len(rules)}

    def add_rule(self, tenant_id: str, rule: dict) -> dict:
        # Validate rule has required fields
        if "name" not in rule:
            raise ValueError("Policy rule must have a 'name' field.")
        policy_engine.add_rule(tenant_id, rule)
        log.info("policy_service.rule_added", tenant_id=tenant_id, rule=rule.get("name"))
        return {"status": "added", "rule": rule}

    def get_rules(self, tenant_id: str) -> List[dict]:
        return policy_engine.get_rules(tenant_id)

    def clear_rules(self, tenant_id: str) -> dict:
        policy_engine.clear_rules(tenant_id)
        return {"tenant_id": tenant_id, "status": "cleared"}

    def evaluate(
        self,
        tenant_id: str,
        agent_name: str,
        action: str,
        scopes: List[str],
        role: Optional[str] = None,
        workflow_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> dict:
        ctx = PolicyContext(
            tenant_id=tenant_id,
            agent_name=agent_name,
            action=action,
            scopes=scopes,
            role=role,
            workflow_id=workflow_id,
            metadata=metadata or {},
        )
        result: PolicyResult = policy_engine.evaluate(ctx)
        return {
            "decision": result.decision.value,
            "reason": result.reason,
            "allowed": result.allowed,
            "violations": result.violations,
            "matched_rule": result.matched_rule,
        }


policy_service = PolicyService()
