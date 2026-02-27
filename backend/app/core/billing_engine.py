"""
app/core/billing_engine.py — Double-entry billing ledger engine.
Supports per-agent, per-workflow, per-tenant cost tracking.
LLM token usage billed at configurable rates. Ledger is append-only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Dict, List, Optional

from app.core.config import settings


class EntryType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    RESERVE = "reserve"
    VOID = "void"
    COMMIT = "commit"


@dataclass
class LedgerEntry:
    entry_id: str
    tenant_id: str
    workflow_id: Optional[str]
    agent_name: Optional[str]
    entry_type: EntryType
    amount: Decimal
    currency: str
    description: str
    reference: Optional[str]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            **self.__dict__,
            "amount": str(self.amount),
        }


class BillingEngine:
    """
    Append-only double-entry billing engine.

    Rules:
      - DEBIT  → cost charged to tenant balance
      - CREDIT → funds added to tenant balance
      - RESERVE → tentative hold (pending workflow completion)
      - COMMIT  → convert RESERVE to DEBIT
      - VOID    → cancel a RESERVE without charging
    """

    def __init__(self):
        # tenant_id -> list of entries (in-memory; also persisted via BillingService)
        self._ledger: Dict[str, List[LedgerEntry]] = {}
        # pending reserves: reserve_id -> entry
        self._reserves: Dict[str, LedgerEntry] = {}

    def _add(self, entry: LedgerEntry) -> LedgerEntry:
        self._ledger.setdefault(entry.tenant_id, []).append(entry)
        return entry

    def _round(self, amount: float) -> Decimal:
        return Decimal(str(amount)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    # ── Core Operations ───────────────────────────────────────────

    def charge_agent_call(
        self,
        tenant_id: str,
        agent_name: str,
        workflow_id: Optional[str] = None,
        cost_override: Optional[float] = None,
    ) -> LedgerEntry:
        amount = self._round(cost_override or settings.DEFAULT_AGENT_COST_PER_CALL)
        entry = LedgerEntry(
            entry_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            agent_name=agent_name,
            entry_type=EntryType.DEBIT,
            amount=amount,
            currency="USD",
            description=f"Agent call: {agent_name}",
            reference=workflow_id,
        )
        return self._add(entry)

    def charge_llm_tokens(
        self,
        tenant_id: str,
        agent_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        workflow_id: Optional[str] = None,
        cost_per_1k_override: Optional[float] = None,
    ) -> LedgerEntry:
        rate = self._round(cost_per_1k_override or settings.DEFAULT_LLM_COST_PER_1K_TOKENS)
        total_tokens = prompt_tokens + completion_tokens
        amount = (self._round(total_tokens) / Decimal("1000")) * rate
        entry = LedgerEntry(
            entry_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            agent_name=agent_name,
            entry_type=EntryType.DEBIT,
            amount=amount,
            currency="USD",
            description=f"LLM tokens ({model}): {total_tokens} tokens",
            reference=workflow_id,
            metadata={
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        )
        return self._add(entry)

    def reserve_workflow_cost(
        self,
        tenant_id: str,
        workflow_id: str,
        estimated_cost: Optional[float] = None,
    ) -> str:
        """Reserve (hold) estimated workflow cost. Returns reserve_id."""
        amount = self._round(estimated_cost or settings.DEFAULT_WORKFLOW_BASE_COST)
        reserve_id = str(uuid.uuid4())
        entry = LedgerEntry(
            entry_id=reserve_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            agent_name=None,
            entry_type=EntryType.RESERVE,
            amount=amount,
            currency="USD",
            description=f"Workflow reserve: {workflow_id}",
            reference=workflow_id,
        )
        self._add(entry)
        self._reserves[reserve_id] = entry
        return reserve_id

    def commit_reserve(self, reserve_id: str) -> Optional[LedgerEntry]:
        """Convert RESERVE to DEBIT on completion."""
        reserve = self._reserves.pop(reserve_id, None)
        if not reserve:
            return None
        entry = LedgerEntry(
            entry_id=str(uuid.uuid4()),
            tenant_id=reserve.tenant_id,
            workflow_id=reserve.workflow_id,
            agent_name=None,
            entry_type=EntryType.COMMIT,
            amount=reserve.amount,
            currency="USD",
            description=f"Commit reserve: {reserve.entry_id}",
            reference=reserve.entry_id,
        )
        return self._add(entry)

    def void_reserve(self, reserve_id: str) -> Optional[LedgerEntry]:
        """Void a RESERVE (no charge) on workflow failure/rejection."""
        reserve = self._reserves.pop(reserve_id, None)
        if not reserve:
            return None
        entry = LedgerEntry(
            entry_id=str(uuid.uuid4()),
            tenant_id=reserve.tenant_id,
            workflow_id=reserve.workflow_id,
            agent_name=None,
            entry_type=EntryType.VOID,
            amount=Decimal("0"),
            currency="USD",
            description=f"Void reserve: {reserve.entry_id}",
            reference=reserve.entry_id,
        )
        return self._add(entry)

    def credit_tenant(
        self, tenant_id: str, amount: float, description: str
    ) -> LedgerEntry:
        entry = LedgerEntry(
            entry_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            workflow_id=None,
            agent_name=None,
            entry_type=EntryType.CREDIT,
            amount=self._round(amount),
            currency="USD",
            description=description,
            reference=None,
        )
        return self._add(entry)

    # ── Reporting ─────────────────────────────────────────────────

    def get_balance(self, tenant_id: str) -> Decimal:
        """Net balance = credits - debits (reserves treated as debits)."""
        entries = self._ledger.get(tenant_id, [])
        total = Decimal("0")
        for e in entries:
            if e.entry_type in (EntryType.CREDIT,):
                total += e.amount
            elif e.entry_type in (EntryType.DEBIT, EntryType.RESERVE, EntryType.COMMIT):
                total -= e.amount
        return total

    def get_ledger(self, tenant_id: str) -> List[dict]:
        return [e.to_dict() for e in self._ledger.get(tenant_id, [])]

    def get_workflow_cost(self, tenant_id: str, workflow_id: str) -> Decimal:
        entries = self._ledger.get(tenant_id, [])
        return sum(
            e.amount
            for e in entries
            if e.workflow_id == workflow_id
            and e.entry_type in (EntryType.DEBIT, EntryType.COMMIT)
        )


billing_engine = BillingEngine()
