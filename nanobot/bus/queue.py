"""Message queue for nanobot event bus.

This module provides message queue management for the event bus system.
"""

import asyncio
from typing import Optional
from .events import Event, InboundMessage, OutboundMessage


class MessageBus:
    """Message bus for inter-module communication."""

    def __init__(self):
        self._outbound_queue: asyncio.Queue = asyncio.Queue()
        self._inbound_queue: asyncio.Queue = asyncio.Queue()
        self._event_bus: Optional["EventBus"] = None

    def attach_event_bus(self, event_bus):
        """Attach event bus to message bus."""
        self._event_bus = event_bus

    async def publish(self, event: Event):
        """Publish an event to the message bus."""
        if self._event_bus:
            await self._event_bus.publish(event)

    async def consume_outbound(self, timeout: Optional[float] = None) -> Event:
        """Consume an event from the outbound queue."""
        if timeout:
            try:
                return await asyncio.wait_for(
                    self._outbound_queue.get(), timeout=timeout
                )
            except asyncio.TimeoutError:
                raise
        return await self._outbound_queue.get()

    async def consume_inbound(self, timeout: Optional[float] = None) -> Event:
        """Consume an event from the inbound queue."""
        if timeout:
            try:
                return await asyncio.wait_for(
                    self._inbound_queue.get(), timeout=timeout
                )
            except asyncio.TimeoutError:
                raise
        return await self._inbound_queue.get()
