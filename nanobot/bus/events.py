"""Event system for nanobot message bus.

This module defines the event types used throughout the nanobot system.
"""

import asyncio
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Event:
    """Base event class for nanobot events."""

    type: str
    content: Optional[str] = None
    sender_id: Optional[str] = None
    chat_id: Optional[str] = None
    channel: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InboundMessage(Event):
    """Inbound message from a channel to the agent."""

    def __init__(
        self,
        type: str = "text",
        content: Optional[str] = None,
        sender_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        channel: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(
            type=type,
            content=content,
            sender_id=sender_id,
            chat_id=chat_id,
            channel=channel,
            metadata=metadata or {},
            **kwargs,
        )


@dataclass
class OutboundMessage(Event):
    """Outbound message from the agent to a channel."""

    def __init__(
        self,
        type: str = "text",
        content: Optional[str] = None,
        sender_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        channel: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(
            type=type,
            content=content,
            sender_id=sender_id,
            chat_id=chat_id,
            channel=channel,
            metadata=metadata or {},
            **kwargs,
        )


class EventBus:
    """Simple event bus for handling events."""

    def __init__(self):
        self._handlers: Dict[str, list] = {}
        self._queue: asyncio.Queue = asyncio.Queue()

    def subscribe(self, event_type: str, handler):
        """Subscribe to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event):
        """Publish an event."""
        await self._queue.put(event)

        # Call handlers
        if event.type in self._handlers:
            for handler in self._handlers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    print(f"Error in event handler: {e}")

    async def get_event(self, timeout: Optional[float] = None) -> Event:
        """Get the next event from the queue."""
        if timeout:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        return await self._queue.get()
