"""
LMS remote entity for player control and sync.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import Any

from ucapi import StatusCodes
from ucapi.remote import Attributes, Commands, Features, States
from ucapi_framework import RemoteEntity

from uc_intg_lmserver.config import LMServerConfig
from uc_intg_lmserver.const import MAX_FAVOURITE_COMMANDS
from uc_intg_lmserver.device import LMServerDevice

_LOG = logging.getLogger(__name__)


def _sanitize_name(name: str) -> str:
    sanitized = name.lower()
    sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
    return "_".join(filter(None, sanitized.split("_")))


def create_remotes(
    device_config: LMServerConfig, device: LMServerDevice
) -> list[LMSRemote]:
    entities = []
    for player in device_config.players:
        entities.append(LMSRemote(device_config, device, player))
    return entities


class LMSRemote(RemoteEntity):

    def __init__(
        self, device_config: LMServerConfig, device: LMServerDevice, player: dict
    ) -> None:
        self._device = device
        self._device_config = device_config
        self._player_id = player.get("player_id", "")
        self._player_name = player.get("name", "Unknown")

        entity_id = f"remote.{device_config.identifier}.{_sanitize_name(self._player_name)}"

        simple_commands = self._build_simple_commands(device_config, player)
        ui_pages = self._build_ui_pages(device_config, player)

        attributes = {Attributes.STATE: States.OFF}

        super().__init__(
            entity_id,
            f"{self._player_name} Control",
            [Features.ON_OFF, Features.SEND_CMD],
            attributes,
            simple_commands=simple_commands,
            ui_pages=ui_pages,
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        ps = self._device.get_player_state(self._player_id)
        power = ps.get("power", 0) if ps else 0
        state = States.ON if power == 1 else States.OFF
        self.update({Attributes.STATE: state})

    def _build_simple_commands(
        self, config: LMServerConfig, player: dict
    ) -> list[str]:
        commands = [
            "PLAY", "PAUSE", "STOP", "PLAY_PAUSE",
            "NEXT", "PREVIOUS",
            "VOLUME_UP", "VOLUME_DOWN", "MUTE_TOGGLE",
            "POWER_ON", "POWER_OFF", "POWER_TOGGLE",
            "UNSYNC",
            "SLEEP_15", "SLEEP_30", "SLEEP_60", "SLEEP_90", "SLEEP_CANCEL",
            "PLAYLIST_CLEAR", "RANDOM_SONGS", "RANDOM_ALBUMS",
        ]

        for p in config.players:
            if p.get("player_id") != self._player_id:
                cmd_name = f"SYNC_{_sanitize_name(p.get('name', ''))}"
                commands.append(cmd_name)

        num_favs = min(len(self._device.favorites), MAX_FAVOURITE_COMMANDS)
        for i in range(1, num_favs + 1):
            commands.append(f"FAVORITE_{i}")

        return commands

    def _build_ui_pages(
        self, config: LMServerConfig, player: dict
    ) -> list[dict[str, Any]]:
        pages = [self._main_page()]

        other_players = [p for p in config.players if p.get("player_id") != self._player_id]
        if other_players:
            pages.append(self._sync_page(other_players))

        if self._device.favorites:
            pages.append(self._favorites_page())

        pages.append(self._playlist_page())
        return pages

    def _main_page(self) -> dict[str, Any]:
        return {
            "page_id": "main",
            "name": "Playback",
            "grid": {"width": 4, "height": 6},
            "items": [
                {"type": "icon", "icon": "uc:prev", "command": {"cmd_id": "PREVIOUS"},
                 "location": {"x": 0, "y": 0}},
                {"type": "text", "text": "Play/Pause", "command": {"cmd_id": "PLAY_PAUSE"},
                 "location": {"x": 1, "y": 0}, "size": {"width": 2, "height": 1}},
                {"type": "icon", "icon": "uc:next", "command": {"cmd_id": "NEXT"},
                 "location": {"x": 3, "y": 0}},
                {"type": "text", "text": "Vol-", "command": {"cmd_id": "VOLUME_DOWN"},
                 "location": {"x": 0, "y": 1}},
                {"type": "text", "text": "Vol+", "command": {"cmd_id": "VOLUME_UP"},
                 "location": {"x": 1, "y": 1}},
                {"type": "text", "text": "Mute", "command": {"cmd_id": "MUTE_TOGGLE"},
                 "location": {"x": 2, "y": 1}},
                {"type": "text", "text": "Stop", "command": {"cmd_id": "STOP"},
                 "location": {"x": 3, "y": 1}},
                {"type": "text", "text": "On", "command": {"cmd_id": "POWER_ON"},
                 "location": {"x": 0, "y": 2}},
                {"type": "text", "text": "Off", "command": {"cmd_id": "POWER_OFF"},
                 "location": {"x": 1, "y": 2}},
                {"type": "text", "text": "Sleep 15", "command": {"cmd_id": "SLEEP_15"},
                 "location": {"x": 0, "y": 3}},
                {"type": "text", "text": "Sleep 30", "command": {"cmd_id": "SLEEP_30"},
                 "location": {"x": 1, "y": 3}},
                {"type": "text", "text": "Sleep 60", "command": {"cmd_id": "SLEEP_60"},
                 "location": {"x": 2, "y": 3}},
                {"type": "text", "text": "Cancel", "command": {"cmd_id": "SLEEP_CANCEL"},
                 "location": {"x": 3, "y": 3}},
            ],
        }

    def _sync_page(self, other_players: list[dict]) -> dict[str, Any]:
        items: list[dict] = [
            {"type": "text", "text": "Ungroup", "command": {"cmd_id": "UNSYNC"},
             "location": {"x": 0, "y": 0}},
        ]
        col, row = 1, 0
        for p in other_players:
            if row >= 6:
                break
            name = p.get("name", "?")
            cmd_name = f"SYNC_{_sanitize_name(name)}"
            items.append({
                "type": "text",
                "text": f"→{name[:8]}",
                "command": {"cmd_id": cmd_name},
                "location": {"x": col, "y": row},
            })
            col += 1
            if col >= 4:
                col = 0
                row += 1

        return {
            "page_id": "sync",
            "name": "Group Players",
            "grid": {"width": 4, "height": 6},
            "items": items,
        }

    def _favorites_page(self) -> dict[str, Any]:
        items: list[dict] = []
        col, row = 0, 0
        for i, fav in enumerate(self._device.favorites[:24], 1):
            if row >= 6:
                break
            name = fav.get("name", f"Fav {i}")
            items.append({
                "type": "text",
                "text": name[:10],
                "command": {"cmd_id": f"FAVORITE_{i}"},
                "location": {"x": col, "y": row},
            })
            col += 1
            if col >= 4:
                col = 0
                row += 1

        return {
            "page_id": "favorites",
            "name": "Favorites",
            "grid": {"width": 4, "height": 6},
            "items": items,
        }

    def _playlist_page(self) -> dict[str, Any]:
        return {
            "page_id": "playlist",
            "name": "Playlist",
            "grid": {"width": 4, "height": 6},
            "items": [
                {"type": "text", "text": "Clear", "command": {"cmd_id": "PLAYLIST_CLEAR"},
                 "location": {"x": 0, "y": 0}},
                {"type": "text", "text": "+10 Songs", "command": {"cmd_id": "RANDOM_SONGS"},
                 "location": {"x": 1, "y": 0}},
                {"type": "text", "text": "+5 Albums", "command": {"cmd_id": "RANDOM_ALBUMS"},
                 "location": {"x": 2, "y": 0}},
            ],
        }

    async def _handle_command(
        self, entity: RemoteEntity, cmd_id: str, params: dict[str, Any] | None = None
    ) -> StatusCodes:
        params = params or {}

        if cmd_id == Commands.ON:
            await self._device.cmd_power_on(self._player_id)
            return StatusCodes.OK
        if cmd_id == Commands.OFF:
            await self._device.cmd_power_off(self._player_id)
            return StatusCodes.OK

        if cmd_id == Commands.SEND_CMD:
            command = params.get("command", "")
            if not command:
                return StatusCodes.BAD_REQUEST
            return await self._dispatch(command)

        return StatusCodes.NOT_IMPLEMENTED

    async def _dispatch(self, command: str) -> StatusCodes:
        dev = self._device
        pid = self._player_id

        try:
            if command == "PLAY":
                await dev.cmd_play(pid)
            elif command == "PAUSE":
                await dev.cmd_pause(pid)
            elif command == "STOP":
                await dev.cmd_stop(pid)
            elif command == "PLAY_PAUSE":
                await dev.cmd_toggle_play_pause(pid)
            elif command == "NEXT":
                await dev.cmd_next(pid)
            elif command == "PREVIOUS":
                await dev.cmd_previous(pid)
            elif command == "VOLUME_UP":
                await dev.cmd_volume_up(pid)
            elif command == "VOLUME_DOWN":
                await dev.cmd_volume_down(pid)
            elif command == "MUTE_TOGGLE":
                await dev.cmd_toggle_mute(pid)
            elif command == "POWER_ON":
                await dev.cmd_power_on(pid)
            elif command == "POWER_OFF":
                await dev.cmd_power_off(pid)
            elif command == "POWER_TOGGLE":
                await dev.cmd_toggle_power(pid)
            elif command == "UNSYNC":
                await dev.cmd_unsync(pid)
            elif command.startswith("SYNC_"):
                target_name = command.replace("SYNC_", "")
                target_id = self._find_player_id(target_name)
                if target_id:
                    await dev.cmd_sync(pid, target_id)
                else:
                    return StatusCodes.NOT_FOUND
            elif command.startswith("FAVORITE_"):
                return await self._play_favorite(command)
            elif command.startswith("SLEEP_"):
                return await self._handle_sleep(command)
            elif command == "PLAYLIST_CLEAR":
                await dev.cmd_playlist_clear(pid)
            elif command == "RANDOM_SONGS":
                await dev.cmd_playlist_random_songs(pid, 10)
            elif command == "RANDOM_ALBUMS":
                await dev.cmd_playlist_random_albums(pid, 5)
            else:
                _LOG.warning("Unknown remote command: %s", command)
                return StatusCodes.NOT_IMPLEMENTED

            return StatusCodes.OK

        except Exception as err:
            _LOG.error("Remote command %s failed: %s", command, err)
            return StatusCodes.SERVER_ERROR

    def _find_player_id(self, sanitized_name: str) -> str | None:
        for p in self._device_config.players:
            if _sanitize_name(p.get("name", "")) == sanitized_name:
                return p.get("player_id")
        return None

    async def _play_favorite(self, command: str) -> StatusCodes:
        try:
            fav_num = int(command.split("_")[1])
            favs = self._device.favorites
            if 0 < fav_num <= len(favs):
                fav_id = str(favs[fav_num - 1].get("id", ""))
                if fav_id:
                    await self._device.cmd_play_favorite(self._player_id, fav_id)
                    return StatusCodes.OK
            return StatusCodes.BAD_REQUEST
        except (ValueError, IndexError) as err:
            _LOG.error("Invalid favorite command %s: %s", command, err)
            return StatusCodes.BAD_REQUEST

    async def _handle_sleep(self, command: str) -> StatusCodes:
        if command == "SLEEP_CANCEL":
            await self._device.cmd_sleep_timer(self._player_id, 0)
            return StatusCodes.OK
        try:
            minutes = int(command.split("_")[1])
            await self._device.cmd_sleep_timer(self._player_id, minutes)
            return StatusCodes.OK
        except (ValueError, IndexError) as err:
            _LOG.error("Invalid sleep command %s: %s", command, err)
            return StatusCodes.BAD_REQUEST
