# Nextcloud Talk Channel for nanobot

This is a `nextcloud_talk` Channel for nanobot (OpenCode-Agent).

## Overview

This channel enables integration of [Nextcloud Talk](https://nextcloud.com/apps/spreed/) into the nanobot Agent. It uses the official **Talk Bot Webhook API** from Nextcloud.

**Features:**
- Webhook-based event handling (no persistent WebSocket connection)
- HMAC signature validation
- Configurable `roomPolicy` (open/mention)
- Whitelist for users and rooms
- Support for long messages (chunking)
- Full integration with the nanobot MessageBus

## System Architecture

```
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│  Nextcloud Talk │ <------> │  nanobot Agent  │ <------> │  I/O/System     │
│  (Webhook API)  │          │  (OpenCode)     │          │  /tools/git     │
└─────────────────┘          └─────────────────┘          └─────────────────┘
          ▲                              ▲
          │                              │
    OCS API Bot Endpoints          MessageBus
    (ngrok/port-forward)
```

## Installation

### 1. Prerequisites

- Python 3.10+
- Nextcloud Talk with enabled Bot feature
- Aiohttp for the webhook server

### 2. Install dependencies

```bash
pip install aiohttp
```

### 3. Install Bot in Nextcloud

Run on the Nextcloud server:

```bash
# Register bot
php occ talk:bot:install \
  "Nanobot" \
  "your-shared-secret-min-40-chars" \
  "https://nanobot.example.com/webhook/nextcloud_talk" \
  --feature webhook \
  --feature response

# Install bot in a room
php occ talk:bot:install-in-room "Nanobot" "<room-token>"
```

**Important Details:**
- The `bot_secret` must be at least 40 characters long
- The `webhook_url` should be publicly accessible (ngrok, port-forward, reverse proxy)
- Use the `webhook` and `response` features for full functionality

## Configuration

### File: `~/.nanobot/config.json`

```json
{
  "channels": {
    "nextcloud_talk": {
      "enabled": true,
      "baseUrl": "https://cloud.example.com",
      "botSecret": "your-shared-secret-min-40-chars",
      "webhookPath": "/webhook/nextcloud_talk",
      "allowFrom": ["volker"],
      "allowRooms": [],
      "roomPolicy": "open"
    }
  }
}
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | `false` | Enable channel |
| `base_url` | string | `""` | Nextcloud URL (e.g., "https://cloud.example.com") |
| `botSecret` | string | `""` | Shared Secret from `occ talk:bot:install` (min. 40 characters) |
| `webhookPath` | string | `"/webhook/nextcloud_talk"` | Webhook path on nanobot Gateway |
| `allowFrom` | list[str] | `[]` | Allowed Nextcloud User IDs (empty = all) |
| `allowRooms` | list[str] | `[]` | Allowed conversation tokens (empty = all) |
| `roomPolicy` | string | `"open"` | `"open"` (all messages) or `"mention"` (@Bot required) |

**Important:**
- Keys in `config.json` are camelCase (due to `alias_generator=to_camel`)
- `allowRooms` contains conversation tokens, not room IDs

## Write Event Listener

### Example: Respond to Messages Without @Bot

Create a file `nextcloud_talk_listener.py`:

```python
"""Event-Listener for Nextcloud Talk Channel.

This example shows how to implement a custom listener that responds to messages from Nextcloud Talk.
"""

import asyncio
from loguru import logger
from nanobot.bus.events import Event
from nanobot.bus.dispatcher import Dispatcher


class NextcloudTalkListener:
    """Example listener for Nextcloud Talk messages.

    This listener processes:
    - Help commands (@Bot help)
    - Status requests (@Bot status)
    - System questions (@Bot what can you do)
    """

    def __init__(self, dispatcher: Dispatcher) -> None:
        self.dispatcher = dispatcher
        self.allowed_rooms = {
            "testtoken123",
            "roomtoken456",
            "productionroom789",
        }
        self.commands = {
            "hilfe": self._send_help,
            "help": self._send_help,
            "status": self._send_status,
            "info": self._send_info,
            "capabilities": self._send_capabilities,
            "was kannst du": self._send_capabilities,
            "help-was-kannst-du": self._send_capabilities,
        }

    async def on_message(self, event: Event) -> None:
        """Process new message from Nextcloud Talk."""
        try:
            content = event.content or ""
            sender_id = event.sender_id or ""
            chat_id = event.chat_id or ""

            logger.info(
                "Nanobot received message from {} in room {}: {}",
                sender_id,
                chat_id,
                content[:100],
            )

            if not sender_id:
                logger.warning("Invalid message: sender_id missing")
                return

            # Check room whitelist
            if chat_id not in self.allowed_rooms:
                logger.debug(
                    "Room {} not in allowed list. Allowed rooms: {}",
                    chat_id,
                    self.allowed_rooms,
                )
                return

            # Process message
            await self._process_message(content, sender_id, chat_id)

        except Exception as e:
            logger.exception("Error processing message: {}", e)

    async def _process_message(self, content: str, sender_id: str, chat_id: str) -> None:
        """Process message based on content."""
        content_lower = content.lower().strip()

        # Check if it's a known command
        for command, handler in self.commands.items():
            if command in content_lower:
                await handler(content, sender_id, chat_id)
                return

        # If no known command, send help message
        if not content.lower().startswith("@"):
            await self._send_help(content, sender_id, chat_id)

    async def _send_help(self, content: str, sender_id: str, chat_id: str) -> None:
        """Send help message."""
        response = {
            "type": "text",
            "content": """
**Hello! I am your Nanobot! 🤖**

**Available Commands:**
- `@Bot hilfe` or `@Bot help` - Show this list
- `@Bot status` - Show system status
- `@Bot info` - Show agent information
- `@Bot capabilities` - Show what I can do

**Examples:**
- `@Bot status` - Get system status
- `@Bot was kannst du` - See my capabilities

If you want to execute git commands or edit files, just write the command directly. I'll follow your goal.
            """.strip(),
            "channel": "nextcloud_talk",
            "chat_id": chat_id,
            "sender_id": sender_id,
            "metadata": {
                "nextcloud_talk": {
                    "skip": True,
                    "command": "hilfe"
                }
            }
        }
        await self.dispatcher.dispatch(response)

    async def _send_status(self, content: str, sender_id: str, chat_id: str) -> None:
        """Send system status."""
        from datetime import datetime

        now = datetime.now().isoformat()

        response = {
            "type": "text",
            "content": f"""
**System Status**

---
**Time:** {now}

**Nextcloud Talk Channel:**
- Status: ✅ **Active**
- Bot Secret: ✅ **Configured**
- Gateway Port: **18790**
- Webhook Path: `/webhook/nextcloud_talk`
- Room Policy: **open**

**Nextcloud:**
- Base URL: {self.dispatcher.config.channels.nextcloud_talk.base_url or "Not configured"}
- Available Features: webhook, response

---
The response was sent by {sender_id} in room {chat_id}.
            """.strip(),
            "channel": "nextcloud_talk",
            "chat_id": chat_id,
            "sender_id": sender_id,
            "metadata": {
                "nextcloud_talk": {
                    "skip": True,
                    "command": "status"
                }
            }
        }
        await self.dispatcher.dispatch(response)

    async def _send_info(self, content: str, sender_id: str, chat_id: str) -> None:
        """Send agent information."""
        response = {
            "type": "text",
            "content": """
**Agent Information**

---
**Agent:** Nanobot (OpenCode-Agent)
**Version:** 1.0.0
**Model:** anthropic/claude-opus-4-5 (default)

**Configured Channels:**
- Nextcloud Talk: ✅ (Active)

**Workspace:** ~/.nanobot/workspace

---
**What I can:**
- Execute git commands (clone, status, log, etc.)
- Read, edit, create files
- Perform web search
- Execute shell commands
- Find files (list_files, glob)

**Usage:**
You can enter git commands directly, for example:
- `git status` - Show git status
- `git log -5` - Show last 5 commits
- `git diff` - Show changes
- `git checkout -b feature` - Create new branch

You can also edit files or request information.
            """.strip(),
            "channel": "nextcloud_talk",
            "chat_id": chat_id,
            "sender_id": sender_id,
            "metadata": {
                "nextcloud_talk": {
                    "skip": True,
                    "command": "info"
                }
            }
        }
        await self.dispatcher.dispatch(response)

    async def _send_capabilities(self, content: str, sender_id: str, chat_id: str) -> None:
        """Send available capabilities."""
        response = {
            "type": "text",
            "content": """
**My Capabilities**

---
**Git Commands:**
- `git status` - Status
- `git log` - Logs
- `git diff` - Changes
- `git branch`, `git checkout`, `git merge`
- `git clone`, `git pull`, `git push`

**File Operations:**
- `read_file("path")` - Read file
- `edit_file("path", content)` - Edit file
- `write_file("path", content)` - Create file
- `list_directory("path")` - List directory

**Other Tools:**
- `web_search(query)` - Web search
- `exec(command)` - Execute shell command
- `list_files()`, `glob(pattern)` - Find files

---
Just state your wish and I'll execute the appropriate commands. Type `@Bot hilfe` to learn more.
            """.strip(),
            "channel": "nextcloud_talk",
            "chat_id": chat_id,
            "sender_id": sender_id,
            "metadata": {
                "nextcloud_talk": {
                    "skip": True,
                    "command": "capabilities"
                }
            }
        }
        await self.dispatcher.dispatch(response)


async def main() -> None:
    """Main function - Example application."""
    from nanobot.bus.dispatcher import Dispatcher
    from nanobot.bus.queue import MessageBus
    from nanobot.config.schema import Config
    from nanobot.agent.runner import AgentRunner

    print("🚀 Starting Nextcloud Talk Listener")

    try:
        # Load config
        config = Config()

        # Initialize dispatcher
        dispatcher = Dispatcher(config)

        # Initialize MessageBus
        bus = MessageBus()

        # Register listener
        listener = NextcloudTalkListener(dispatcher)
        dispatcher.add_event_handler("message", listener.on_message)

        # Message router: MessageBus → Dispatcher
        async def route_to_dispatcher():
            while True:
                try:
                    event = await bus.consume_outbound(timeout=0.1)
                    await dispatcher.handle_event(event)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

        # Response router: Dispatcher → MessageBus
        async def route_dispatcher_to_bus():
            while True:
                try:
                    event = await dispatcher.consume_inbound(timeout=0.1)
                    await bus.publish(event)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

        # Start tasks
        print("📡 Message Router started")
        task1 = asyncio.create_task(route_to_dispatcher())
        task2 = asyncio.create_task(route_dispatcher_to_bus())

        # Send test messages (wait 2 seconds)
        print("⏳ Waiting 2 seconds, then sending test messages...")
        await asyncio.sleep(2)

        from nanobot.bus.events import InboundMessage
        test_messages = [
            {
                "type": "text",
                "content": "@Bot hilfe",
                "sender_id": "testuser1",
                "chat_id": "testtoken123",
                "metadata": {
                    "channel": "nextcloud_talk",
                    "source": "nextcloud_talk"
                }
            },
            {
                "type": "text",
                "content": "@Bot status",
                "sender_id": "testuser1",
                "chat_id": "testtoken123",
                "metadata": {
                    "channel": "nextcloud_talk",
                    "source": "nextcloud_talk"
                }
            },
            {
                "type": "text",
                "content": "git status",
                "sender_id": "testuser1",
                "chat_id": "testtoken123",
                "metadata": {
                    "channel": "nextcloud_talk",
                    "source": "nextcloud_talk"
                }
            },
        ]

        for msg in test_messages:
            test_message = InboundMessage(**msg)
            await bus.publish(test_message)
            await asyncio.sleep(0.5)

        print("✅ Test messages sent")
        print("⏳ Waiting 3 seconds for responses...")
        await asyncio.sleep(3)

        print("👋 All done! Listener will exit...")

        # Exit
        task1.cancel()
        task2.cancel()

    except Exception as e:
        logger.exception("Error in listener: {}", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())