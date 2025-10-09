"""
Configuration management for LMS integration.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

_LOG = logging.getLogger(__name__)


class LMSConfig:
    """Configuration manager for LMS integration."""

    def __init__(self, data_path: str = None):
        """
        Initialize configuration manager.

        :param data_path: Optional path to configuration directory
        """
        if data_path is None:
            data_path = os.getenv("UC_CONFIG_HOME", os.path.expanduser("~/.config/uc-intg-lmserver"))
        
        self._data_path = Path(data_path)
        self._config_file = self._data_path / "config.json"
        self._config: dict[str, Any] = {}
        
        try:
            self._data_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        
        self.load()

    def load(self) -> bool:
        """
        Load configuration from disk.

        :return: True if configuration was loaded successfully
        """
        if not self._config_file.exists():
            _LOG.info("No configuration file found, starting with empty config")
            return False

        try:
            with open(self._config_file, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            _LOG.info("Configuration loaded successfully from %s", self._config_file.name)
            return True
        except Exception as e:
            _LOG.error("Failed to load configuration: %s", e)
            return False

    def save(self) -> bool:
        """
        Save configuration to disk.

        :return: True if configuration was saved successfully
        """
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
            _LOG.info("Configuration saved successfully to %s", self._config_file.name)
            return True
        except Exception as e:
            _LOG.error("Failed to save configuration: %s", e)
            return False

    def is_configured(self) -> bool:
        """
        Check if the integration has been configured.

        :return: True if server and players are configured
        """
        return bool(self.server_host and self.players)

    @property
    def server_host(self) -> str:
        """Get LMS server host."""
        return self._config.get("server_host", "")

    @server_host.setter
    def server_host(self, value: str):
        """Set LMS server host."""
        self._config["server_host"] = value

    @property
    def server_port(self) -> int:
        """Get LMS server port."""
        return self._config.get("server_port", 9000)

    @server_port.setter
    def server_port(self, value: int):
        """Set LMS server port."""
        self._config["server_port"] = value

    @property
    def players(self) -> list[dict[str, Any]]:
        """Get configured players."""
        return self._config.get("players", [])

    @players.setter
    def players(self, value: list[dict[str, Any]]):
        """Set configured players."""
        self._config["players"] = value

    def add_player(self, player_id: str, name: str, model: str) -> bool:
        """
        Add a player to the configuration.

        :param player_id: Player MAC address
        :param name: Player name
        :param model: Player model
        :return: True if player was added
        """
        players = self.players
        
        for player in players:
            if player.get("player_id") == player_id:
                _LOG.debug("Player %s already in configuration", player_id)
                return False
        
        players.append({
            "player_id": player_id,
            "name": name,
            "model": model,
            "enabled": True
        })
        
        self.players = players
        return True

    def remove_player(self, player_id: str) -> bool:
        """
        Remove a player from the configuration.

        :param player_id: Player MAC address
        :return: True if player was removed
        """
        players = self.players
        original_count = len(players)
        
        self.players = [p for p in players if p.get("player_id") != player_id]
        
        return len(self.players) < original_count

    def get_player(self, player_id: str) -> dict[str, Any] | None:
        """
        Get player configuration by ID.

        :param player_id: Player MAC address
        :return: Player configuration or None
        """
        for player in self.players:
            if player.get("player_id") == player_id:
                return player
        return None

    @property
    def polling_interval(self) -> int:
        """Get polling interval in seconds."""
        return self._config.get("polling_interval", 2)

    @polling_interval.setter
    def polling_interval(self, value: int):
        """Set polling interval in seconds."""
        self._config["polling_interval"] = value

    @property
    def artwork_enabled(self) -> bool:
        """Check if artwork fetching is enabled."""
        return self._config.get("artwork_enabled", True)

    @artwork_enabled.setter
    def artwork_enabled(self, value: bool):
        """Enable or disable artwork fetching."""
        self._config["artwork_enabled"] = value

    def clear(self):
        """Clear all configuration."""
        self._config = {}
    
    def clear_configuration(self):
        """Clear configuration (alias for compatibility)."""
        self.clear()