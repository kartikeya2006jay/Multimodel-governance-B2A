"""
app/registry/tenant_registry.py — In-memory tenant registry.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


class TenantInfo:
    def __init__(self, tenant_id: str, name: str, slug: str, plan: str = "free"):
        self.tenant_id = tenant_id
        self.name = name
        self.slug = slug
        self.plan = plan
        self.is_active = True

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "slug": self.slug,
            "plan": self.plan,
            "is_active": self.is_active,
        }


class TenantRegistry:
    def __init__(self):
        self._tenants: Dict[str, TenantInfo] = {}

    def register(
        self, tenant_id: str, name: str, slug: str, plan: str = "free"
    ) -> TenantInfo:
        tenant = TenantInfo(tenant_id, name, slug, plan)
        self._tenants[tenant_id] = tenant
        log.info("tenant_registry.registered", tenant_id=tenant_id, name=name)
        return tenant

    def get(self, tenant_id: str) -> Optional[TenantInfo]:
        return self._tenants.get(tenant_id)

    def get_or_raise(self, tenant_id: str) -> TenantInfo:
        t = self.get(tenant_id)
        if not t:
            raise KeyError(f"Tenant '{tenant_id}' not found.")
        return t

    def list_all(self) -> List[TenantInfo]:
        return list(self._tenants.values())

    def deactivate(self, tenant_id: str) -> bool:
        t = self._tenants.get(tenant_id)
        if t:
            t.is_active = False
            return True
        return False


tenant_registry = TenantRegistry()
