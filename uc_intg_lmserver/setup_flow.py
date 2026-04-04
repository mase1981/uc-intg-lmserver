"""
Setup flow for LMS integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ucapi import RequestUserInput, SetupAction
from ucapi_framework import BaseSetupFlow

from uc_intg_lmserver.client import LMSClient
from uc_intg_lmserver.config import LMServerConfig
from uc_intg_lmserver.const import DEFAULT_PORT

_LOG = logging.getLogger(__name__)


class LMServerSetupFlow(BaseSetupFlow[LMServerConfig]):

    async def get_pre_discovery_screen(self) -> RequestUserInput | None:
        return self.get_manual_entry_form()

    async def _handle_discovery(self) -> SetupAction:
        if self._pre_discovery_data:
            host = self._pre_discovery_data.get("host")
            if not host:
                return self.get_manual_entry_form()
            try:
                result = await self.query_device(self._pre_discovery_data)
                if hasattr(result, "identifier"):
                    return await self._finalize_device_setup(result, self._pre_discovery_data)
                return result
            except Exception as err:
                _LOG.error("Discovery failed: %s", err)
                return self.get_manual_entry_form()

        return await self._handle_manual_entry()

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
    ) -> LMServerConfig | RequestUserInput:
        players_json = input_values.get("_players", "")
        if players_json:
            return self._finalize_player_selection(input_values, players_json)

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

            return self._create_player_selection_form(host, port, players)

        except Exception as err:
            _LOG.error("Setup failed: %s", err)
            raise ValueError(f"Setup failed: {err}") from err

        finally:
            await client.disconnect()

    def _create_player_selection_form(
        self, host: str, port: int, players: list[dict]
    ) -> RequestUserInput:
        settings: list[dict] = [
            {
                "id": "_players",
                "label": {"en": ""},
                "field": {"text": {"value": json.dumps({"host": host, "port": port, "players": players})}},
            },
        ]

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

    def _finalize_player_selection(
        self, input_values: dict[str, Any], players_json: str
    ) -> LMServerConfig:
        try:
            data = json.loads(players_json)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("Invalid player data")

        host = data.get("host", "")
        port = data.get("port", DEFAULT_PORT)
        all_players = data.get("players", [])

        selected = []
        for key, value in input_values.items():
            if key.startswith("player_") and value:
                try:
                    idx = int(key.replace("player_", ""))
                    if idx < len(all_players):
                        p = all_players[idx]
                        selected.append({
                            "player_id": p.get("playerid", ""),
                            "name": p.get("name", ""),
                            "model": p.get("model", ""),
                        })
                except (ValueError, IndexError):
                    continue

        if not selected:
            raise ValueError("No players selected")

        identifier = f"lms_{host.replace('.', '_')}_{port}"
        server_name = f"Lyrion Music Server ({host})"

        _LOG.info("Setup complete: %s with %d player(s)", server_name, len(selected))

        return LMServerConfig(
            identifier=identifier,
            name=server_name,
            host=host,
            port=port,
            players=selected,
        )
