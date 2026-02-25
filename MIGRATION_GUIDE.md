# Updatescript-Mechanismus & Zentrale Konfiguration

## 📋 Übersicht

Dieses Dokument erklärt das Updatesystem für Nanobot und wie es sicherstellt, dass **alle Pfade immer synchron sind**.

## 🎯 Kernprinzip

### **Altes Problem:**
- Updatescripts hatten hartcodierte Pfade
- Jede Änderung an PFXML erforderte manuelles Editieren aller Scripts
- Gefahr von Inkonsistenzen

### **Neue Lösung:**
- **Zentrale Konfiguration** (`scripts/central_paths.py`)
- Alle Pfade sind **einziges Source-of-Truth**
- Updatescript importiert automatisch diese Pfade

## 📁 Zentrale Konfiguration

### Datei: `scripts/central_paths.py`

Diese Datei enthält **ALLE** Pfade im Projekt:

```python
class Paths:
    """Alle relevanten Pfade in einer zentralen Konfiguration"""

    # Installation-Verzeichnisse
    NANOBOT_BASE_DIR = "/opt/nanobot"
    NANOBOT_CONFIG_DIR = os.path.join(NANOBOT_BASE_DIR, "config")
    NANOBOT_WORKSPACE_DIR = os.path.join(NANOBOT_BASE_DIR, "workspace")
    NANOBOT_LOGS_DIR = os.path.join(NANOBOT_BASE_DIR, "logs")
    NANOBOT_SCRIPTS_DIR = os.path.join(NANOBOT_BASE_DIR, "scripts")
    NANOBOT_TOOLS_DIR = os.path.join(NANOBOT_BASE_DIR, "tools")
    NANOBOT_BACKUP_DIR = os.path.join(NANOBOT_BASE_DIR, "backup")

    # Docker Config Files
    NANOBOT_CONFIG_FILE = os.path.join(NANOBOT_CONFIG_DIR, "config.json")
    NANOBOT_CONFIG_DOCKER_FILE = os.path.join(NANOBOT_CONFIG_DIR, "config.docker.json")
    NANOBOT_CONFIG_BACKUP_FILE = os.path.join(NANOBOT_CONFIG_DIR, "config.backup.json")
    NANOBOT_ENV_FILE = os.path.join(NANOBOT_BASE_DIR, ".env")
    NANOBOT_DOCKER_COMPOSE_FILE = os.path.join(NANOBOT_BASE_DIR, "docker-compose.yml")
    NANOBOT_DOCKERFILE_FILE = os.path.join(NANOBOT_BASE_DIR, "Dockerfile")

    # Container Verzeichnisse
    NANOBOT_CONTAINER_CONFIG_DIR = "/home/nanobot/config"
    NANOBOT_CONTAINER_WORKSPACE_DIR = "/home/nanobot/workspace"
    NANOBOT_CONTAINER_LOGS_DIR = "/home/nanobot/logs"
    NANOBOT_CONTAINER_SCRIPTS_DIR = "/home/nanobot/scripts"
    NANOBOT_CONTAINER_TOOLS_DIR = "/opt/nanobot/tools"
    NANOBOT_CONTAINER_CONFIG_FILE = "/home/nanobot/config/config.json"
    NANOBOT_CONTAINER_CONFIG_DOCKER_FILE = "/home/nanobot/config/config.docker.json"
    NANOBOT_CONTAINER_CONFIG_BACKUP_FILE = "/home/nanobot/config/config.backup.json"

    # Projekt Verzeichnisse
    SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)

    # Container Names
    NANOBOT_CONTAINER_NAME = "nanobot"

    # Ports
    NANOBOT_PORT = 18790

    # Environment
    AUTO_UPDATE_HOUR = "00"
    AUTO_UPDATE_MINUTE = "15"
```

## 🔄 Updatescript-Arbeitsweise

### Updatescript: `scripts/update_migrate.py`

