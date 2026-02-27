"""
app/registry/role_registry.py — Role-to-scope mappings, per-tenant overrides.
"""

from __future__ import annotations

from typing import Dict, List, Optional


DEFAULT_ROLE_SCOPES: Dict[str, List[str]] = {
    "admin": ["*"],
    "finance": ["finance:read", "finance:write", "approve:purchase", "billing:read"],
    "legal": ["legal:read", "legal:write", "compliance:read", "compliance:write"],
    "risk": ["risk:read", "risk:write", "risk:assess"],
    "devops": ["devops:read", "devops:write", "deploy:read", "deploy:write"],
    "analyst": ["finance:read", "risk:read", "legal:read"],
    "viewer": ["read:*"],
    "llm": ["llm:call", "llm:read"],
}


class RoleRegistry:
    def __init__(self):
        # tenant_id -> role -> scopes
        self._overrides: Dict[str, Dict[str, List[str]]] = {}

    def get_scopes(self, role: str, tenant_id: Optional[str] = None) -> List[str]:
        """Return scopes for a role. Per-tenant overrides take precedence."""
        if tenant_id and tenant_id in self._overrides:
            tenant_roles = self._overrides[tenant_id]
            if role in tenant_roles:
                return tenant_roles[role]
        return DEFAULT_ROLE_SCOPES.get(role, [])

    def set_tenant_override(
        self, tenant_id: str, role: str, scopes: List[str]
    ) -> None:
        if tenant_id not in self._overrides:
            self._overrides[tenant_id] = {}
        self._overrides[tenant_id][role] = scopes

    def list_roles(self, tenant_id: Optional[str] = None) -> Dict[str, List[str]]:
        base = dict(DEFAULT_ROLE_SCOPES)
        if tenant_id and tenant_id in self._overrides:
            base.update(self._overrides[tenant_id])
        return base

    def is_valid_role(self, role: str, tenant_id: Optional[str] = None) -> bool:
        return bool(self.get_scopes(role, tenant_id))


role_registry = RoleRegistry()
