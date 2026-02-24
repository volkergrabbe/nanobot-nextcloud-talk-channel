# agent.md – OpenCode: Nextcloud Talk Channel für nanobot (volkergrabbe/nanobot)

## Aufgabe

Erstelle einen vollständigen `nextcloud_talk` Channel. Es sind **exakt 3 Dateien** zu ändern/erstellen.
Alle anderen Dateien bleiben unverändert.

---

## Projektkontext

- **Logger:** `from loguru import logger` (NIEMALS `import logging`)
- **HTTP-Client:** `httpx.AsyncClient` (NIEMALS `aiohttp`)
- **Base-Klasse:** `nanobot.channels.base.BaseChannel` – MUSS vererbt werden
- **Config-Base:** Klasse `Base(BaseModel)` mit `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)`
- **Field-Standard:** `Field(default_factory=list)` für Listen (wie alle anderen Configs)
- **Gateway-Port:** Standard ist `18790` – bereits in `GatewayConfig` definiert
- **`self._running`:** Kommt aus `BaseChannel` – nicht neu definieren

---

## Datei 1: `nanobot/config/schema.py` – ÄNDERN

### Wo einfügen?
Nach der `MatrixConfig`-Klasse (Zeile ~nach `maxMediaBytes: int = 10485760`),
VOR der `ChannelsConfig`-Klasse.

### Neue Klasse (exakter Code):

```python
class NextcloudTalkConfig(Base):
    """Nextcloud Talk channel configuration using the Talk Bot Webhook API."""

    enabled: bool = False
    base_url: str = ""              # e.g. "https://cloud.example.com"
    bot_secret: str = ""            # Shared Secret from: occ talk:bot:install (min. 40 chars)
    webhook_path: str = "/webhook/nextcloud_talk"
    allow_from: list[str] = Field(default_factory=list)   # Nextcloud user IDs (empty = all)
    allowRooms: list[str] = Field(default_factory=list)   # Conversation tokens (empty = all)
    roomPolicy: str = "open"        # "open" | "mention"
```

### In `ChannelsConfig` ergänzen:
Nach der Zeile `matrix: MatrixConfig = Field(default_factory=MatrixConfig)` einfügen:

```python
    nextcloud_talk: NextcloudTalkConfig = Field(default_factory=NextcloudTalkConfig)
```

---

## Datei 2: `nanobot/channels/manager.py` – ÄNDERN

### Wo einfügen?
Nach dem Matrix-Block (letzter Block in `_init_channels()`), direkt vor `async def _start_channel`.

### Neuer Block (exakter Code):

```python
        # Nextcloud Talk channel
        if self.config.channels.nextcloud_talk.enabled:
            try:
                from nanobot.channels.nextcloud_talk import NextcloudTalkChannel
                self.channels["nextcloud_talk"] = NextcloudTalkChannel(
                    self.config.channels.nextcloud_talk, self.bus
                )
                logger.info("Nextcloud Talk channel enabled")
            except ImportError as e:
                logger.warning("Nextcloud Talk channel not available: {}", e)
```

---

## Datei 3: `nanobot/channels/nextcloud_talk.py` – NEU ERSTELLEN

Erstelle diese Datei vollständig. Orientiere dich am Stil von `discord.py` (httpx, loguru, BaseChannel).

### Vollständiger Code:

```python
"""Nextcloud Talk channel implementation using the Talk Bot Webhook API."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
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
        self._webhook_task: asyncio.Task | None = None

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

        # Start aiohttp webhook server
        try:
            from aiohttp import web

            app = web.Application()
            app.router.add_post(
                self.config.webhook_path, self._handle_webhook
            )
            runner = web.AppRunner(app)
            await runner.setup()

            # Reuse the gateway port from GatewayConfig if available, otherwise 18790
            port = getattr(self.config, "webhook_port", 18790)
            site = web.TCPSite(runner, "0.0.0.0", port)
            await site.start()
            self._runner = runner
            logger.info(
                "Nextcloud Talk channel started – listening on port {} path {}",
                port,
                self.config.webhook_path,
            )
            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1)
        except ImportError:
            logger.error(
                "Nextcloud Talk: aiohttp not installed. Run: pip install aiohttp"
            )
        except Exception as e:
            logger.error("Nextcloud Talk: webhook server error: {}", e)
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the Nextcloud Talk channel."""
        self._running = False
        if self._http:
            await self._http.aclose()
            self._http = None
        if hasattr(self, "_runner") and self._runner:
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

        # Split long messages (Talk has a practical limit)
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

        # Build body
        reference_id = hashlib.sha256(text.encode()).hexdigest()
        body = json.dumps({"message": text, "referenceId": reference_id})

        # Build HMAC signature: HMAC-SHA256(random + body, secret)
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

            # Validate HMAC signature
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

            # Only process "Create" events (new messages)
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

            # Check allowFrom whitelist
            if not self.is_allowed(sender_id):
                logger.info(
                    "Nextcloud Talk: user {} not in allow_from – ignored", sender_id
                )
                return web.Response(status=200, text="OK")

            # Check allowRooms whitelist
            if self.config.allowRooms and conversation_token not in self.config.allowRooms:
                logger.info(
                    "Nextcloud Talk: room {} not in allowRooms – ignored",
                    conversation_token,
                )
                return web.Response(status=200, text="OK")

            # Check roomPolicy (mention required?)
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_allowed(self, sender_id: str) -> bool:
        """Check if a sender is in the allow_from whitelist."""
        if not self.config.allow_from:
            return True
        return sender_id in self.config.allow_from


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

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
```

