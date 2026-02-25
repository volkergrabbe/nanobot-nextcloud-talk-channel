#!/usr/bin/env python3
"""
Config Synchronisation Manager for Nanobot.

This module handles bidirectional config synchronization between:
- /opt/nanobot/config/config.json (external - main source)
- /opt/nanobot/config/config.docker.json (container - read-only)
- /opt/nanobot/config/config.backup.json (original config)
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class ConfigSyncManager:
    """Manages config synchronization between external and container storage."""

    def __init__(self, config_dir: Path = Path("/opt/nanobot/config")):
        self.config_dir = config_dir
        self.external_config = config_dir / "config.json"
        self.docker_config = config_dir / "config.docker.json"
        self.backup_config = config_dir / "config.backup.json"

    def ensure_config_exists(self) -> None:
        """Ensure initial config file exists."""
        if not self.external_config.exists():
            print("✅ Creating initial config at /opt/nanobot/config/config.json")
            initial_config = self._get_default_config()
            self._save_config(self.external_config, initial_config)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default nanobot configuration."""
        return {
            "agents": {
                "defaults": {
                    "model": "anthropic/claude-opus-4-5",
                    "workspace": "/workspace",
                }
            },
            "channels": {
                "nextcloud_talk": {
                    "enabled": False,
                    "base_url": "https://cloud.example.com",
                    "webhook_path": "/webhook/nextcloud_talk",
                    "botSecret": "",
                }
            },
            "providers": {
                "anthropic": {"api_key": ""},
                "ollama": {
                    "api_base": "http://host.docker.internal:11434",
                    "api_key": "",
                },
                "openai": {"api_key": ""},
                "vllm": {
                    "api_base": "http://host.docker.internal:8000/v1",
                    "api_key": "",
                },
                "custom": {"api_base": "", "api_key": ""},
            },
            "gateway": {"host": "0.0.0.0", "port": 18790},
            "tools": {
                "web": {"search": {"api_key": "", "max_results": 5}},
                "exec": {"timeout": 60, "restrict_to_workspace": False},
                "mcp_servers": {},
            },
        }

    def _save_config(self, path: Path, config: Dict[str, Any]) -> None:
        """Save config to file."""
        config_dir = path.parent
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def _load_config(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load config from file."""
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading config from {path}: {e}")
            return None

    def initialize_backup(self) -> None:
        """Create initial backup of external config."""
        if self.external_config.exists() and not self.backup_config.exists():
            print("🛡️  Creating initial config backup")
            shutil.copy2(self.external_config, self.backup_config)

    def backup_external(self) -> None:
        """Backup current external config."""
        if self.external_config.exists():
            backup_name = self.docker_config.with_suffix(
                f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            shutil.copy2(self.external_config, backup_name)
            print(f"📦 Backup created: {backup_name}")

    def sync_from_external_to_docker(self) -> None:
        """Sync external config to docker config."""
        if not self.external_config.exists():
            print("❌ External config does not exist")
            return

        config = self._load_config(self.external_config)
        if not config:
            return

        # Save to docker config
        self._save_config(self.docker_config, config)
        print("✅ Synced external config to docker config")

    def sync_from_docker_to_external(self) -> None:
        """Sync docker config to external config."""
        if not self.docker_config.exists():
            print("❌ Docker config does not exist yet")
            return

        config = self._load_config(self.docker_config)
        if not config:
            return

        # Save to external config
        self._save_config(self.external_config, config)
        print("✅ Synced docker config to external config")

    def import_docker_config(self) -> bool:
        """Import docker config to external and create new backup."""
        if not self.docker_config.exists():
            print("❌ Docker config does not exist")
            return False

        # Backup current external
        if self.external_config.exists():
            current_backup = self.backup_config.with_suffix(
                f".before_import.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            shutil.copy2(self.external_config, current_backup)

        # Import docker config
        config = self._load_config(self.docker_config)
        if not config:
            return False

        self._save_config(self.external_config, config)
        print(f"✅ Imported docker config to external config")
        print(f"   Backup of previous config: {current_backup}")
        return True

    def show_diff(self) -> None:
        """Show differences between external and docker config."""
        external = self._load_config(self.external_config)
        docker = self._load_config(self.docker_config)

        if not external or not docker:
            print("❌ Cannot compare - one or both configs missing")
            return

        import json

        external_str = json.dumps(external, indent=2, sort_keys=True)
        docker_str = json.dumps(docker, indent=2, sort_keys=True)

        if external_str != docker_str:
            print("📋 Config differences detected:")
            print("   External config differs from docker config")
            print("\nExternal config:")
            print(
                external_str[:500] + "..." if len(external_str) > 500 else external_str
            )
            print("\nDocker config:")
            print(docker_str[:500] + "..." if len(docker_str) > 500 else docker_str)
        else:
            print("✅ External config matches docker config")

    def validate_config(self) -> bool:
        """Validate external config structure."""
        if not self.external_config.exists():
            print("❌ External config does not exist")
            return False

        config = self._load_config(self.external_config)
        if not config:
            print("❌ Failed to load external config")
            return False

        # Check required fields
        required = ["agents", "channels", "providers", "gateway", "tools"]
        for field in required:
            if field not in config:
                print(f"❌ Missing required field: {field}")
                return False

        print("✅ External config structure is valid")
        return True

    def cleanup_old_backups(self, max_age_days: int = 7) -> None:
        """Remove backup files older than specified days."""
        now = datetime.now()
        deleted = 0

        for backup_file in self.config_dir.glob("config.*.backup.*.json"):
            try:
                age = now - datetime.fromtimestamp(backup_file.stat().st_mtime)
                if age.days > max_age_days:
                    backup_file.unlink()
                    deleted += 1
            except Exception as e:
                print(f"⚠️  Could not delete backup {backup_file}: {e}")

        if deleted > 0:
            print(f"🧹 Cleaned up {deleted} old backup files")


def main():
    """Command line interface for config sync."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Config Synchronisation Manager for Nanobot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  init          Initialize config directory and create initial config
  backup        Backup current external config
  sync-to-docker  Sync external config to docker config
  sync-from-docker  Sync docker config to external config
  import-docker  Import docker config to external config (creates backup)
  validate      Validate external config structure
  diff          Show differences between external and docker config
  cleanup       Remove old backup files
  list          List all config files
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Initialize command
    init_parser = subparsers.add_parser("init", help="Initialize config")
    init_parser.add_argument(
        "--dir", type=str, default="/opt/nanobot/config", help="Config directory path"
    )

    # Backup command
    subparsers.add_parser("backup", help="Backup external config")

    # Sync commands
    sync_docker_parser = subparsers.add_parser(
        "sync-to-docker", help="Sync external to docker"
    )
    sync_docker_parser.add_argument(
        "--dir", type=str, default="/opt/nanobot/config", help="Config directory path"
    )

    sync_external_parser = subparsers.add_parser(
        "sync-from-docker", help="Sync docker to external"
    )
    sync_external_parser.add_argument(
        "--dir", type=str, default="/opt/nanobot/config", help="Config directory path"
    )

    # Import command
    subparsers.add_parser("import-docker", help="Import docker config to external")

    # Validate command
    subparsers.add_parser("validate", help="Validate config structure")

    # Diff command
    subparsers.add_parser("diff", help="Show config differences")

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean old backups")
    cleanup_parser.add_argument(
        "--days", type=int, default=7, help="Max backup age in days"
    )

    # List command
    subparsers.add_parser("list", help="List config files")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    manager = ConfigSyncManager(Path(args.dir) if "dir" in args else None)

    if args.command == "init":
        manager.ensure_config_exists()
        manager.initialize_backup()

    elif args.command == "backup":
        manager.backup_external()

    elif args.command == "sync-to-docker":
        manager.sync_from_external_to_docker()

    elif args.command == "sync-from-docker":
        manager.sync_from_docker_to_external()

    elif args.command == "import-docker":
        if manager.import_docker_config():
            print("✅ Successfully imported docker config")
        else:
            print("❌ Failed to import docker config")

    elif args.command == "validate":
        manager.validate_config()

    elif args.command == "diff":
        manager.show_diff()

    elif args.command == "cleanup":
        manager.cleanup_old_backups(args.days)

    elif args.command == "list":
        print("📋 Config files:")
        print(f"   External:    {manager.external_config}")
        print(f"   Docker:      {manager.docker_config}")
        print(f"   Backup:      {manager.backup_config}")
        print(
            f"   Exists:      external={manager.external_config.exists()}, "
            f"docker={manager.docker_config.exists()}, "
            f"backup={manager.backup_config.exists()}"
        )


if __name__ == "__main__":
    main()