**Vorteile:**
- ✅ Importiert zentrale Konfiguration
- ✅ Keine hartcodierten Pfade mehr
- ✅ Alle Änderungen müssen nur in einer Datei gemacht werden
- ✅ Automatische Konsistenzprüfung

### Verwendung:

```bash
# Configuration anzeigen
python3 scripts/central_paths.py

# Dry-Run (zeige was passieren würde)
python3 scripts/update_migrate.py --dry-run

# Updatescript ausführen
python3 scripts/update_migrate.py --force

# Mit Skip-Backup
python3 scripts/update_migrate.py --skip-backup

# Um Version anzuzeigen
python3 scripts/update_migrate.py --print-config
```

## 📝 Beispiel: Ändern eines Pfades

### Szenario: Workspace-Pfad ändern

**FALSCH (altes System):**
```bash
# Ändere von /opt/nanobot/workspace nach /opt/data/nanobot
# MUSS manuell in ALLEN Scripts geändert werden:
nano /opt/nanobot/scripts/update_migrate.sh    # Zeile X
nano /opt/nanobot/scripts/config_sync.py       # Zeile Y
nano /opt/nanobot/scripts/migrate_to_new_version.sh  # Zeile Z
nano docker-compose.yml  # Zeile 39
# usw...
```

**RICHTIG (neues System):**
```bash
# Ändere Workspace nur in der zentralen Konfiguration:
nano scripts/central_paths.py

# Zeile anpassen:
NANOBOT_WORKSPACE_DIR = os.path.join(NANOBOT_BASE_DIR, "workspace_data")

# FERTIG! Alle Scripts automatisch korrekt
```

## 🔧 Warum dieses System funktioniert

### 1. Single Source of Truth
Jeder der Scripts kann zu folgendem Zeitpunkt navigieren:
```python
from central_paths import Paths

# Nutzt automatisch die zentrale Konfiguration
print(Paths.NANOBOT_CONFIG_FILE)
print(Paths.NANOBOT_CONTAINER_WORKSPACE_DIR)
```

### 2. Konsistente Pfade
Alle Pfade (externe und interne) werden aus derselben Quelle gelesen, garantiert identisch.

### 3. Automatische Updates
Wenn das Updatescript ausgeführt wird:
1. Lädt zentrale Konfiguration
2. Prüft alle Installationen
3. Kopiert aktuelle Scripts mit korrekten Pfaden
4. Führt Migration durch

### 4. Container Synchronisation
Container erhält:
- Aktuelles Updatescript
- Aktuelles Config-Sync-Script
- Aktuelles Dockerfile
- Aktuelles docker-compose.yml

## 📂 Dateistruktur

```
nanobot-nextcloud-talk-channel/
├── scripts/
│   ├── central_paths.py          ⭐ ZENTRALE KONFIGURATION (ALLE PFADE)
│   ├── update_migrate.py         ⭐ Updatescript (nutzt zentrale Konfiguration)
│   ├── config_sync.py            (utilscript)
│   ├── migrate_to_new_version.sh  (legacy)
│   └── install_all_tools.sh      (legacy)
├── docker-compose.yml            (nutzt: Paths.NANOBOT_DOCKER_COMPOSE_FILE)
├── Dockerfile                    (nutzt: Paths.NANOBOT_DOCKERFILE_FILE)
├── INSTALLATION.md               (beschreibt Installation)
└── MIGRATION_GUIDE.md            (Dieses Dokument)
```

## 🔄 Flow: Änderung an einem Pfad

Wenn du einen Pfad änderst:

1. **Ändere** `scripts/central_paths.py`
   ```python
   NANOBOT_WORKSPACE_DIR = "/neuer/workspace/pfad"
   ```

2. **Updatescript nutzt** automatisch den neuen Pfad
   ```python
   from central_paths import Paths
   # Jetzt zeigt alles auf den neuen Pfad
   ```

3. **Container Synchronisation** beim nächsten Update
   ```bash
   python3 scripts/update_migrate.py --force
   # Kopiert alle Scripts mit dem neuen Pfad
   ```

