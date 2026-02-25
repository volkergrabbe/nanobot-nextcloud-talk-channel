# Nanobot Installation Guide

## 📋 Inhaltsverzeichnis

1. [Systemanforderungen](#systemanforderungen)
2. [Direkt-installation (ohne Docker)](#direkt-installation-ohne-docker)
3. [Docker-Installation](#docker-installation)
4. [Config-Synchronisation](#config-synchronisation)
5. [Update-Mechanismus](#update-mechanismus)
6. [Nützliche Befehle](#nützliche-befehle)

---

## Systemanforderungen

### Mindestvoraussetzungen
- **Betriebssystem**: Linux, macOS oder Windows (mit Docker)
- **Python**: 3.11+ (bei direkter Installation)
- **Docker**: 20.10+ (bei Docker-Installation)
- **RAM**: Mindestens 2GB, empfohlen 4GB
- **Speicher**: Mindestens 5GB freier Speicher

### Empfohlene Tools im Container
- **Version Control**: Git, Git LFS
- **Editoren**: Vim, Nano, Tmux
- **Monitoring**: htop
- **Datei-Tools**: rsync, tar, gzip, jq
- **Netzwerk**: curl, wget, ping
- **SSH**: OpenSSH Client
- **Sprache**: Python 3.11

---

## Direkt-Installation (ohne Docker)

### 1. Ordnerstruktur erstellen

```bash
sudo mkdir -p /opt/nanobot/config
sudo mkdir -p /opt/nanobot/workspace
sudo mkdir -p /opt/nanobot/logs
sudo chown -R $USER:$USER /opt/nanobot
```

### 2. Config initialisieren

```bash
cd /opt/nanobot
python3 /home/volker/Private-Nextcloud/Projekte/nanobot-nextcloud-talk-channel/scripts/config_sync.py init
```

### 3. Git-Repository klonen

```bash
git clone <repository-url> /home/volker/Private-Nextcloud/Projekte/nanobot-nextcloud-talk-channel
cd /home/volker/Private-Nextcloud/Projekte/nanobot-nextcloud-talk-channel
```

### 4. Python-Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 5. Config anpassen

Bearbeiten Sie `/opt/nanobot/config/config.json`:

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "workspace": "/home/nanobot/workspace"
    }
  },
  "channels": {
    "nextcloud_talk": {
      "enabled": false,
      "base_url": "https://cloud.example.com",
      "webhook_path": "/webhook/nextcloud_talk",
      "botSecret": ""
    }
  },
  "providers": {
    "anthropic": {
      "api_key": "your-anthropic-api-key"
    },
    "ollama": {
      "api_base": "http://localhost:11434",
      "api_key": ""
    },
    "vllm": {
      "api_base": "http://localhost:8000/v1",
      "api_key": ""
    }
  },
  "gateway": {
    "host": "0.0.0.0",
    "port": 18790
  }
}
```

### 6. Nanobot starten

```bash
cd /home/volker/Private-Nextcloud/Projekte/nanobot-nextcloud-talk-channel
python3 nanobot/agent/runner.py
```

---

## Docker-Installation

### 1. Config-Ordner erstellen

```bash
sudo mkdir -p /opt/nanobot/config
sudo mkdir -p /opt/nanobot/workspace
sudo mkdir -p /opt/nanobot/logs
sudo mkdir -p /opt/nanobot/.ssh
sudo chown -R $USER:$USER /opt/nanobot
```

### 2. Git-Repository klonen

```bash
git clone <repository-url> /home/volker/Private-Nextcloud/Projekte/nanobot-nextcloud-talk-channel
cd /home/volker/Private-Nextcloud/Projekte/nanobot-nextcloud-talk-channel
```

### 3. SSH Keys für Git einrichten (optional)

```bash
# Falls private Repositories verwendet werden:
ssh-keygen -t ed25519 -C "nanobot@your-domain"
# Kopiere den Inhalt von ~/.ssh/id_ed25519.pub auf die GitHub/GitLab-Seite
```

### 4. Docker Compose einrichten

Erstellen Sie eine `.env` Datei im Projektverzeichnis:

```bash
cat > .env << EOF
# Nanobot Configuration
NEXTCLOUD_BASE_URL=https://cloud.example.com
NEXTCLOUD_BOT_SECRET=your-nextcloud-bot-secret

# LLM Provider Configuration
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key

# Ollama Configuration (für lokale LLMs)
OLLAMA_API_BASE=http://host.docker.internal:11434

# VLLM Configuration (für vLLM Server)
VLLM_API_BASE=http://host.docker.internal:8000/v1
EOF

chmod 600 .env
```

### 5. Config initialisieren

```bash
python3 scripts/config_sync.py init
python3 scripts/config_sync.py import-docker
```

### 6. Docker Container starten

```bash
docker compose up -d
```

### 7. Container-Logs prüfen

```bash
docker compose logs -f nanobot
```

### 8. Config-Update in Container

```bash
docker exec -it nanobot python3 scripts/config_sync.py import-docker
docker compose restart nanobot
```

---

## Config-Synchronisation

Das System unterstützt eine **bidirektionale Config-Synchronisation**:

### Wichtige Dateien

```
/opt/nanobot/config/
├── config.json              # Externe Config (Hauptquelle) - READ/WRITE
├── config.docker.json       # Docker Config (Container) - READ-ONLY
└── config.backup.json       # Original Config (sicher) - READ-ONLY
```

### Bidirektionale Sync-Strategie

1. **Erster Start**: `config.json` wird erstellt als Kopie von `config.docker.json`
2. **Update Container Config**: Änderungen an `config.json` → `config.docker.json`
3. **Update Externe Config**: Änderungen in Container → `config.json` (import-docker)
4. **Backup**: Alte Externe Config wird als `config.backup.json` gesichert

### Sync-Kommandos

#### Externe Config → Docker Config

```bash
# Nur ausführen, wenn Änderungen an der externen Config
python3 scripts/config_sync.py sync-to-docker
```

#### Docker Config → Externe Config (Importer)

```bash
# Nützlich, wenn Updates im Container gemacht wurden
python3 scripts/config_sync.py import-docker
```

#### Backups erstellen

```bash
# Backup der aktuellen externen Config
python3 scripts/config_sync.py backup
```

#### Config validieren

```bash
# Prüft die Struktur der externen Config
python3 scripts/config_sync.py validate
```

#### Diff anzeigen

```bash
# Zeigt Unterschiede zwischen extern und docker Config
python3 scripts/config_sync.py diff
```

#### Aufräumen

```bash
# Löscht alte Backups (> 7 Tage)
python3 scripts/config_sync.py cleanup --days 7
```

### Cron-Job für automatische Updates

Die automatischen Updates erfolgen nachts um **00:15 Uhr**:

```bash
# Prüfen ob Update-Job läuft
crontab -l

# Löschen und neu erstellen für midnight updates
(crontab -l 2>/dev/null; echo "0 15 0 * * cd /home/nanobot && bash update_nanobot.sh >> /home/nanobot/logs/update_cron.log 2>&1") | crontab -
```

---

## Update-Mechanismus

### Automatische Updates (Docker)

Der Container führt tägliche Update-Checks durch:

1. **Täglich**: Update-Check um 00:15 Uhr
2. **Update-Zeit**: Nachts in den ungenutzten Stunden
3. **Automatische Updates**: Wenn Updates verfügbar sind → Container wird neugestartet

### Manuelle Updates

```bash
# Im Container
docker exec -it nanobot bash
python3 /home/nanobot/update_nanobot.sh

# Ausserhalb des Containers
docker exec -it nanobot python3 /home/nanobot/update_nanobot.sh
```

### Update-Logs prüfen

```bash
# Log im Container
docker logs nanobot | grep update

# Cron-Log
docker exec -it nanobot cat /home/nanobot/logs/update_cron.log

# Update Log
docker exec -it nanobot cat /home/nanobot/logs/update.log
```

### Neuen Nanobot-Release installieren

```bash
# Im Projektverzeichnis
git pull origin main
docker compose build --no-cache
docker compose up -d
```

---

## Nützliche Befehle

### Docker Management

```bash
# Container starten
docker compose up -d

# Container stoppen
docker compose down

# Container neu starten
docker compose restart nanobot

# Logs ansehen
docker compose logs -f nanobot

# Logs nach Zeit suchen
docker compose logs nanobot --since 1h

# Ins Container einloggen
docker exec -it nanobot bash

# Ins Container python einloggen
docker exec -it nanobot python3
```

### Config Management

```bash
# Config im Container anzeigen
docker exec -it nanobot cat /home/nanobot/config/config.json

# Config-Struktur validieren
docker exec -it nanobot python3 /home/nanobot/scripts/config_sync.py validate

# Config importieren (Docker → Extern)
docker exec -it nanobot python3 /home/nanobot/scripts/config_sync.py import-docker
```

### Status prüfen

```bash
# Container Status
docker ps -a | grep nanobot

# Container Healthcheck
docker inspect nanobot | grep -A 5 Health

# Git Status
cd /home/volker/Private-Nextcloud/Projekte/nanobot-nextcloud-talk-channel
git status
git log --oneline -5
```

### Container Dockerfile rebuilden

```bash
# Mit Cache
docker compose build

# Ohne Cache (vollständiger Neuaufbau)
docker compose build --no-cache
docker compose up -d
```

### SSH in Container einloggen

```bash
docker exec -it nanobot bash
```

### Systemtools im Container nutzen

```bash
docker exec -it nanobot htop
docker exec -it nanobot git status
docker exec -it nanobot curl -I https://cloud.example.com
docker exec -it nanobot python3 -c "import sys; print(sys.version)"
```

---

## Config-Beispiel

### Vollständige Config (Nextcloud Talk + Ollama)

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "workspace": "/home/nanobot/workspace"
    }
  },
  "channels": {
    "nextcloud_talk": {
      "enabled": true,
      "base_url": "https://your-cloud.example.com",
      "webhook_path": "/webhook/nextcloud_talk",
      "botSecret": "your-64-character-hex-string"
    }
  },
  "providers": {
    "anthropic": {
      "api_key": "sk-ant-..."
    },
    "ollama": {
      "api_base": "http://host.docker.internal:11434",
      "api_key": ""
    },
    "openai": {
      "api_key": ""
    },
    "vllm": {
      "api_base": "http://host.docker.internal:8000/v1",
      "api_key": ""
    },
    "custom": {
      "api_base": "",
      "api_key": ""
    }
  },
  "gateway": {
    "host": "0.0.0.0",
    "port": 18790
  },
  "tools": {
    "web": {
      "search": {
        "api_key": "",
        "max_results": 5
      }
    },
    "exec": {
      "timeout": 60,
      "restrict_to_workspace": false
    },
    "mcp_servers": {}
  }
}
```

---

## Troubleshooting

### Container startet nicht

```bash
# Logs prüfen
docker compose logs nanobot

# Container sauber stoppen
docker compose down
docker compose up -d

# Fehlende Config prüfen
ls -la /opt/nanobot/config/
```

### Config-Update fehlt

```bash
# Im Container
docker exec -it nanobot python3 /home/nanobot/scripts/config_sync.py import-docker
docker compose restart nanobot
```

### Update funktioniert nicht

```bash
# Logs prüfen
docker logs nanobot | grep update

# Manuell ausführen
docker exec -it nanobot bash /home/nanobot/update_nanobot.sh
```

---

## Sicherheit

### Config-Dateien schützen

```bash
# Config nur von Owner schreiben lassen
sudo chmod 600 /opt/nanobot/config/config.json
sudo chmod 644 /opt/nanobot/config/*.json
sudo chmod 700 /opt/nanobot/config
```

### SSH Keys sicher speichern

```bash
sudo chmod 600 /opt/nanobot/.ssh/id_*
sudo chmod 644 /opt/nanobot/.ssh/id_*.pub
sudo chown -R $USER:$USER /opt/nanobot/.ssh
```

### Docker-Container maximale Sicherheit

- Read-only Config in Container
- Minimale Docker Capabilities
- User-Drop Privileges
- Network Sandbox

---

## Support

Fragen? - Siehe `.nanobot_changelog.md` für detaillierte Änderungshistorie.

---

*Installation Guide erstellt am 25.02.2026*