#!/usr/bin/env python3
"""Webhook-Test-Skript für Nextcloud Talk Channel.

Dieses Skript testet den Webhook-Endpunkt mit einer Test-Nachricht.
Benötigt: python3, openssl
"""

import asyncio
import hashlib
import hmac
import json
import os
import subprocess
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Fehler: httpx nicht installiert")
    print("Installiere mit: pip install httpx")
    exit(1)

try:
    from aiohttp import web
except ImportError:
    print("Fehler: aiohttp nicht installiert")
    print("Installiere mit: pip install aiohttp")
    exit(1)


async def test_webhook(port: int = 18790) -> None:
    """Führe einen Webhook-Test durch."""
    print(f"🧪 Starte Webhook-Test-Skript")
    print(f"📡 Gateway Port: {port}")

    # Test-Config ausgeben
    print("\n📋 Test-Details:")
    print(f"   BASE_URL: https://cloud.example.com")
    print(f"   BOT_SECRET: dein-shared-secret-mindestens-40-zeichen")
    print(f"   WEBHOOK_PATH: /webhook/nextcloud_talk")
    print(f"   ROOM_TOKEN: testtoken123")

    # Payload erstellen
    test_payload = {
        "type": "Create",
        "actor": {"type": "users", "id": "testuser1", "displayName": "Test User 1"},
        "object": {
            "type": "comment",
            "id": "1",
            "name": "Test User 1",
            "content": "Hallo Bot! Was kannst du?",
            "mediaType": "text/markdown",
        },
        "target": {"type": "room", "id": "testtoken123", "name": "Test Room"},
    }

    print("\n📤 Test-Payload:")
    print(json.dumps(test_payload, indent=2))

    # Signatur berechnen
    print("\n🔐 HMAC-Signatur-Berechnung:")

    # WICHTIG: Bot-Secret muss aus config.json stammen
    print("   Hinweis: Der Test nutzt ein Platzhalter-Bot-Secret.")
    print(
        "   Stelle sicher, dass du den echten Bot-Secret aus deiner config.json verwendest."
    )

    # Bot-Secret aus config.json lesen (falls vorhanden)
    config_path = Path.home() / ".nanobot" / "config.json"
    if config_path.exists():
        import configparser
        import json

        config_data = json.loads(config_path.read_text())
        bot_secret = (
            config_data.get("channels", {})
            .get("nextcloud_talk", {})
            .get("botSecret", "")
        )
        if bot_secret:
            print(
                f"   ✅ Bot-Secret aus config.json gefunden ({len(bot_secret)} Zeichen)"
            )

    # Test mit Platzhalter
    bot_secret = "test-shared-secret-mindestens-40-zeichen"
    random_value = os.urandom(32).hex()
    body = json.dumps(test_payload)
    signature = hmac.new(
        bot_secret.encode(),
        (random_value + body).encode(),
        hashlib.sha256,
    ).hexdigest()

    print(f"   RANDOM_VALUE: {random_value}")
    print(f"   SIGNATURE: {signature}")

    # Test-Anfrage senden
    print("\n🌐 Sende Test-Anfrage an:")
    url = f"http://localhost:{port}/webhook/nextcloud_talk"

    print(f"   URL: {url}")
    print(f"   HEADERS:")
    print(f"     X-Nextcloud-Talk-Random: {random_value}")
    print(f"     X-Nextcloud-Talk-Signature: {signature}")
    print(f"   BODY: {body[:100]}...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                content=body,
                headers={
                    "X-Nextcloud-Talk-Random": random_value,
                    "X-Nextcloud-Talk-Signature": signature,
                    "Content-Type": "application/json",
                },
            )
            print(f"\n✅ Antwort empfangen:")
            print(f"   Status: {response.status_code}")
            print(f"   Body: {response.text[:200]}...")

            if response.status_code == 200:
                print("\n🎉 Webhook-Test erfolgreich!")
            else:
                print(
                    f"\n❌ Webhook-Test fehlgeschlagen! Status: {response.status_code}"
                )

    except httpx.ConnectError:
        print("\n❌ Verbindung fehlgeschlagen!")
        print(f"   Stellen sicher, dass der nanobot Gateway auf Port {port} läuft:")
        print(f"   > nanobot gateway")
    except Exception as e:
        print(f"\n❌ Fehler bei der Anfrage: {e}")


async def start_webhook_test_server() -> None:
    """Startet einen lokalen Webhook-Server für Tests."""
    print(f"🚀 Starte lokalen Webhook-Test-Server")

    app = web.Application()

    async def handle_webhook(request):
        """Behandle den Webhook."""
        from aiohttp import web

        print(f"\n📨 Webhook empfangen!")

        try:
            body_bytes = await request.read()
            body_str = body_bytes.decode("utf-8")

            random_header = request.headers.get("X-Nextcloud-Talk-Random", "")
            sig_header = request.headers.get("X-Nextcloud-Talk-Signature", "")

            print(f"   RANDOM_HEADER: {random_header}")
            print(f"   SIGNATURE_HEADER: {sig_header}")
            print(f"   BODY: {body_str[:200]}...")

            # Test-Bot-Secret
            bot_secret = "test-shared-secret-mindestens-40-zeichen"

            expected = hmac.new(
                bot_secret.encode(),
                (random_header + body_str).encode(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(sig_header.lower(), expected.lower()):
                print(f"   ❌ Ungültige Signatur!")
                return web.Response(status=401, text="Unauthorized")

            print(f"   ✅ Signatur valid!")

            data = json.loads(body_str)
            print(f"   Event-Type: {data.get('type')}")

            response = {"status": 200, "text": "OK", "received_payload": data}

            print(f"   📦 Antwort: {json.dumps(response)[:200]}...")
            return web.json_response(response)

        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            return web.Response(status=500, text=str(e))

    app.router.add_post("/webhook/nextcloud_talk", handle_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 18791)
    await site.start()

    print(f"✅ Test-Server gestartet auf http://localhost:18791/webhook/nextcloud_talk")
    print("⚠️  Drücke STRG+C zum Beenden")

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("\n🛑 Server wird beendet...")
        await runner.cleanup()


async def main() -> None:
    """Hauptfunktion."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Webhook-Test-Skript für Nextcloud Talk Channel"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=18791,
        help="Port für den Webhook-Server (Standard: 18791)",
    )
    parser.add_argument(
        "--test-external",
        action="store_true",
        help="Webhook auf Port 18790 testen (Gateway-Server)",
    )

    args = parser.parse_args()

    if args.test_external:
        # Test externen Gateway-Server
        await test_webhook(port=18790)
    else:
        # Lokalen Test-Server starten
        await start_webhook_test_server()


if __name__ == "__main__":
    asyncio.run(main())
