#!/usr/bin/env python3
"""Centric Update Script with Config-Driven Paths"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Import zentrale Pfade-Konfiguration
from central_paths import Paths, print_paths, generate_compatible_pylint_ignore


class MigrationLogger:
    """Migration Logger with Colors"""

    def __init__(self):
        self.colors = {
            "RED": "\033[0;31m",
            "GREEN": "\033[0;32m",
            "YELLOW": "\033[1;33m",
            "BLUE": "\033[0;34m",
            "CYAN": "\033[0;36m",
            "NC": "\033[0m",
        }

    def success(self, message):
        print(f"{self.colors['GREEN']}✅ {self.colors['NC']}{message}")

    def error(self, message):
        print(f"{self.colors['RED']}❌ {self.colors['NC']}{message}")

    def warning(self, message):
        print(f"{self.colors['YELLOW']}⚠️  {self.colors['NC']}{message}")

    def info(self, message):
        print(f"{self.colors['BLUE']}ℹ️  {self.colors['NC']}{message}")

    def highlight(self, message):
        print(f"{self.colors['CYAN']}👉 {self.colors['NC']}{message}")


class PathManager:
    """Manages paths based on centralized configuration"""

    def __init__(self):
        self.logger = MigrationLogger()

    def ensure_directories_exist(self):
        """Ensure all configured directories exist"""
        self.logger.info("Creating required directories...")

        directories = [
            Paths.NANOBOT_BASE_DIR,
            Paths.NANOBOT_CONFIG_DIR,
            Paths.NANOBOT_WORKSPACE_DIR,
            Paths.NANOBOT_LOGS_DIR,
            Paths.NANOBOT_SCRIPTS_DIR,
            Paths.NANOBOT_TOOLS_DIR,
            Paths.NANOBOT_BACKUP_DIR,
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

            # Set permissions
            try:
                if os.geteuid() == 0:
                    os.chown(directory, 1000, 1000)
                else:
                    os.chown(directory, os.getuid(), os.getgid())
            except:
                pass

        self.logger.success("Directories created/verified")

    def check_existing_config(self):
        """Check if existing config exists"""
        if os.path.exists(Paths.NANOBOT_CONFIG_FILE):
            return True
        return False

    def backup_existing_config(self):
        """Backup existing configuration"""
        if not self.check_existing_config():
            return

        self.logger.info("Creating backup of existing configuration...")

        backup_dir = Paths.NANOBOT_BACKUP_DIR
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"config_{timestamp}.json")

        try:
            import shutil

            shutil.copy2(Paths.NANOBOT_CONFIG_FILE, backup_file)
            self.logger.success(f"Backup created: {backup_file}")
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")


class MigrationManager:
    """Manages migration of existing installations"""

    def __init__(self):
        self.path_manager = PathManager()
        self.logger = MigrationLogger()

    def check_docker_installed(self):
        """Check if Docker installation exists"""
        return (
            os.path.exists(Paths.NANOBOT_DOCKER_COMPOSE_FILE)
            or self.docker_ps_expects_nanobot()
        )

    def docker_ps_expects_nanobot(self):
        """Check if nanobot container is running"""
        import subprocess

        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
            )
            return Paths.NANOBOT_CONTAINER_NAME in result.stdout
        except:
            return False

    def check_direct_installed(self):
        """Check if direct Python installation exists"""
        return os.path.exists(Paths.NANOBOT_CONFIG_FILE)

    def migrate_docker_installation(self):
        """Migrate Docker installation"""
        self.logger.highlight("Migrating Docker installation...")

        # 1. Create directory structure
        self.path_manager.ensure_directories_exist()

        # 2. Copy docker-compose.yml if it doesn't exist or needs update
        if not os.path.exists(Paths.NANOBOT_DOCKER_COMPOSE_FILE):
            self.logger.info("Copying docker-compose.yml from project...")
            self._copy_project_file("docker-compose.yml")

        # 3. Copy Dockerfile if it doesn't exist
        if not os.path.exists(Paths.NANOBOT_DOCKERFILE_FILE):
            self.logger.info("Copying Dockerfile from project...")
            self._copy_project_file("Dockerfile")

        # 4. Create/update .env file
        if not os.path.exists(Paths.NANOBOT_ENV_FILE):
            self.logger.info("Creating .env file...")
            self._create_env_file()

        # 5. Copy scripts
        if not os.path.exists(Paths.NANOBOT_SCRIPTS_DIR):
            self.logger.info("Copying scripts directory...")
            self._copy_project_directory("scripts")

        # 6. Update config sync script
        self._update_config_sync_script()

        self.logger.success("Docker installation migrated successfully")

    def migrate_direct_installation(self):
        """Migrate direct Python installation"""
        self.logger.highlight("Migrating direct Python installation...")

        # 1. Backup existing installation
        backup_dir = Paths.NANOBOT_BACKUP_DIR
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"python_install_{timestamp}.tar.gz")

        self.logger.info("Creating backup of existing installation...")
        try:
            import subprocess

            subprocess.run(
                ["tar", "-czf", backup_file, "-C", Paths.PROJECT_DIR, "."],
                capture_output=True,
                check=True,
            )
            self.logger.success(f"Backup created: {backup_file}")
        except Exception as e:
            self.logger.warning(f"Backup creation skipped: {e}")

        # 2. Update project directory
        if not os.path.exists(Paths.PROJECT_DIR):
            self.logger.info("Updating project directory...")
            subprocess.run(["git", "pull"], capture_output=True, check=True)

        # 3. Install dependencies
        self.logger.info("Installing Python dependencies...")
        requirements_file = os.path.join(Paths.PROJECT_DIR, "requirements.txt")
        if os.path.exists(requirements_file):
            subprocess.run(
                ["pip3", "install", "-r", requirements_file],
                capture_output=True,
                check=True,
            )

        self.logger.success("Direct installation migrated successfully")

    def _copy_project_file(self, filename):
        """Copy project file to installation directory"""
        source = os.path.join(Paths.PROJECT_DIR, filename)
        destination = (
            Paths.NANOBOT_DOCKER_COMPOSE_FILE
            if filename == "docker-compose.yml"
            else Paths.NANOBOT_DOCKERFILE_FILE
        )

        if os.path.exists(source):
            import shutil

            shutil.copy2(source, destination)
            self.logger.success(f"Copied {filename} to {destination}")
        else:
            self.logger.error(f"Source file not found: {source}")

    def _copy_project_directory(self, dirname):
        """Copy project directory to installation directory"""
        source = os.path.join(Paths.PROJECT_DIR, dirname)
        destination = Paths.NANOBOT_SCRIPTS_DIR

        if os.path.exists(source):
            import shutil

            shutil.copytree(source, destination, dirs_exist_ok=True)
            self.logger.success(f"Copied {dirname} directory")

    def _create_env_file(self):
        """Create .env file with default values"""
        env_content = f"""# Nanobot Configuration
