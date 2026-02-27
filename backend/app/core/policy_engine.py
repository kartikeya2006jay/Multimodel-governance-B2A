"""
app/core/policy_engine.py — Rule-based policy evaluation engine.
Policies loaded from DB per tenant. Validates scope, role, and
custom rules per workflow step. No hardcoded rules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"


@dataclass
class PolicyContext:
    """Context passed to the policy engine for evaluation."""
    tenant_id: str
    agent_name: str
    action: str
    scopes: List[str]
    role: Optional[str]
    workflow_id: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class PolicyResult:
    decision: PolicyDecision
    reason: str
    matched_rule: Optional[str] = None
    violations: List[str] = None

    def __post_init__(self):
        if self.violations is None:
            self.violations = []

    @property
    def allowed(self) -> bool:
        return self.decision == PolicyDecision.ALLOW


# ── Policy Rule Types ────────────────────────────────────────────

def _eval_scope_rule(rule: dict, ctx: PolicyContext) -> Optional[PolicyResult]:
    required_scopes: List[str] = rule.get("required_scopes", [])
    if not required_scopes:
        return None
    missing = [s for s in required_scopes if s not in ctx.scopes and "*" not in ctx.scopes]
    if missing:
        return PolicyResult(
            decision=PolicyDecision.DENY,
            reason=f"Missing required scopes: {missing}",
            matched_rule=rule.get("name"),
            violations=missing,
        )
    return None


def _eval_role_rule(rule: dict, ctx: PolicyContext) -> Optional[PolicyResult]:
    allowed_roles: List[str] = rule.get("allowed_roles", [])
    if not allowed_roles:
        return None
    if ctx.role not in allowed_roles:
        return PolicyResult(
            decision=PolicyDecision.DENY,
            reason=f"Role '{ctx.role}' not permitted. Allowed: {allowed_roles}",
            matched_rule=rule.get("name"),
        )
    return None


def _eval_action_rule(rule: dict, ctx: PolicyContext) -> Optional[PolicyResult]:
    blocked_actions: List[str] = rule.get("blocked_actions", [])
    if ctx.action in blocked_actions:
        return PolicyResult(
            decision=PolicyDecision.DENY,
            reason=f"Action '{ctx.action}' is explicitly blocked by policy.",
            matched_rule=rule.get("name"),
        )
    return None


RULE_EVALUATORS = [_eval_scope_rule, _eval_role_rule, _eval_action_rule]


# ── Policy Engine ────────────────────────────────────────────────

class PolicyEngine:
    """
    Evaluates a PolicyContext against a set of tenant-specific rules.

    Rules are JSON objects loaded from the database or config.
    Rule schema:
    {
        "name": "require_finance_scope",
        "required_scopes": ["finance:read"],
        "allowed_roles": ["finance", "admin"],
        "blocked_actions": [],
        "effect": "deny"          # deny | allow | review
    }
    """

    def __init__(self):
        # In-memory cache: tenant_id -> list of rule dicts
        self._rule_cache: Dict[str, List[dict]] = {}

    def load_rules(self, tenant_id: str, rules: List[dict]) -> None:
        """Load (or refresh) policy rules for a tenant."""
        self._rule_cache[tenant_id] = rules

    def evaluate(self, ctx: PolicyContext) -> PolicyResult:
        """Evaluate a policy context against all loaded rules for the tenant."""
        rules = self._rule_cache.get(ctx.tenant_id, [])

        # Default: allow if no rules configured (open by default in dev)
        if not rules:
            return PolicyResult(
                decision=PolicyDecision.ALLOW,
                reason="No policy rules configured for tenant; defaulting to allow.",
            )

        violations: List[str] = []
        for rule in rules:
            for evaluator in RULE_EVALUATORS:
                result = evaluator(rule, ctx)
                if result and result.decision == PolicyDecision.DENY:
                    violations.append(result.reason)

        if violations:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason="; ".join(violations),
                violations=violations,
            )

        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="All policy rules passed.",
        )

    def add_rule(self, tenant_id: str, rule: dict) -> None:
        if tenant_id not in self._rule_cache:
            self._rule_cache[tenant_id] = []
        self._rule_cache[tenant_id].append(rule)

    def clear_rules(self, tenant_id: str) -> None:
        self._rule_cache.pop(tenant_id, None)

    def get_rules(self, tenant_id: str) -> List[dict]:
        return self._rule_cache.get(tenant_id, [])


# Singleton policy engine instance
policy_engine = PolicyEngine()
