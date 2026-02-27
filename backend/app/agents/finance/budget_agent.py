"""
app/agents/finance/budget_agent.py — Budget analysis and approval agent.
"""

from __future__ import annotations

from typing import Any, Dict

import structlog

from app.agents.base_agent import BaseAgent

log = structlog.get_logger(__name__)


class BudgetAgent(BaseAgent):
    name = "finance"
    role = "finance"
    scopes = ["finance:read", "finance:write", "approve:purchase"]
    description = "Analyses budget requests, validates spending limits, recommends approval or rejection."
    version = "1.0.0"
    cost_per_call = 0.01

    # Configurable thresholds (loaded from context, not hardcoded)
    DEFAULT_LOW_THRESHOLD = 1_000
    DEFAULT_HIGH_THRESHOLD = 100_000

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        amount = float(context.get("amount", 0))
        purpose = context.get("purpose", "unspecified")
        department = context.get("department", "unknown")
        budget_remaining = float(context.get("budget_remaining", float("inf")))

        low_threshold = float(
            context.get("finance_low_threshold", self.DEFAULT_LOW_THRESHOLD)
        )
        high_threshold = float(
            context.get("finance_high_threshold", self.DEFAULT_HIGH_THRESHOLD)
        )

        flags = []
        risk_score = 0

        if amount > high_threshold:
            flags.append("EXCEEDS_HIGH_THRESHOLD")
            risk_score += 40

        if amount > budget_remaining:
            flags.append("EXCEEDS_BUDGET")
            risk_score += 50

        if amount > low_threshold:
            flags.append("REQUIRES_SECONDARY_APPROVAL")
            risk_score += 10

        recommendation = "approve" if risk_score < 50 else "review" if risk_score < 90 else "reject"

        log.info(
            "budget_agent.evaluated",
            amount=amount,
            risk_score=risk_score,
            recommendation=recommendation,
        )

        return {
            "finance_status": "evaluated",
            "finance_amount": amount,
            "finance_purpose": purpose,
            "finance_department": department,
            "finance_risk_score": risk_score,
            "finance_flags": flags,
            "finance_recommendation": recommendation,
        }
