"""Event-Listener für Nextcloud Talk Channel.

Dieses Beispiel zeigt, wie du einen eigenen Listener implementieren kannst,
der auf Nachrichten aus Nextcloud Talk reagiert.
"""

import asyncio
from loguru import logger
from nanobot.bus.events import Event
from nanobot.bus.dispatcher import Dispatcher


class NextcloudTalkListener:
    """Beispiel-Listener für Nextcloud Talk Nachrichten.

    Dieser Listener verarbeitet:
    - Hilfekommandos (@Bot hilfe)
    - Statusanfragen (@Bot status)
    - Systemfragen (@Bot was kannst du)
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
        """Verarbeite neue Nachricht von Nextcloud Talk."""
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
                logger.warning("Ungültige Nachricht: sender_id fehlt")
                return

            # Raum-Whitelist prüfen
            if chat_id not in self.allowed_rooms:
                logger.debug(
                    "Room {} not in allowed list. Allowed rooms: {}",
                    chat_id,
                    self.allowed_rooms,
                )
                return

            # Nachricht verarbeiten
            await self._process_message(content, sender_id, chat_id)

        except Exception as e:
            logger.exception("Fehler beim Verarbeiten der Nachricht: {}", e)

    async def _process_message(
        self, content: str, sender_id: str, chat_id: str
    ) -> None:
        """Verarbeite Nachricht basierend auf Inhalt."""
        content_lower = content.lower().strip()

        # Überprüfen, ob es ein bekanntes Kommando ist
        for command, handler in self.commands.items():
            if command in content_lower:
                await handler(content, sender_id, chat_id)
                return

        # Falls kein bekanntes Kommando, Hilfemeldung schicken
        if not content.lower().startswith("@"):
            await self._send_help(content, sender_id, chat_id)

    async def _send_help(self, content: str, sender_id: str, chat_id: str) -> None:
        """Sende Hilfemeldung."""
        response = {
            "type": "text",
            "content": """
**Hallo! Ich bin dein Nanobot! 🤖**

**Verfügbare Befehle:**
- `@Bot hilfe` oder `@Bot help` - Zeigt diese Liste
- `@Bot status` - Zeigt Systemstatus
- `@Bot info` - Zeigt Agent-Informationen
- `@Bot capabilities` - Zeigt was du kannst

**Beispiele:**
- `@Bot status` - Systemstatus abrufen
- `@Bot was kannst du` - Meine Fähigkeiten sehen

Wenn du Git-Befehle ausführen oder Dateien bearbeiten willst, schreib einfach den Befehl direkt. Ich richte mich nach deinem Ziel.
            """.strip(),
            "channel": "nextcloud_talk",
            "chat_id": chat_id,
            "sender_id": sender_id,
            "metadata": {"nextcloud_talk": {"skip": True, "command": "hilfe"}},
        }
        await self.dispatcher.dispatch(response)

    async def _send_status(self, content: str, sender_id: str, chat_id: str) -> None:
        """Sende Systemstatus."""
        from datetime import datetime

        now = datetime.now().isoformat()

        response = {
            "type": "text",
            "content": f"""
**Systemstatus**

---
**Zeit:** {now}

**Nextcloud Talk Channel:**
- Status: ✅ **Aktiv**
- Bot Secret: ✅ **Konfiguriert**
- Gateway Port: **18790**
- Webhook-Pfad: `/webhook/nextcloud_talk`
- Raum-Policy: **open**

**Nextcloud:**
- Base URL: {self.dispatcher.config.channels.nextcloud_talk.base_url or "Nicht konfiguriert"}
- Verfügbare Features: webhook, response

---
Die Antwort erfolgt von {sender_id} in Raum {chat_id}.
            """.strip(),
            "channel": "nextcloud_talk",
            "chat_id": chat_id,
            "sender_id": sender_id,
            "metadata": {"nextcloud_talk": {"skip": True, "command": "status"}},
        }
        await self.dispatcher.dispatch(response)

    async def _send_info(self, content: str, sender_id: str, chat_id: str) -> None:
        """Sende Agent-Informationen."""
        response = {
            "type": "text",
            "content": """
**Agent-Informationen**

---
**Agent:** Nanobot (OpenCode-Agent)
**Version:** 1.0.0
**Model:** anthropic/claude-opus-4-5 (Standardeinstellung)

**Konfigurierte Kanäle:**
- Nextcloud Talk: ✅ (Aktiv)

**Arbeitsbereich:** ~/.nanobot/workspace

---
**Was kann ich:**
- Git-Befehle ausführen (clone, status, log, etc.)
- Dateien lesen, bearbeiten, erstellen
- Web-Suche durchführen
- Shell-Befehle ausführen

