"""Nextcloud Talk channel implementation using the Talk Bot Webhook API."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from typing import Any

import httpx
from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import NextcloudTalkConfig


class NextcloudTalkChannel(BaseChannel):
    """Nextcloud Talk channel using the Talk Bot Webhook API."""

    name = "nextcloud_talk"

    def __init__(self, config: NextcloudTalkConfig, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config: NextcloudTalkConfig = config
        self._http: httpx.AsyncClient | None = None
        self._runner = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the Nextcloud Talk webhook listener."""
        if not self.config.base_url:
            logger.error("Nextcloud Talk: base_url not configured")
            return
        if not self.config.bot_secret:
            logger.error("Nextcloud Talk: bot_secret not configured")
            return

        self._running = True
        self._http = httpx.AsyncClient(timeout=30.0)
        self._webhook_port = getattr(self.config, "webhook_port", 18790)

        try:
            from aiohttp import web

            app = web.Application()
            app.router.add_post(self.config.webhook_path, self._handle_webhook)
            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(runner, "0.0.0.0", self._webhook_port)
            await site.start()
            self._runner = runner
            logger.info(
                "Nextcloud Talk channel started – listening on port {} path {}",
                self._webhook_port,
                self.config.webhook_path,
            )
            while self._running:
                await asyncio.sleep(1)
        except ImportError:
            logger.error(
                "Nextcloud Talk: aiohttp not installed. Run: pip install aiohttp"
            )
        except Exception as e:
            logger.error("Nextcloud Talk: webhook server error: {}", e)

    async def stop(self) -> None:
        """Stop the Nextcloud Talk channel."""
        self._running = False
        if self._http:
            await self._http.aclose()
            self._http = None
        if self._runner:
            try:
                await self._runner.cleanup()
            except Exception as e:
                logger.warning("Nextcloud Talk: cleanup error: {}", e)
            self._runner = None
        logger.info("Nextcloud Talk channel stopped")

    # ------------------------------------------------------------------
    # Outbound: nanobot → Nextcloud Talk
    # ------------------------------------------------------------------

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message to a Nextcloud Talk conversation."""
        if not self._http:
            logger.warning("Nextcloud Talk: HTTP client not initialized")
            return

        conversation_token = msg.chat_id
        if not conversation_token:
            logger.warning("Nextcloud Talk: no chat_id (conversation token) in message")
            return

        chunks = _split_message(msg.content or "")
        if not chunks:
            return

        for chunk in chunks:
            await self._send_message(conversation_token, chunk)

    async def _send_message(self, token: str, text: str) -> None:
        """Send a single message chunk to a Nextcloud Talk room."""
        if not self._http:
            return

        url = (
            f"{self.config.base_url.rstrip('/')}"
            f"/ocs/v2.php/apps/spreed/api/v1/bot/{token}/message"
        )

        reference_id = hashlib.sha256(text.encode()).hexdigest()
        body = json.dumps({"message": text, "referenceId": reference_id})

        random_value = os.urandom(32).hex()
        signature = hmac.new(
            self.config.bot_secret.encode(),
            (random_value + body).encode(),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "X-Nextcloud-Talk-Bot-Random": random_value,
            "X-Nextcloud-Talk-Bot-Signature": signature,
            "OCS-APIRequest": "true",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            response = await self._http.post(url, content=body, headers=headers)
            if response.status_code not in (200, 201):
                logger.error(
                    "Nextcloud Talk: send failed – status {} body {}",
                    response.status_code,
                    response.text[:200],
                )
            else:
                logger.debug("Nextcloud Talk: message sent to room {}", token)
        except Exception as e:
            logger.error("Nextcloud Talk: error sending message: {}", e)

    # ------------------------------------------------------------------
    # Inbound: Nextcloud Talk → nanobot
    # ------------------------------------------------------------------

    async def _handle_webhook(self, request: Any) -> Any:
        """Handle incoming webhook events from Nextcloud Talk."""
        from aiohttp import web

        try:
            body_bytes = await request.read()
            body_str = body_bytes.decode("utf-8")

            random_header = request.headers.get("X-Nextcloud-Talk-Random", "")
            sig_header = request.headers.get("X-Nextcloud-Talk-Signature", "")

            expected = hmac.new(
                self.config.bot_secret.encode(),
                (random_header + body_str).encode(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(sig_header.lower(), expected.lower()):
                logger.warning("Nextcloud Talk: invalid signature – request rejected")
                return web.Response(status=401, text="Unauthorized")

            data = json.loads(body_str)

            if data.get("type") != "Create":
                return web.Response(status=200, text="OK")

            actor = data.get("actor", {})
            obj = data.get("object", {})
            target = data.get("target", {})

            sender_id = actor.get("id", "")
            content = obj.get("content", "").strip()
            conversation_token = target.get("id", "")

            if not sender_id or not content or not conversation_token:
                logger.debug("Nextcloud Talk: incomplete webhook payload – ignored")
                return web.Response(status=200, text="OK")

            if not self.is_allowed(sender_id):
                logger.info(
                    "Nextcloud Talk: user {} not in allow_from – ignored", sender_id
                )
                return web.Response(status=200, text="OK")

            if (
                self.config.allowRooms
                and conversation_token not in self.config.allowRooms
            ):
                logger.info(
                    "Nextcloud Talk: room {} not in allowRooms – ignored",
                    conversation_token,
                )
                return web.Response(status=200, text="OK")

            if self.config.roomPolicy == "mention":
                if not _is_mention(content):
                    logger.debug(
                        "Nextcloud Talk: no mention detected – roomPolicy=mention"
                    )
                    return web.Response(status=200, text="OK")
                content = _strip_mention(content)

            logger.debug(
                "Nextcloud Talk: message from {} in room {}: {}...",
                sender_id,
                conversation_token,
                content[:50],
            )

            await self._handle_message(
                sender_id=sender_id,
                chat_id=conversation_token,
                content=content,
                metadata={
                    "nextcloud_talk": {
                        "object_id": obj.get("id", ""),
                        "room_name": target.get("name", ""),
                        "actor_display_name": actor.get("displayName", ""),
                        "media_type": obj.get("mediaType", "text/plain"),
                    }
                },
            )

            return web.Response(status=200, text="OK")

        except json.JSONDecodeError:
            logger.warning("Nextcloud Talk: invalid JSON in webhook body")
            return web.Response(status=400, text="Bad Request")
        except Exception as e:
            logger.exception("Nextcloud Talk: error handling webhook: {}", e)
            return web.Response(status=500, text="Internal Server Error")

    def is_allowed(self, sender_id: str) -> bool:
        """Check if a sender is in the allow_from whitelist."""
        if not self.config.allow_from:
            return True
        return sender_id in self.config.allow_from


def _split_message(content: str, max_len: int = 32000) -> list[str]:
    """Split content into chunks within max_len, preferring line breaks."""
    if not content:
        return []
    if len(content) <= max_len:
        return [content]
    chunks: list[str] = []
    while content:
        if len(content) <= max_len:
            chunks.append(content)
            break
        cut = content[:max_len]
        pos = cut.rfind("\n")
        if pos <= 0:
            pos = cut.rfind(" ")
        if pos <= 0:
            pos = max_len
        chunks.append(content[:pos])
        content = content[pos:].lstrip()
    return chunks


def _is_mention(content: str) -> bool:
    """Check if message starts with a @mention (simple heuristic)."""
    return content.strip().startswith("@")


def _strip_mention(content: str) -> str:
    """Remove leading @mention from message content."""
    parts = content.strip().split(None, 1)
    if len(parts) > 1 and parts[0].startswith("@"):
        return parts[1].strip()
    return content.strip()
