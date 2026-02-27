"""
app/models/workflow.py — Workflow instance persistence.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class WorkflowRecord(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    workflow_type: Mapped[str] = mapped_column(String(100), nullable=False)
    initiator: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_results: Mapped[list] = mapped_column(JSON, default=list)
    agent_sequence: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    reserve_id: Mapped[str] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "workflow_type": self.workflow_type,
            "initiator": self.initiator,
            "status": self.status,
            "context": self.context,
            "agent_results": self.agent_results,
            "agent_sequence": self.agent_sequence,
            "error": self.error,
            "total_cost": self.total_cost,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