NEXTCLOUD_BASE_URL=https://cloud.example.com
NEXTCLOUD_BOT_SECRET=
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OLLAMA_API_BASE=http://host.docker.internal:11434
VLLM_API_BASE=http://host.docker.internal:8000/v1
"""

        with open(Paths.NANOBOT_ENV_FILE, "w") as f:
            f.write(env_content)

        self.logger.success(f"Created .env file: {Paths.NANOBOT_ENV_FILE}")

    def _update_config_sync_script(self):
        """Update config sync script in container"""
        if not os.path.exists(Paths.NANOBOT_SCRIPTS_DIR):
            return

        source_script = os.path.join(Paths.PROJECT_DIR, "scripts/config_sync.py")
        dest_script = os.path.join(Paths.NANOBOT_SCRIPTS_DIR, "config_sync.py")

        if os.path.exists(source_script):
            import shutil

            shutil.copy2(source_script, dest_script)
            self.logger.success("Updated config_sync.py")

            # Make executable
            os.chmod(dest_script, 0o755)

    def verify_container_config(self):
        """Verify container configuration"""
        if not self.check_docker_installed():
            self.logger.info("No Docker installation found to verify")
            return

        self.logger.highlight("Verifying container configuration...")

        # Check if scripts directory exists in container
        docker_script = f"{Paths.NANOBOT_CONTAINER_SCRIPTS_DIR}/config_sync.py"
        if os.path.exists(Paths.NANOBOT_SCRIPTS_DIR):
            try:
                subprocess.run(
                    [
                        "docker",
                        "cp",
                        Paths.NANOBOT_SCRIPTS_DIR + "/config_sync.py",
                        f"{Paths.NANOBOT_CONTAINER_NAME}:{docker_script}",
                    ],
                    capture_output=True,
                )
                self.logger.success("Config sync script copied to container")
            except Exception as e:
                self.logger.warning(f"Failed to copy config sync script: {e}")


def main():
    """Main migration function"""
    logger = MigrationLogger()

    print("\n" + "=" * 60)
    print("   NANOBOT CENTRIC UPDATE SCRIPT")
    print("=" * 60)
    print("\nZentrale Pfad-Konfiguration wird geladen...\n")

    # Parse command line arguments
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv
    skip_backup = "--skip-backup" in sys.argv

    if dry_run:
        logger.warning("DRY RUN MODE - Keine tatsächlichen Änderungen")

    if "--print-config" in sys.argv:
        print_paths()
        return

    # Verify central configuration
    logger.info("Zentrale Pfad-Konfiguration wird validiert...")
    if not Paths.SCRIPTS_DIR:
        logger.error("Fehler in zentraler Konfiguration!")
        sys.exit(1)

    # Detect installation
    migration_manager = MigrationManager()

    if migration_manager.check_docker_installed():
        installation_type = "docker"
    elif migration_manager.check_direct_installed():
        installation_type = "direct"
    else:
        logger.error("Keine Installation gefunden!")
        sys.exit(1)

    logger.success(f"{installation_type.capitalize()} Installation erkannt")

    # Backup existing config if needed
    if not skip_backup:
        path_manager = PathManager()
        path_manager.backup_existing_config()

    # Migrate based on installation type
    if dry_run:
        logger.info("[DRY RUN] Would migrate installation...")
    else:
        if installation_type == "docker":
            migration_manager.migrate_docker_installation()
        elif installation_type == "direct":
            migration_manager.migrate_direct_installation()

    # Verify container configuration
    migration_manager.verify_container_config()

    # Print next steps
    print("\n" + "=" * 60)
    print("         MIGRATION/KORREKTUR ABGESCHLOSSEN")
    print("=" * 60)
    print()

    if installation_type == "docker":
        print(">>> Nächste Schritte:")
        print("1. Docker Container starten:")
        print(f"   docker compose up -d")
        print()
        print("2. Container prüfen:")
        print(f"   docker compose logs -f {Paths.NANOBOT_CONTAINER_NAME}")
        print()
        print("3. Config im Container importieren:")
        print(
            f"   docker exec -it {Paths.NANOBOT_CONTAINER_NAME} python3 {Paths.NANOBOT_CONTAINER_SCRIPTS_DIR}/config_sync.py import-docker"
        )
        print()
        print("4. Container neustarten:")
        print(f"   docker compose restart {Paths.NANOBOT_CONTAINER_NAME}")
    else:
        print(">>> Nächste Schritte:")
        print("1. Installation prüfen:")
        print(f"   cd {Paths.PROJECT_DIR}")
        print("   pip3 install -r requirements.txt")
        print("   python3 nanobot/agent/runner.py")

    print()
    print("📌 Für Details siehe: INSTALLATION.md")
    print()
    print("=" * 60)

    sys.exit(0)


if __name__ == "__main__":
    main()
