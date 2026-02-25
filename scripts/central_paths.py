#!/usr/bin/env python3
# Zentrale Konfiguration für alle Installationen und Updates
# Ändere nur diese Datei, und alle Scripts werden automatisch aktualisiert

import os
from pathlib import Path


# Zentrale Pfade-Konfiguration
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

    # Git-Verzeichnisse
    NANOBOT_GIT_DIR = os.path.join(NANOBOT_WORKSPACE_DIR, ".git")

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


def print_paths():
    """Druckt alle definierten Pfade zur Überprüfung"""
    print("=" * 60)
    print("ZENTRALE PFADE KONFIGURATION")
    print("=" * 60)

    print("\n📋 Installation-Verzeichnisse:")
    print(f"  Base:          {Paths.NANOBOT_BASE_DIR}")
    print(f"  Config:        {Paths.NANOBOT_CONFIG_DIR}")
    print(f"  Workspace:     {Paths.NANOBOT_WORKSPACE_DIR}")
    print(f"  Logs:          {Paths.NANOBOT_LOGS_DIR}")
    print(f"  Scripts:       {Paths.NANOBOT_SCRIPTS_DIR}")
    print(f"  Tools:         {Paths.NANOBOT_TOOLS_DIR}")
    print(f"  Backup:        {Paths.NANOBOT_BACKUP_DIR}")

    print("\n📋 Docker Config Files:")
    print(f"  Config:        {Paths.NANOBOT_CONFIG_FILE}")
    print(f"  Docker:        {Paths.NANOBOT_CONFIG_DOCKER_FILE}")
    print(f"  Backup:        {Paths.NANOBOT_CONFIG_BACKUP_FILE}")
    print(f"  .env:          {Paths.NANOBOT_ENV_FILE}")
    print(f"  docker-compose: {Paths.NANOBOT_DOCKER_COMPOSE_FILE}")
    print(f"  Dockerfile:    {Paths.NANOBOT_DOCKERFILE_FILE}")

    print("\n📋 Container Verzeichnisse:")
    print(f"  Config Dir:    {Paths.NANOBOT_CONTAINER_CONFIG_DIR}")
    print(f"  Workspace Dir: {Paths.NANOBOT_CONTAINER_WORKSPACE_DIR}")
    print(f"  Logs Dir:      {Paths.NANOBOT_CONTAINER_LOGS_DIR}")
    print(f"  Scripts Dir:   {Paths.NANOBOT_CONTAINER_SCRIPTS_DIR}")
    print(f"  Tools Dir:     {Paths.NANOBOT_CONTAINER_TOOLS_DIR}")

    print("\n📋 Container Config Files:")
    print(f"  Config:        {Paths.NANOBOT_CONTAINER_CONFIG_FILE}")
    print(f"  Docker:        {Paths.NANOBOT_CONTAINER_CONFIG_DOCKER_FILE}")
    print(f"  Backup:        {Paths.NANOBOT_CONTAINER_CONFIG_BACKUP_FILE}")

    print("\n📋 Projekt Information:")
    print(f"  Scripts Dir:   {Paths.SCRIPTS_DIR}")
    print(f"  Project Dir:   {Paths.PROJECT_DIR}")

    print("\n📋 Container Information:")
    print(f"  Container Name:{Paths.NANOBOT_CONTAINER_NAME}")
    print(f"  Port:          {Paths.NANOBOT_PORT}")

    print("\n📋 Update Schedule:")
    print(f"  Hour:          {Paths.AUTO_UPDATE_HOUR}")
    print(f"  Minute:        {Paths.AUTO_UPDATE_MINUTE}")

    print("\n" + "=" * 60)


def generate_compatible_pylint_ignore():
    """Generiert kompatible pylint-ignore Zeilen für alle Scripts"""
    # Diese Zeilen können in jedem Script als erste Zeilen kopiert werden
    import json
    from pathlib import Path

    return f"""
# pylint: disable=maybe-no-member
# pylint: disable=global-variable-undefined
# pylint: disable=unused-variable
# pylint: disable=global-statement
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-lines
# pylint: disable=broad-except
# pylint: disable=logging-fstring-interpolation
# pylint: disable=line-too-long
# pylint: disable=import-error
"""


if __name__ == "__main__":
    print_paths()
