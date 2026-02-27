"""
app/registry/agent_registry.py — In-memory + DB-backed agent registry.
Supports plugin-style agent registration with zero core modification.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

import structlog

from app.agents.base_agent import BaseAgent

log = structlog.get_logger(__name__)


class AgentRegistry:
    """
    Central registry for all BaseAgent subclasses.

    Agents are keyed by (tenant_id, agent_name) to support
    per-tenant agent isolation.

    Usage:
        agent_registry.register(MyAgent(), tenant_id="acme")
        agent = agent_registry.get("my-agent", tenant_id="acme")
    """

    def __init__(self):
        # key: (tenant_id, agent_name) -> agent instance
        self._agents: Dict[tuple, BaseAgent] = {}
        # class registry (shared across tenants)
        self._classes: Dict[str, Type[BaseAgent]] = {}

    def register(
        self,
        agent: BaseAgent,
        tenant_id: str = "default",
        override: bool = False,
    ) -> None:
        key = (tenant_id, agent.name)
        if key in self._agents and not override:
            raise ValueError(
                f"Agent '{agent.name}' already registered for tenant '{tenant_id}'. "
                "Use override=True to replace."
            )
        self._agents[key] = agent
        log.info(
            "agent_registry.registered",
            agent=agent.name,
            role=agent.role,
            tenant=tenant_id,
        )

    def register_class(self, cls: Type[BaseAgent]) -> None:
        """Register an agent class (usable across tenants)."""
        self._classes[cls.name] = cls

    def get(self, agent_name: str, tenant_id: str = "default") -> Optional[BaseAgent]:
        # Try tenant-specific first, then fall back to default tenant
        return self._agents.get((tenant_id, agent_name)) or self._agents.get(
            ("default", agent_name)
        )

    def get_or_raise(self, agent_name: str, tenant_id: str = "default") -> BaseAgent:
        agent = self.get(agent_name, tenant_id)
        if agent is None:
            raise KeyError(
                f"Agent '{agent_name}' not found for tenant '{tenant_id}'."
            )
        return agent

    def list_all(self, tenant_id: Optional[str] = None) -> List[BaseAgent]:
        if tenant_id:
            return [
                a for (tid, _), a in self._agents.items() if tid == tenant_id
            ]
        return list(self._agents.values())

    def deregister(self, agent_name: str, tenant_id: str = "default") -> bool:
        key = (tenant_id, agent_name)
        if key in self._agents:
            del self._agents[key]
            log.info("agent_registry.deregistered", agent=agent_name, tenant=tenant_id)
            return True
        return False

    def instantiate_and_register(
        self,
        agent_name: str,
        tenant_id: str = "default",
        **kwargs,
    ) -> BaseAgent:
        """Instantiate a registered class and register as instance."""
        cls = self._classes.get(agent_name)
        if cls is None:
            raise KeyError(f"Agent class '{agent_name}' not found.")
        instance = cls(**kwargs)
        self.register(instance, tenant_id=tenant_id)
        return instance


agent_registry = AgentRegistry()
