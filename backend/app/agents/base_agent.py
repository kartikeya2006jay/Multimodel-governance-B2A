"""
app/agents/base_agent.py — Abstract BaseAgent.
All domain agents must inherit this class and implement execute().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseAgent(ABC):
    """
    Base class for all governance agents.

    To add a new agent:
    1. Create a new file under app/agents/<domain>/
    2. Subclass BaseAgent
    3. Implement execute(context) -> dict
    4. Register: agent_registry.register(MyAgent(), tenant_id="your-tenant")
    """

    name: str = ""
    role: str = ""
    scopes: List[str] = []
    description: str = ""
    version: str = "1.0.0"
    cost_per_call: Optional[float] = None   # None = use system default

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent logic against the workflow context.

        Args:
            context: Shared mutable context dict from WorkflowContext.
                     May already contain results from previous agents.

        Returns:
            dict: Result to merge into the workflow context.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Agent name={self.name!r} role={self.role!r}>"