---

## Exakte Änderungen in `schema.py`

```diff
# Nach MatrixConfig, vor ChannelsConfig:
+class NextcloudTalkConfig(Base):
+    """Nextcloud Talk channel configuration using the Talk Bot Webhook API."""
+    enabled: bool = False
+    base_url: str = ""
+    bot_secret: str = ""
+    webhook_path: str = "/webhook/nextcloud_talk"
+    allow_from: list[str] = Field(default_factory=list)
+    allowRooms: list[str] = Field(default_factory=list)
+    roomPolicy: str = "open"

# In ChannelsConfig, nach matrix:
-    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
+    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
+    nextcloud_talk: NextcloudTalkConfig = Field(default_factory=NextcloudTalkConfig)
```

---

## Nextcloud-Server: Bot registrieren

```bash
php occ talk:bot:install \
  "Nanobot" \
  "dein-shared-secret-mindestens-40-zeichen" \
  "https://nanobot.example.com/webhook/nextcloud_talk" \
  --feature webhook \
  --feature response

php occ talk:bot:install-in-room "Nanobot" "<raum-token>"
```

---

## `~/.nanobot/config.json`

```json
{
  "channels": {
    "nextcloud_talk": {
      "enabled": true,
      "baseUrl": "https://cloud.example.com",
      "botSecret": "dein-shared-secret-mindestens-40-zeichen",
      "webhookPath": "/webhook/nextcloud_talk",
      "allowFrom": ["volker"],
      "allowRooms": [],
      "roomPolicy": "open"
    }
  }
}
```

> **Hinweis:** Keys in `config.json` sind camelCase (wegen `alias_generator=to_camel` in `Base`).

---

## Validierung

```bash
# 1. Schema
python -c "from nanobot.config.schema import NextcloudTalkConfig, ChannelsConfig; c = ChannelsConfig(); print(c.nextcloud_talk)"

# 2. Channel-Import
python -c "from nanobot.channels.nextcloud_talk import NextcloudTalkChannel; print('OK')"

# 3. Manager
python -c "from nanobot.channels.manager import ChannelManager; print('OK')"

# 4. Gateway
nanobot gateway
# Erwartete Ausgabe: "Nextcloud Talk channel started – listening on port 18790 path /webhook/nextcloud_talk"

# 5. Webhook testen
SECRET="dein-shared-secret"
RANDOM_VAL=$(openssl rand -hex 16)
BODY='{"type":"Create","actor":{"type":"users","id":"volker","displayName":"Volker Grabbe"},"object":{"type":"comment","id":"1","name":"Volker Grabbe","content":"Hallo Bot!","mediaType":"text/markdown"},"target":{"type":"room","id":"testtoken123","name":"Test"}}'
SIG=$(echo -n "${RANDOM_VAL}${BODY}" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -X POST http://localhost:18790/webhook/nextcloud_talk \
  -H "Content-Type: application/json" \
  -H "X-Nextcloud-Talk-Random: $RANDOM_VAL" \
  -H "X-Nextcloud-Talk-Signature: $SIG" \
  -d "$BODY"
```

---

## Zusammenfassung der Änderungen

| Datei | Aktion | Was |
|-------|--------|-----|
| `nanobot/channels/nextcloud_talk.py` | NEU | Vollständige Channel-Klasse |
| `nanobot/config/schema.py` | +8 Zeilen | `NextcloudTalkConfig` + 1 Zeile in `ChannelsConfig` |
| `nanobot/channels/manager.py` | +8 Zeilen | 1 Block am Ende von `_init_channels()` |

**Nicht anfassen:** Alle anderen Dateien.
