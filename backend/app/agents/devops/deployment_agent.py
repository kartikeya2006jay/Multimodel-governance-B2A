"""
app/agents/devops/deployment_agent.py — Deployment readiness validation agent.
"""

from __future__ import annotations

from typing import Any, Dict, List

import structlog

from app.agents.base_agent import BaseAgent

log = structlog.get_logger(__name__)


class DeploymentAgent(BaseAgent):
    name = "devops"
    role = "devops"
    scopes = ["devops:read", "devops:write", "deploy:read", "deploy:write"]
    description = "Validates deployment readiness: environment, version, rollback plan."
    version = "1.0.0"
    cost_per_call = 0.01

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        environment = context.get("environment", "unknown")
        service_name = context.get("service_name", "unknown")
        version = context.get("deploy_version", "unspecified")
        rollback_plan = context.get("rollback_plan")
        test_coverage = float(context.get("test_coverage", 0))
        canary = context.get("canary_deploy", False)

        checks: List[Dict[str, Any]] = []
        blockers: List[str] = []

        # Environment check
        allowed_envs: List[str] = context.get("allowed_environments", ["staging", "production"])
        if environment not in allowed_envs:
            blockers.append(f"Target environment '{environment}' not in allowed list.")
        checks.append({"check": "environment", "passed": environment in allowed_envs})

        # Rollback plan check
        has_rollback = bool(rollback_plan)
        if not has_rollback and environment == "production":
            blockers.append("Production deployments require a rollback plan.")
        checks.append({"check": "rollback_plan", "passed": has_rollback})

        # Test coverage check
        min_coverage = float(context.get("min_test_coverage", 80.0))
        coverage_ok = test_coverage >= min_coverage
        if not coverage_ok:
            blockers.append(
                f"Test coverage {test_coverage}% is below required {min_coverage}%."
            )
        checks.append({"check": "test_coverage", "passed": coverage_ok})

        status = "ready" if not blockers else "blocked"

        log.info(
            "deployment_agent.validated",
            service=service_name,
            environment=environment,
            status=status,
            blockers=len(blockers),
        )

        return {
            "devops_status": status,
            "devops_service": service_name,
            "devops_environment": environment,
            "devops_version": version,
            "devops_checks": checks,
            "devops_blockers": blockers,
            "devops_canary": canary,
            "devops_recommendation": "deploy" if not blockers else "block",
        }