4. **Alte Installationen** werden mit korrektem Pfad aktualisiert

## ✅ Vorteile

### Für Entwickler:
- ✅ Keine vielfachen Änderungen in vielen Dateien
- ✅ Konsistente Pfade über das gesamte Projekt
- ✅ Einfaches Nachvollziehen von Pfaden
- ✅ Sicherheit gegen Typos

### Für Installationen:
- ✅ Scripts sind sofort mit korrekten Pfaden
- ✅ Automatische Migration mit korrekten Pfaden
- ✅ Container-Updates funktionieren ohne manuelle Anpassungen
- ✅ Aktualisierte Scripts im Container

## 🚀 Beispiel: Ändern eines Container-Pfades

### Neues Beispiel: Container-Speicherpfad ändern

**1. In `central_paths.py` ändern:**
```python
# Container Scripts-Pfad ändern
NANOBOT_CONTAINER_SCRIPTS_DIR = "/opt/container/scripts"  # neu
```

**2. Alle Scripts nutzen automatisch den neuen Pfad:**
```python
from central_paths import Paths

# Nun alle Pfade korrekt
destination = Paths.NANOBOT_CONTAINER_SCRIPTS_DIR
source = Paths.NANOBOT_SCRIPTS_DIR

# Verschiebt/dupliziert nur das richtige Verzeichnis
shutil.copytree(source, destination)
```

**3. Container wird automatisch mit korrektem Pfad aktualisiert**
- Updatescript kopiert Scripts mit neuen Pfaden
- Container führt aus dem neuen Pfad aus

## 📝 Migration Best Practice

### Wenn du eine Änderung machst:

1. **Erstelle Backup:**
   ```bash
   cp scripts/central_paths.py scripts/central_paths.py.backup
   ```

2. **Ändere den Pfad:**
   ```bash
   nano scripts/central_paths.py
   ```

3. **Validiere die Konfiguration:**
   ```bash
   python3 scripts/central_paths.py
   ```

4. **Teste das Updatescript:**
   ```bash
   python3 scripts/update_migrate.py --dry-run
   ```

5. **Commite die Änderung:**
   ```bash
   git add scripts/central_paths.py scripts/update_migrate.py
   git commit -m "Update: Changed workspace path to /opt/data/nanobot/workspace"
   ```

6. **Updates ausführen:**
   ```bash
   python3 scripts/update_migrate.py --force
   ```

## 🔍 Debugging

### Pfad-Probleme verifizieren:

```bash
# Zeige alle Pfade an
python3 scripts/central_paths.py

# Prüfe, ob Datei existiert
python3 -c "from central_paths import Paths; print('Exists:', Path(Paths.NANOBOT_CONFIG_FILE).exists())"

# Zeige alle relevanten Pfade an
python3 -c "from central_paths import Paths; print(f'Config: {Paths.NANOBOT_CONFIG_FILE}'); print(f'Docker Config: {Paths.NANOBOT_CONFIG_DOCKER_FILE}'); print(f'Container Config: {Paths.NANOBOT_CONTAINER_CONFIG_FILE}')"
```

## 📚 Zusammenfassung

### Single Source of Truth:
- **Scripts:** `scripts/central_paths.py`
- **Pfade:** `class Paths`
- **Updatescript:** `scripts/update_migrate.py`

### Regeln:
1. **Niemand** hardcodiert Pfade
2. **Jeder** Pfad kommt von `central_paths.py`
3. **Änderungen** in `central_paths.py` werden automatisch sichtbar
4. **Updatescript** nutzt nur diese Konfiguration

### Erfolg:
- ✅ Konsistente Pfade überall
- ✅ Keine Inkonsistenzen
- ✅ Einfache Wartung
- ✅ Automatische Migration

---

**Letzte Aktualisierung:** 25.02.2026
**Version:** 2.0 (Centric Path System)