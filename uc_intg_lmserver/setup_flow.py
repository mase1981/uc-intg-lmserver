"""
Setup flow for LMS integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ucapi import RequestUserInput, SetupAction, UserDataResponse
from ucapi_framework import BaseSetupFlow

from uc_intg_lmserver.client import LMSClient
from uc_intg_lmserver.config import LMServerConfig
from uc_intg_lmserver.const import DEFAULT_PORT

_LOG = logging.getLogger(__name__)


class LMServerSetupFlow(BaseSetupFlow[LMServerConfig]):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._discovered_players: list[dict] = []
        self._setup_host: str = ""
        self._setup_port: int = DEFAULT_PORT

    def get_manual_entry_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "LMS Server Setup", "de": "LMS Server Einrichtung"},
            [
                {
                    "id": "host",
                    "label": {"en": "LMS Server IP Address", "de": "LMS Server IP-Adresse"},
                    "field": {"text": {"placeholder": "192.168.1.100"}},
                },
                {
                    "id": "port",
                    "label": {"en": "LMS Server Port"},
                    "field": {"text": {"placeholder": str(DEFAULT_PORT)}},
                },
            ],
        )

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> LMServerConfig | SetupAction | RequestUserInput:
        host = (input_values.get("host") or "").strip()
        port_str = (input_values.get("port") or "").strip()

        if not host:
            return self.get_manual_entry_form()

        if ":" in host:
            parts = host.rsplit(":", 1)
            host = parts[0]
            try:
                port_str = parts[1]
            except (IndexError, ValueError):
                pass

        try:
            port = int(port_str) if port_str else DEFAULT_PORT
        except ValueError:
            port = DEFAULT_PORT

        _LOG.info("Connecting to LMS at %s:%d...", host, port)

        client = LMSClient(host, port)
        try:
            if not await client.connect():
                raise ValueError(f"Cannot connect to LMS at {host}:{port}")

            version = await client.get_server_version()
            _LOG.info("Connected to LMS version %s", version)

            players = await client.get_players()
            _LOG.info("Discovered %d player(s)", len(players))

            if not players:
                raise ValueError("No players found on LMS server")

            self._discovered_players = players
            self._setup_host = host
            self._setup_port = port

            identifier = f"lms_{host.replace('.', '_')}_{port}"
            server_name = f"Lyrion Music Server ({host})"

            self._pending_device_config = LMServerConfig(
                identifier=identifier,
                name=server_name,
                host=host,
                port=port,
                players=[],
            )

            return self._create_player_selection_form(players)

        except Exception as err:
            _LOG.error("Setup failed: %s", err)
            raise ValueError(f"Setup failed: {err}") from err

        finally:
            await client.disconnect()

    def _create_player_selection_form(self, players: list[dict]) -> RequestUserInput:
        settings: list[dict] = []

        for idx, player in enumerate(players):
            name = player.get("name", f"Player {idx + 1}")
            model = player.get("modelname", player.get("model", ""))
            connected = "Connected" if player.get("connected", 0) == 1 else "Disconnected"

            settings.append({
                "id": f"player_{idx}",
                "label": {"en": f"{name} ({model}) - {connected}"},
                "field": {"checkbox": {"value": player.get("connected", 0) == 1}},
            })

        return RequestUserInput(
            {"en": "Select Players", "de": "Spieler auswählen"},
            settings,
        )

    async def handle_additional_configuration_response(
        self, msg: UserDataResponse
    ) -> LMServerConfig | None:
        selected = []
        for key, value in msg.input_values.items():
            if key.startswith("player_") and value:
                try:
                    idx = int(key.replace("player_", ""))
                    if idx < len(self._discovered_players):
                        p = self._discovered_players[idx]
                        selected.append({
                            "player_id": p.get("playerid", ""),
                            "name": p.get("name", ""),
                            "model": p.get("model", ""),
                        })
                except (ValueError, IndexError):
                    continue

        if not selected:
            raise ValueError("No players selected")

        self._pending_device_config.players = selected

        _LOG.info(
            "Setup complete: %s with %d player(s)",
            self._pending_device_config.name,
            len(selected),
        )

        return None
