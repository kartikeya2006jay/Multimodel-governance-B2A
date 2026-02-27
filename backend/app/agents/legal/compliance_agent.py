"""
app/agents/legal/compliance_agent.py — Compliance review agent.
"""

from __future__ import annotations

from typing import Any, Dict, List

import structlog

from app.agents.base_agent import BaseAgent

log = structlog.get_logger(__name__)


class ComplianceAgent(BaseAgent):
    name = "legal"
    role = "legal"
    scopes = ["legal:read", "legal:write", "compliance:read", "compliance:write"]
    description = "Reviews compliance requirements against workflow context."
    version = "1.0.0"
    cost_per_call = 0.01

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        jurisdiction = context.get("jurisdiction", "default")
        categories: List[str] = context.get("compliance_categories", [])
        document_refs: List[str] = context.get("document_refs", [])
        amount = float(context.get("amount", 0))
        purpose = context.get("purpose", "")

        compliance_checks = []
        violations = []

        # GDPR check example (configurable via categories)
        if "gdpr" in categories or "privacy" in categories:
            compliance_checks.append("GDPR")
            if "personal_data" in purpose.lower():
                violations.append("Personal data processing requires DPA agreement.")

        # Financial regulation check
        if amount > float(context.get("compliance_financial_threshold", 50000)):
            compliance_checks.append("AML_CHECK")
            if not context.get("aml_verified", False):
                violations.append("AML verification required for amounts over threshold.")

        # Document completeness check
        required_docs: List[str] = context.get("required_documents", [])
        missing_docs = [d for d in required_docs if d not in document_refs]
        if missing_docs:
            violations.append(f"Missing required documents: {missing_docs}")

        status = "compliant" if not violations else "non_compliant"

        log.info(
            "compliance_agent.evaluated",
            jurisdiction=jurisdiction,
            violations=len(violations),
            status=status,
        )

        return {
            "legal_status": status,
            "legal_jurisdiction": jurisdiction,
            "legal_checks_performed": compliance_checks,
            "legal_violations": violations,
            "legal_recommendation": "proceed" if not violations else "halt",
        }
