"""
app/agents/risk/risk_agent.py — Risk assessment and scoring agent.
"""

from __future__ import annotations

from typing import Any, Dict, List

import structlog

from app.agents.base_agent import BaseAgent

log = structlog.get_logger(__name__)


class RiskAgent(BaseAgent):
    name = "risk"
    role = "risk"
    scopes = ["risk:read", "risk:write", "risk:assess"]
    description = "Scores risk level of a workflow context and generates a structured risk report."
    version = "1.0.0"
    cost_per_call = 0.01

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        risk_factors: List[str] = []
        risk_score = 0

        # Score based on finance output (previous agent result)
        finance_risk = int(context.get("finance_risk_score", 0))
        risk_score += finance_risk
        if finance_risk > 30:
            risk_factors.append(f"Finance risk elevated: score={finance_risk}")

        # Score based on legal output
        legal_violations: List[str] = context.get("legal_violations", [])
        if legal_violations:
            risk_score += len(legal_violations) * 20
            risk_factors.append(f"Legal violations detected: {len(legal_violations)}")

        # Score from custom risk_indicators in context
        custom_indicators: List[str] = context.get("risk_indicators", [])
        for indicator in custom_indicators:
            risk_score += int(context.get(f"risk_{indicator}_score", 10))
            risk_factors.append(f"Custom indicator: {indicator}")

        # Determine risk level from configurable thresholds
        low_threshold = int(context.get("risk_low_threshold", 25))
        medium_threshold = int(context.get("risk_medium_threshold", 60))
        high_threshold = int(context.get("risk_high_threshold", 80))

        if risk_score < low_threshold:
            risk_level = "low"
            risk_action = "approve"
        elif risk_score < medium_threshold:
            risk_level = "medium"
            risk_action = "review"
        elif risk_score < high_threshold:
            risk_level = "high"
            risk_action = "escalate"
        else:
            risk_level = "critical"
            risk_action = "reject"

        log.info(
            "risk_agent.assessed",
            risk_score=risk_score,
            risk_level=risk_level,
            factors=len(risk_factors),
        )

        return {
            "risk_status": "assessed",
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "risk_action": risk_action,
            "risk_recommendation": risk_action,
        }
