"""Event dispatcher for nanobot.

This module provides event dispatching and routing capabilities.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional
from .events import Event, InboundMessage, OutboundMessage


class Dispatcher:
    """Event dispatcher for routing messages between channels and agents."""

    def __init__(self, config: Optional[Any] = None):
        self.config = config
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._inbound_queue: asyncio.Queue = asyncio.Queue()
        self._outbound_queue: asyncio.Queue = asyncio.Queue()

    def add_event_handler(self, event_type: str, handler: Callable):
        """Add an event handler for a specific event type."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def remove_event_handler(self, event_type: str, handler: Callable):
        """Remove an event handler."""
        if event_type in self._event_handlers:
            try:
                self._event_handlers[event_type].remove(handler)
            except ValueError:
                pass

    async def handle_event(self, event: Event):
        """Handle an event by calling registered handlers."""
        event_type = getattr(event, "type", "message")

        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    print(f"Error in event handler: {e}")

    async def dispatch(self, message: Dict[str, Any]):
        """Dispatch a message to the outbound queue."""
        event = OutboundMessage(**message)
        await self._outbound_queue.put(event)

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

    async def put_inbound(self, event: Event):
        """Put an event into the inbound queue."""
        await self._inbound_queue.put(event)

    async def put_outbound(self, event: Event):
        """Put an event into the outbound queue."""
        await self._outbound_queue.put(event)
