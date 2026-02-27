"""
app/agents/registry.py — Centralized registration for default agents.
"""

from app.registry.agent_registry import agent_registry
from app.agents.finance.budget_agent import BudgetAgent
from app.agents.legal.compliance_agent import ComplianceAgent
from app.agents.risk.risk_agent import RiskAgent
from app.agents.devops.deployment_agent import DeploymentAgent
from app.agents.llm.llm_agent import LLMAgent

def register_all_agents():
    """Register all agent classes and default instances."""
    
    # 1. Register Classes (for dynamic instantiation)
    agent_registry.register_class(BudgetAgent)
    agent_registry.register_class(ComplianceAgent)
    agent_registry.register_class(RiskAgent)
    agent_registry.register_class(DeploymentAgent)
    agent_registry.register_class(LLMAgent)
    
    # 2. Register Default Instances for the 'default' tenant
    # This makes these agents available immediately for workflows.
    agent_registry.register(BudgetAgent(), tenant_id="default", override=True)
    agent_registry.register(ComplianceAgent(), tenant_id="default", override=True)
    agent_registry.register(RiskAgent(), tenant_id="default", override=True)
    agent_registry.register(DeploymentAgent(), tenant_id="default", override=True)
    agent_registry.register(LLMAgent(), tenant_id="default", override=True)
