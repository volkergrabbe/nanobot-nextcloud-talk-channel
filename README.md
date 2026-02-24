# Nextcloud Talk Channel for nanobot

Dies ist ein `nextcloud_talk` Channel für nanobot (OpenCode-Agent).

## Überblick

Dieser Channel ermöglicht die Integration von [Nextcloud Talk](https://nextcloud.com/apps/spreed/) in den nanobot-Agent. Er verwendet die offizielle **Talk Bot Webhook API** von Nextcloud.

**Features:**
- Webhook-basiertes Event-Handling (kein dauerhafter WebSocket-Verbindung)
- HMAC-Signatur-Validierung
- Konfigurierbarer `roomPolicy` (open/mention)
- Whitelist für Benutzer und Räume
- Unterstützung für lange Nachrichten (chunking)
- Vollständige Integration mit dem nanobot MessageBus

## System-Architektur

```
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│  Nextcloud Talk │ <------> │  nanobot Agent  │ <------> │  I/O/System     │
│  (Webhook API)  │          │  (OpenCode)     │          │  /tools/git     │
└─────────────────┘          └─────────────────┘          └─────────────────┘
          ▲                              ▲
          │                              │
    OCS API Bot Endpunkte          MessageBus
    (ngrok/port-forward)
```

## Installation

### 1. Voraussetzungen

- Python 3.10+
- Nextcloud Talk mit aktiviertem Bot-Feature
- Aiohttp für den Webhook-Server

### 2. Abhängigkeiten installieren

```bash
pip install aiohttp
```

### 3. Bot in Nextcloud installieren

Führe auf dem Nextcloud-Server aus:

```bash
# Bot registrieren
php occ talk:bot:install \
  "Nanobot" \
  "dein-shared-secret-mindestens-40-zeichen" \
  "https://nanobot.example.com/webhook/nextcloud_talk" \
  --feature webhook \
  --feature response

# Bot in einen Raum einbinden
php occ talk:bot:install-in-room "Nanobot" "<raum-token>"
```

**Wichtige Details:**
- Der `bot_secret` muss mindestens 40 Zeichen lang sein
- Der `webhook_url` sollte öffentlich erreichbar sein (ngrok, port-forward, Reverse Proxy)
- Nutze die Features `webhook` und `response` für das volle Funktionsumfang

## Konfiguration

### Datei: `~/.nanobot/config.json`

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

### Konfigurationsparameter

| Parameter | Typ | Default | Beschreibung |
|-----------|-----|---------|-------------|
| `enabled` | bool | `false` | Channel aktivieren |
| `base_url` | string | `""` | Nextcloud URL (z.B. "https://cloud.example.com") |
| `botSecret` | string | `""` | Shared Secret von `occ talk:bot:install` (min. 40 Zeichen) |
| `webhookPath` | string | `"/webhook/nextcloud_talk"` | Webhook-Pfad auf dem nanobot-Gateway |
| `allowFrom` | list[str] | `[]` | Nextcloud User IDs erlaubt (leer = alle) |
| `allowRooms` | list[str] | `[]` | Konversations-Token erlaubt (leer = alle) |
| `roomPolicy` | string | `"open"` | `"open"` (alle Nachrichten) oder `"mention"` (@Bot erforderlich) |

**Important:**
- Keys in `config.json` sind camelCase (wegen `alias_generator=to_camel`)
- `allowRooms` beinhaltet die Konversationstoken, nicht die Raum-IDs

## Event-Listener schreiben

### Beispiel: Nachrichten ohne @Bot reagieren

Erstelle eine Datei `nextcloud_talk_listener.py`:

```python
"""Event-Listener für Nextcloud Talk Channel."""

import asyncio
from loguru import logger
from nanobot.bus.events import Event
from nanobot.bus.dispatcher import Dispatcher


class NextcloudTalkListener:
    """Beispiel-Listener für Nextcloud Talk Nachrichten."""

    def __init__(self, dispatcher: Dispatcher) -> None:
        self.dispatcher = dispatcher

    async def on_message(self, message: Event) -> None:
        """Verarbeite neue Nachricht."""
        logger.info(
            "Nanobot received message from {} in room {}",
            message.sender_id,
            message.chat_id
        )

        # Nachrichten aus bestimmten Räumen filtern
        allowed_rooms = {"testtoken123"}
        if message.chat_id not in allowed_rooms:
            logger.debug("Room {} not in allowed list", message.chat_id)
            return

        # Beispiel: Antwort basierend auf Inhalt
        content = message.content.lower()
        if "hilfe" in content:
            await self._send_help(message)
        elif "status" in content:
            await self._send_status(message)

    async def _send_help(self, message: Event) -> None:
        """Sende Hilfemeldung."""
        response = {
            "type": "text",
            "content": "Hallo! Ich bin bereit. Nutze 'status' für Systeminfo.",
            "channel": "nextcloud_talk",
            "chat_id": message.chat_id,
            "sender_id": message.sender_id,
        }
        await self.dispatcher.dispatch(response)

    async def _send_status(self, message: Event) -> None:
        """Sende Systemstatus."""
        response = {
            "type": "text",
            "content": """
Systemstatus:
- Nextcloud Talk Channel: ✅ Aktiv
- Bot Secret: ✅ Konfiguriert
- Gateway Port: 18790

Du kannst auch Git-Befehle oder Code bearbeiten.
            """.strip(),
            "channel": "nextcloud_talk",
            "chat_id": message.chat_id,
            "sender_id": message.sender_id,
        }
        await self.dispatcher.dispatch(response)


async def main() -> None:
    """Hauptfunktion."""
    from nanobot.bus.dispatcher import Dispatcher
    from nanobot.bus.queue import MessageBus
    from nanobot.config.schema import Config

    # Config laden
    config = Config()

    # Dispatcher und MessageBus initialisieren
    dispatcher = Dispatcher(config)
    bus = MessageBus()

    # Listener registrieren
    listener = NextcloudTalkListener(dispatcher)
    dispatcher.add_event_handler("message", listener.on_message)

    # Nachrichten von MessageBus an Dispatcher senden
    async def route_to_dispatcher():
        while True:
            try:
                event = await bus.consume_outbound(timeout=0.1)
                await dispatcher.handle_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    # Dispatcher Ausgaben an MessageBus senden
    async def route_dispatcher_to_bus():
        while True:
            try:
                event = await dispatcher.consume_inbound(timeout=0.1)
                await bus.publish(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    # Tasks starten
    task1 = asyncio.create_task(route_to_dispatcher())
    task2 = asyncio.create_task(route_dispatcher_to_bus())

    # Nachrichten simulieren
    await asyncio.sleep(2)
    from nanobot.bus.events import InboundMessage
    test_message = InboundMessage(
        type="text",
        content="hilfe",
        sender_id="volker",
        chat_id="testtoken123",
        metadata={
            "channel": "nextcloud_talk",
            "source": "nextcloud_talk"
        }
    )
    await bus.publish(test_message)

    # Warten
    await asyncio.sleep(2)

    # Beenden
    task1.cancel()
    task2.cancel()


if __name__ == "__main__":
    asyncio.run(main())
```

### Beispiel: Nachrichten mit @Bot reagieren

Die `roomPolicy` kann auf `"mention"` gesetzt werden:

```json
{
  "channels": {
    "nextcloud_talk": {
      "enabled": true,
      "baseUrl": "https://cloud.example.com",
      "botSecret": "dein-shared-secret-mindestens-40-zeichen",
      "webhookPath": "/webhook/nextcloud_talk",
      "roomPolicy": "mention"
    }
  }
}
```

Damit der Bot nur auf Nachrichten antwortet, die mit `@Bot` beginnen.

## Validierung

### 1. Schema-Validierung

```bash
python -c "from nanobot.config.schema import NextcloudTalkConfig, ChannelsConfig; c = ChannelsConfig(); print(c.nextcloud_talk)"
```

### 2. Channel-Import

```bash
python -c "from nanobot.channels.nextcloud_talk import NextcloudTalkChannel; print('OK')"
```

### 3. Manager-Integration

```bash
python -c "from nanobot.channels.manager import ChannelManager; print('OK')"
```

### 4. Gateway testen

```bash
nanobot gateway
```

Erwartete Ausgabe:
```
Nextcloud Talk channel started – listening on port 18790 path /webhook/nextcloud_talk
```

### 5. Webhook testen

```bash
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

Erwartet: `{"status":200,"text":"OK"}`

## Webhook-Verhalten

### Event-Types

Der Bot reagiert nur auf Events vom Typ `"Create"`:

```json
{
  "type": "Create",
  "actor": {
    "type": "users",
    "id": "volker",
    "displayName": "Volker Grabbe"
  },
  "object": {
    "type": "comment",
    "id": "1",
    "content": "Hallo Bot!",
    "mediaType": "text/markdown"
  },
  "target": {
    "type": "room",
    "id": "testtoken123",
    "name": "Test"
  }
}
```

### Metadata

Nachrichten werden mit folgendem Metadata-Payload an den MessageBus gesendet:

```json
{
  "nextcloud_talk": {
    "object_id": "1",
    "room_name": "Test",
    "actor_display_name": "Volker Grabbe",
    "media_type": "text/markdown"
  }
}
```

### HMAC-Signatur

Jede Webhook-Anfrage enthält eine HMAC-SHA256-Signatur:

```
X-Nextcloud-Talk-Random: {32-byte random string}
X-Nextcloud-Talk-Signature: {hex HMAC-SHA256(random + body, bot_secret)}
```

Der Bot validiert die Signatur und lehnt ungültige Anfragen ab (HTTP 401).

## Router-Erweiterung (Optional)

Füge die folgenden Routes zum Router hinzu (beim `ChannelManager`):

```python
from nanobot.bus.events import Event

# Hilfsfunktion zum Senden an Nextcloud Talk
async def send_to_nextcloud_talk(
    dispatcher: Dispatcher,
    sender_id: str,
    chat_id: str,
    content: str
) -> None:
    """Sende Nachricht an Nextcloud Talk Konversation."""
    response = Event(
        type="text",
        content=content,
        sender_id=sender_id,
        chat_id=chat_id,
        metadata={
            "channel": "nextcloud_talk",
            "_no_nob": True,
            "nextcloud_talk": {
                "skip": True
            }
        }
    )
    await dispatcher.dispatch(response)
```

## Sicherheit

- **Bot Secret:** Mindestens 40 Zeichen
- **AllowList:** Nutze `allowFrom` und `allowRooms` für Whitelist
- **RoomPolicy:** `"mention"` erfordert @Bot in der Nachricht
- **HMAC-Validierung:** Jede Webhook-Anfrage wird validiert

## Troubleshooting

### Fehler: `base_url not configured`

Stelle sicher, dass `baseUrl` in der Config gesetzt ist (ohne Slash am Ende).

### Fehler: `bot_secret not configured`

Die `botSecret` muss das Shared Secret von `occ talk:bot:install` sein (min. 40 Zeichen).

### Fehler: `aiohttp not installed`

```bash
pip install aiohttp
```

### Nachricht wird nicht empfangen

- Prüfe `roomPolicy` (nur `open` oder `mention`)
- Überprüfe `allowFrom` und `allowRooms` Whitelisten
- Siehe Log für Debugging: `logger.debug("Nextcloud Talk: ...")`

### Nachricht wird nicht gesendet

- Prüfe `base_url` und URL-Endpunkt
- Siehe Log: `logger.error("Nextcloud Talk: error sending message: {}")`
- Nachrichten werden in 32000-Charakter-Blöcken gesendet

## Nextcloud-Konfiguration

### Fehlerhafte Installation

```bash
# Bot deinstallieren
php occ talk:bot:delete --bot-name "Nanobot"

# Neues Bot erstellen
php occ talk:bot:install \
  "Nanobot" \
  "dein-shared-secret-mindestens-40-zeichen" \
  "https://nanobot.example.com/webhook/nextcloud_talk" \
  --feature webhook \
  --feature response
```

### Bot in weitere Räume einbinden

```bash
php occ talk:bot:install-in-room "Nanobot" "<raum-token>"
```

### Bot-Features prüfen

```bash
php occ talk:bot:list
```

## Weiterführende Dokumentation

- [Nextcloud Talk Bot API](https://docs.nextcloud.com/server/stable/admin_manual/configuration_user/occ_commands.html#talk-bot-install)
- [nanobot /channels/manager.py](nanobot/channels/manager.py)
- [nanobot/channels/nextcloud_talk.py](nanobot/channels/nextcloud_talk.py)
- [nanobot/config/schema.py](nanobot/config/schema.py)

## Änderungen an den nanobot-Quellcode

| Datei | Änderung |
|-------|----------|
| `nanobot/config/schema.py` | `NextcloudTalkConfig` Klasse + Eintrag in `ChannelsConfig` |
| `nanobot/channels/manager.py` | `NextcloudTalkChannel` initialisierung in `_init_channels()` |
| `nanobot/channels/nextcloud_talk.py` | **Neu** (388 Zeilen) |

## Lizenz

Teil von [nanobot](https://github.com/volkergrabbe/nanobot) OpenSource-Projekt.