**Bedienung:**
Du kannst Git-Befehle direkt eingeben, z.B.:
- `git status` - Zeigt Git-Status
- `git log -5` - Zeigt letzten 5 Commits
- `git diff` - Zeigt Änderungen
- `git checkout -b feature` - Erstellt neue Branch

Du kannst auch Dateien bearbeiten oder Informationen anfordern.
            """.strip(),
            "channel": "nextcloud_talk",
            "chat_id": chat_id,
            "sender_id": sender_id,
            "metadata": {"nextcloud_talk": {"skip": True, "command": "info"}},
        }
        await self.dispatcher.dispatch(response)

    async def _send_capabilities(
        self, content: str, sender_id: str, chat_id: str
    ) -> None:
        """Sende verfügbare Fähigkeiten."""
        response = {
            "type": "text",
            "content": """
**Meine Fähigkeiten**

---
**Git-Befehle:**
- `git status` - Status
- `git log` - Logs
- `git diff` - Änderungen
- `git branch`, `git checkout`, `git merge`
- `git clone`, `git pull`, `git push`

**Datei-Operationen:**
- `read_file("path")` - Datei lesen
- `edit_file("path", content)` - Datei bearbeiten
- `write_file("path", content)` - Datei erstellen
- `list_directory("path")` - Verzeichnis auflisten

**Andere Tools:**
- `web_search(query)` - Web-Suche
- `exec(command)` - Shell-Befehle ausführen
- `list_files()`, `glob(pattern)` - Dateien finden

---
Einfach deinen Wunsch angeben und ich werde die entsprechenden Befehle ausführen. Schreib einfach `@Bot hilfe`, um mehr zu erfahren.
            """.strip(),
            "channel": "nextcloud_talk",
            "chat_id": chat_id,
            "sender_id": sender_id,
            "metadata": {"nextcloud_talk": {"skip": True, "command": "capabilities"}},
        }
        await self.dispatcher.dispatch(response)


async def main() -> None:
    """Hauptfunktion - Beispielanwendung."""
    from nanobot.bus.dispatcher import Dispatcher
    from nanobot.bus.queue import MessageBus
    from nanobot.config.schema import Config
    from nanobot.agent.runner import AgentRunner

    print("🚀 Starte Nextcloud Talk Listener")

    try:
        # Config laden
        config = Config()

        # Dispatcher initialisieren
        dispatcher = Dispatcher(config)

        # MessageBus initialisieren
        bus = MessageBus()

        # Listener registrieren
        listener = NextcloudTalkListener(dispatcher)
        dispatcher.add_event_handler("message", listener.on_message)

        # Nachricht Router: MessageBus → Dispatcher
        async def route_to_dispatcher():
            while True:
                try:
                    event = await bus.consume_outbound(timeout=0.1)
                    await dispatcher.handle_event(event)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

        # Antwort Router: Dispatcher → MessageBus
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
        print("📡 Nachricht Router gestartet")
        task1 = asyncio.create_task(route_to_dispatcher())
        task2 = asyncio.create_task(route_dispatcher_to_bus())

        # Test-Nachricht senden (Warte 2 Sekunden)
        print("⏳ Warte 2 Sekunden, dann Test-Nachricht senden...")
        await asyncio.sleep(2)

        from nanobot.bus.events import InboundMessage

        test_messages = [
            {
                "type": "text",
                "content": "@Bot hilfe",
                "sender_id": "testuser1",
                "chat_id": "testtoken123",
                "metadata": {"channel": "nextcloud_talk", "source": "nextcloud_talk"},
            },
            {
                "type": "text",
                "content": "@Bot status",
                "sender_id": "testuser1",
                "chat_id": "testtoken123",
                "metadata": {"channel": "nextcloud_talk", "source": "nextcloud_talk"},
            },
            {
                "type": "text",
                "content": "git status",
                "sender_id": "testuser1",
                "chat_id": "testtoken123",
                "metadata": {"channel": "nextcloud_talk", "source": "nextcloud_talk"},
            },
        ]

        for msg in test_messages:
            test_message = InboundMessage(**msg)
            await bus.publish(test_message)
            await asyncio.sleep(0.5)

        print("✅ Test-Nachrichten gesendet")
        print("⏳ Warte 3 Sekunden für Antworten...")
        await asyncio.sleep(3)

        print("👋 Alles erledigt! Listener wird beendet...")

        # Beenden
        task1.cancel()
        task2.cancel()

    except Exception as e:
        logger.exception("Fehler im Listener: {}", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
