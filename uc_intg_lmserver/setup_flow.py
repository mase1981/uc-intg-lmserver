"""
Setup flow for LMS integration.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any

from ucapi import (
    AbortDriverSetup,
    DriverSetupRequest,
    IntegrationSetupError,
    RequestUserInput,
    SetupAction,
    SetupComplete,
    SetupError,
    UserDataResponse,
)

from uc_intg_lmserver.config import LMSConfig
from uc_intg_lmserver.lms_client import LMSClient

_LOG = logging.getLogger(__name__)


class SetupFlow:
    def __init__(self, config: LMSConfig):
        self._config = config
        self._client: LMSClient | None = None
        self._discovered_players: list[dict[str, Any]] = []
        self._setup_state = "initial"
        self._server_host = ""
        self._server_port = 9000

    async def handle_setup(self, msg_data: DriverSetupRequest) -> SetupAction:
        _LOG.info("Starting LMS integration setup")

        self._setup_state = "server_info"
        return await self._request_server_info()

    async def handle_user_data(self, msg_data: UserDataResponse) -> SetupAction:
        input_values = msg_data.input_values

        if self._setup_state == "server_info":
            return await self._handle_server_connection(input_values)
        
        elif self._setup_state == "player_selection":
            return await self._handle_player_selection(input_values)

        return SetupError(IntegrationSetupError.OTHER)

    async def _handle_server_connection(self, input_values: dict) -> SetupAction:
        self._server_host = input_values.get("server_host", "")
        self._server_port = int(input_values.get("server_port", 9000))

        _LOG.info("Connecting to LMS server at %s:%d", self._server_host, self._server_port)
        
        await self._cleanup_client()
        
        self._client = LMSClient(self._server_host, self._server_port)

        try:
            version = await self._client.get_server_version()
            _LOG.info("Connected to LMS version %s", version)

            _LOG.info("Discovering players...")
            self._discovered_players = await self._client.get_players()
            
            _LOG.info("Discovered %d player(s):", len(self._discovered_players))
            for player in self._discovered_players:
                _LOG.info("  - %s (Model: %s, ID: %s)", 
                         player["name"], player["model"], player["playerid"])

            if not self._discovered_players:
                _LOG.warning("No players found on LMS server")
                await self._cleanup_client()
                return SetupError(IntegrationSetupError.NOT_FOUND)

            self._setup_state = "player_selection"
            return await self._request_player_selection()

        except Exception as e:
            _LOG.error("Failed to connect to LMS: %s", e, exc_info=True)
            await self._cleanup_client()
            return SetupError(IntegrationSetupError.CONNECTION_REFUSED)

    async def _handle_player_selection(self, input_values: dict) -> SetupAction:
        _LOG.info("Processing player selection")

        selected_players = []
        for key, value in input_values.items():
            if key.startswith("player_") and value:
                try:
                    player_idx = int(key.replace("player_", ""))
                    if player_idx < len(self._discovered_players):
                        selected_players.append(self._discovered_players[player_idx])
                except (ValueError, IndexError) as e:
                    _LOG.warning("Invalid player index in key %s: %s", key, e)
                    continue

        if not selected_players:
            _LOG.warning("No players selected")
            await self._cleanup_client()
            return SetupError(IntegrationSetupError.OTHER)

        _LOG.info("User selected %d player(s)", len(selected_players))

        try:
            self._config.server_host = self._server_host
            self._config.server_port = self._server_port

            players = []
            for player in selected_players:
                players.append({
                    "player_id": player["playerid"],
                    "name": player["name"],
                    "model": player["model"],
                    "enabled": True
                })

            self._config.players = players
            self._config.save()

            _LOG.info("Configuration saved successfully")

            await self._cleanup_client()

            self._setup_state = "complete"

            return SetupComplete()

        except Exception as e:
            _LOG.error("Failed to save configuration: %s", e, exc_info=True)
            await self._cleanup_client()
            return SetupError(IntegrationSetupError.OTHER)

    async def _request_server_info(self) -> RequestUserInput:
        return RequestUserInput(
            title={
                "en": "LMS Server Setup",
                "de": "LMS Server Einrichtung",
                "fr": "Configuration du serveur LMS"
            },
            settings=[
                {
                    "id": "server_host",
                    "label": {
                        "en": "LMS Server IP Address",
                        "de": "LMS Server IP-Adresse",
                        "fr": "Adresse IP du serveur LMS"
                    },
                    "field": {
                        "text": {
                            "value": ""
                        }
                    }
                },
                {
                    "id": "server_port",
                    "label": {
                        "en": "LMS Server Port",
                        "de": "LMS Server Port",
                        "fr": "Port du serveur LMS"
                    },
                    "field": {
                        "number": {
                            "value": 9000,
                            "min": 1,
                            "max": 65535
                        }
                    }
                }
            ]
        )

    async def _request_player_selection(self) -> RequestUserInput:
        settings = []

        for idx, player in enumerate(self._discovered_players):
            player_name = player["name"]
            player_model = player.get("modelname", player.get("model", "Unknown"))
            player_status = "Connected" if player.get("connected", 0) == 1 else "Disconnected"

            settings.append({
                "id": f"player_{idx}",
                "label": {
                    "en": f"{player_name} ({player_model}) - {player_status}"
                },
                "field": {
                    "checkbox": {
                        "value": player.get("connected", 0) == 1
                    }
                }
            })

        return RequestUserInput(
            title={
                "en": "Select Players",
                "de": "Wählen Sie Spieler aus",
                "fr": "Sélectionner les lecteurs"
            },
            settings=settings
        )

    async def _cleanup_client(self):
        if self._client:
            try:
                await self._client.close()
            except Exception as e:
                _LOG.debug("Error closing client: %s", e)
            finally:
                self._client = None