"""
infra/seed_agents.py — Seeds default agents for a demo tenant.
All configuration loaded from environment / JSON file. No hardcoded data.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Allow running from /infra directory
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.config import settings
from app.models.base import AsyncSessionLocal, init_db
from app.services.agent_service import agent_service


SEED_FILE = os.environ.get(
    "SEED_FILE",
    str(Path(__file__).parent / "seed_data.json"),
)


async def seed():
    await init_db()

    if not os.path.exists(SEED_FILE):
        print(f"[seed] No seed file found at {SEED_FILE}. Skipping.")
        return

    with open(SEED_FILE) as f:
        data = json.load(f)

    tenant_id = data.get("tenant_id", settings.DEFAULT_TENANT_ID)
    agents = data.get("agents", [])

    async with AsyncSessionLocal() as db:
        for agent_def in agents:
            try:
                record = await agent_service.register(
                    db=db,
                    tenant_id=tenant_id,
                    name=agent_def["name"],
                    role=agent_def["role"],
                    scopes=agent_def.get("scopes", []),
                    description=agent_def.get("description", ""),
                    cost_per_call=agent_def.get("cost_per_call", 0.01),
                    version=agent_def.get("version", "1.0.0"),
                )
                print(f"[seed] ✅ Registered agent: {record.name} (tenant: {tenant_id})")
            except ValueError as exc:
                print(f"[seed] ⚠️  Skipped {agent_def.get('name')}: {exc}")


if __name__ == "__main__":
    asyncio.run(seed())
