"""
app/mesh/message_bus.py — Async in-process pub/sub message bus.
Agents never call each other directly; all messages route through this bus.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)

Handler = Callable[["Message"], Coroutine[Any, Any, None]]


@dataclass
class Message:
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    tenant_id: str = ""
    source: str = ""
    destination: Optional[str] = None           # None = broadcast
    correlation_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "event_type": self.event_type,
            "tenant_id": self.tenant_id,
            "source": self.source,
            "destination": self.destination,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class MessageBus:
    """
    Async pub/sub bus.
    Subscribers register per event_type.
    Publish dispatches to matching handlers concurrently.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Handler]] = defaultdict(list)
        self._dead_letter: List[Message] = []

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._subscribers[event_type].append(handler)
        log.debug("message_bus.subscribed", event_type=event_type, handler=handler.__qualname__)

    def unsubscribe(self, event_type: str, handler: Handler) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, message: Message) -> int:
        """Publish message to all registered handlers. Returns number notified."""
        handlers = self._subscribers.get(message.event_type, [])
        if not handlers:
            log.warning("message_bus.no_handlers", event_type=message.event_type)
            self._dead_letter.append(message)
            return 0

        tasks = [asyncio.create_task(h(message)) for h in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        errors = [r for r in results if isinstance(r, Exception)]
        for err in errors:
            log.error("message_bus.handler_error", error=str(err))

        log.info(
            "message_bus.published",
            event_type=message.event_type,
            handlers=len(handlers),
            errors=len(errors),
        )
        return len(handlers) - len(errors)

    async def emit(
        self,
        event_type: str,
        tenant_id: str,
        source: str,
        payload: dict,
        destination: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Message:
        msg = Message(
            event_type=event_type,
            tenant_id=tenant_id,
            source=source,
            destination=destination,
            correlation_id=correlation_id,
            payload=payload,
        )
        await self.publish(msg)
        return msg

    def get_dead_letter_queue(self) -> List[dict]:
        return [m.to_dict() for m in self._dead_letter]


message_bus = MessageBus()
