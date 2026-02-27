"""
app/core/audit_chain.py — SHA-256 hash-chained immutable audit log.
Each event hashes the previous event's hash, forming a tamper-evident chain.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_hash(data: dict, prev_hash: str) -> str:
    payload = json.dumps({**data, "prev_hash": prev_hash}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class AuditEvent:
    event_id: str
    tenant_id: str
    workflow_id: Optional[str]
    agent_name: Optional[str]
    action: str
    status: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=_utcnow_iso)
    prev_hash: str = "GENESIS"
    event_hash: str = ""
    sequence: int = 0

    def __post_init__(self):
        if not self.event_hash:
            self.event_hash = self._compute()

    def _compute(self) -> str:
        data = {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "agent_name": self.agent_name,
            "action": self.action,
            "status": self.status,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
        }
        return _compute_hash(data, self.prev_hash)

    def to_dict(self) -> dict:
        return asdict(self)


class AuditChain:
    """
    In-memory hash-chain; events are also persisted via AuditService.
    The chain enables tamper detection: verify() walks the chain recomputing hashes.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._events: List[AuditEvent] = []

    @property
    def head_hash(self) -> str:
        if not self._events:
            return "GENESIS"
        return self._events[-1].event_hash

    def append(
        self,
        action: str,
        status: str,
        payload: Dict[str, Any],
        workflow_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            workflow_id=workflow_id,
            agent_name=agent_name,
            action=action,
            status=status,
            payload=payload,
            prev_hash=self.head_hash,
            sequence=len(self._events),
        )
        # Recompute hash with correct seq/prev
        event.event_hash = event._compute()
        self._events.append(event)
        return event

    def verify(self) -> bool:
        """
        Walk the chain and recompute every hash.
        Returns True if chain is intact, False if tampered.
        """
        prev = "GENESIS"
        for evt in self._events:
            expected = _compute_hash(
                {
                    "event_id": evt.event_id,
                    "tenant_id": evt.tenant_id,
                    "workflow_id": evt.workflow_id,
                    "agent_name": evt.agent_name,
                    "action": evt.action,
                    "status": evt.status,
                    "timestamp": evt.timestamp,
                    "sequence": evt.sequence,
                },
                prev,
            )
            if expected != evt.event_hash:
                return False
            prev = evt.event_hash
        return True

    def replay(self) -> List[dict]:
        """Return all events as dicts for full replay."""
        return [e.to_dict() for e in self._events]

    def load_events(self, events: List[AuditEvent]) -> None:
        """Restore chain from persisted events (ordered by sequence)."""
        self._events = sorted(events, key=lambda e: e.sequence)


# ── Per-Tenant Chain Registry ─────────────────────────────────────

class AuditChainRegistry:
    def __init__(self):
        self._chains: Dict[str, AuditChain] = {}

    def get_or_create(self, tenant_id: str) -> AuditChain:
        if tenant_id not in self._chains:
            self._chains[tenant_id] = AuditChain(tenant_id)
        return self._chains[tenant_id]

    def verify_tenant(self, tenant_id: str) -> bool:
        chain = self._chains.get(tenant_id)
        if chain is None:
            return True   # empty chain → intact
        return chain.verify()


audit_chain_registry = AuditChainRegistry()
