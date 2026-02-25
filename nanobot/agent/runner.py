"""Agent runner for nanobot.

This module provides the main agent execution and message routing logic.
"""

import asyncio
import signal
from typing import Optional
from loguru import logger
from .config import Config
from .dispatcher import Dispatcher
from .bus.queue import MessageBus
from ..channels.manager import ChannelManager


class AgentRunner:
    """Main agent runner for nanobot."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.dispatcher = None
        self.bus = None
        self.channel_manager = None

    async def initialize(self):
        """Initialize the agent and its components."""
        logger.info("Initializing Nanobot Agent...")

        # Initialize message bus
        self.bus = MessageBus()

        # Initialize dispatcher
        self.dispatcher = Dispatcher(self.config)

        # Initialize channel manager
        self.channel_manager = ChannelManager(self.config, self.bus)
        await self.channel_manager.initialize()

        # Attach event bus to message bus
        from .bus.events import EventBus

        event_bus = EventBus()
        self.bus.attach_event_bus(event_bus)

        logger.info("Nanobot Agent initialized successfully")

    async def start(self):
        """Start the agent and all channels."""
        await self.initialize()

        logger.info("Starting Nanobot channels...")
        await self.channel_manager.start()

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    async def run(self):
        """Main event loop."""
        logger.info("Nanobot Agent is running...")

        try:
            # Main event loop
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Agent received shutdown signal")
            await self.stop()
        except Exception as e:
            logger.error(f"Error in agent loop: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Stop all channels and cleanup."""
        logger.info("Stopping Nanobot Agent...")

        if self.channel_manager:
            await self.channel_manager.stop()

        logger.info("Nanobot Agent stopped")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}")
        asyncio.create_task(self.stop())
