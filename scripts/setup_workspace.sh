#!/bin/bash
# Workspace Security & Initialization Script - Direct Implementation

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Nanobot Workspace Setup           ${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Standard Pfade
NANOBOT_BASE_DIR="/opt/nanobot"
NANOBOT_WORKSPACE_DIR="/opt/nanobot/workspace"
NANOBOT_LOGS_DIR="/opt/nanobot/logs"
NANOBOT_BACKUP_DIR="/opt/nanobot/backup"
NANOBOT_TOOLS_DIR="/opt/nanobot/tools"

# Funktionen
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️  ${NC}$1"
}

print_info() {
    echo -e "${BLUE}ℹ️  ${NC}$1"
}

echo -e "${GREEN}Workspace Verzeichnisse werden initialisiert...${NC}"

# Erstelle alle benötigten Verzeichnisse mit korrekten Rechten
directories=(
    "$NANOBOT_WORKSPACE_DIR"
    "$NANOBOT_LOGS_DIR"
    "$NANOBOT_BACKUP_DIR"
    "$NANOBOT_TOOLS_DIR"
)

for dir in "${directories[@]}"; do
    # Erstelle Verzeichnis falls nicht existent
    if [ ! -d "$dir" ]; then
        print_info "Erstelle: $dir"
        mkdir -p "$dir"
    fi

    # Setze korrekte Rechte (Linux / macOS)
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux: Setze User und Group
        if [ -f /.dockerenv ]; then
            # Inside Docker: Setze auf user 1000 (nobody)
            print_warning "Setze Container-Rechte auf 1000:1000 für: $dir"
            sudo chown -R 1000:1000 "$dir"
            sudo chmod -R 755 "$dir"
        else
            # Outside Docker: Setze auf aktuellen User
            print_info "Setze Host-Rechte auf $(whoami):$(whoami) für: $dir"
            sudo chown -R "$(whoami):$(whoami)" "$dir"
            sudo chmod -R 755 "$dir"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: Setze auf aktuellen User
        chown -R "$(whoami):staff" "$dir"
        chmod -R 755 "$dir"
    fi
done

print_status "Workspace Verzeichnisse initialisiert"
echo ""

# Erstelle Beispiel-Struktur
echo -e "${GREEN}Erstelle Workspace Beispiel-Struktur...${NC}"

# Beispiel-Dateien
cat > "$NANOBOT_WORKSPACE_DIR/README.md" << 'EOF'
# Nanobot Workspace

Dies ist das Arbeitsverzeichnis für Nanobot Agenten und Skills.

## Struktur

- `/home/nanobot/workspace` - Hauptarbeitsverzeichnis
- `/home/nanobot/.nanobot` - Versteckte Nano-Daten
- `/home/nanobot/logs` - Logdateien
- `/home/nanobot/.cache` - Cachedaten

## Zugriff

Sie können direkt vom Host auf diese Dateien zugreifen:

```bash
# Aus Host-Ordner:
ls -la /opt/nanobot/workspace/

# Aus Container:
docker exec -it nanobot ls /home/nanobot/workspace/
```

## Persistenz

Alle Änderungen sind sofort im Host verfügbar und bleiben auch nach Container-Neustart bestehen.
EOF

print_status "Workspace Beispiel-Struktur erstellt"
echo ""

# Prüfe Container-Zugriff
echo -e "${GREEN}Prüfe Docker Container Zugriffsrechte...${NC}"

if [ -f /.dockerenv ]; then
    print_warning "⚠️  Aus Sicherheitsgründen müssen Sie die Verzeichnisse manuell mit sudo setzen"
    print_info "Führe aus:"
    echo ""
    echo "  sudo chown -R 1000:1000 /opt/nanobot/workspace"
    echo "  sudo chown -R 1000:1000 /opt/nanobot/logs"
    echo "  sudo chown -R 1000:1000 /opt/nanobot/.cache"
    echo "  sudo chown -R 1000:1000 /opt/nanobot/.nanobot"
    echo "  sudo chown -R 1000:1000 /opt/nanobot/.ssh"
    echo ""
else
    print_status "Container nicht erkannt (Host-Betrieb)"
    print_info "HINWEIS: Damit Docker Container die Dateien lesen/schreiben kann:"
    echo ""
    echo "  Führen Sie Folgendes aus: sudo chown -R $(whoami):$(whoami) /opt/nanobot/*"
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Workspace Setup Abgeschlossen!     ${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "${YELLOW}Nächste Schritte:${NC}"
echo -e "1. Setze Container-Zugriffsrechte (falls Docker):"
echo -e "   sudo chown -R 1000:1000 /opt/nanobot/workspace"
echo -e "   sudo chown -R 1000:1000 /opt/nanobot/logs"
echo -e "   sudo chown -R 1000:1000 /opt/nanobot/.cache"
echo -e "   sudo chown -R 1000:1000 /opt/nanobot/.nanobot"
echo -e "   sudo chown -R 1000:1000 /opt/nanobot/.ssh"
echo ""
echo -e "2. Starte den Container:"
echo -e "   docker compose up -d"
echo ""
echo -e "3. Prüfe, ob Dateien erstellt werden:"
echo -e "   docker exec -it nanobot ls -la /home/nanobot/workspace/"
echo ""
echo -e "4. Dateien sollten nun auch auf dem Host sichtbar sein:"
echo -e "   ls -la /opt/nanobot/workspace/"
echo ""
exit 0