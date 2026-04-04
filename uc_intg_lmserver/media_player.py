"""
LMS media player entity.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import Any

from ucapi import StatusCodes
from ucapi.api_definitions import BrowseOptions, BrowseResults, SearchOptions, SearchResults
from ucapi.media_player import Attributes, Commands, DeviceClasses, Features, MediaType, RepeatMode, States
from ucapi_framework import MediaPlayerEntity

from uc_intg_lmserver import browser
from uc_intg_lmserver.config import LMServerConfig
from uc_intg_lmserver.device import LMServerDevice

_LOG = logging.getLogger(__name__)

_FEATURES = [
    Features.ON_OFF,
    Features.VOLUME,
    Features.VOLUME_UP_DOWN,
    Features.MUTE_TOGGLE,
    Features.MUTE,
    Features.UNMUTE,
    Features.PLAY_PAUSE,
    Features.STOP,
    Features.NEXT,
    Features.PREVIOUS,
    Features.SEEK,
    Features.MEDIA_TITLE,
    Features.MEDIA_ARTIST,
    Features.MEDIA_ALBUM,
    Features.MEDIA_IMAGE_URL,
    Features.MEDIA_POSITION,
    Features.MEDIA_DURATION,
    Features.MEDIA_TYPE,
    Features.REPEAT,
    Features.SHUFFLE,
    Features.BROWSE_MEDIA,
    Features.SEARCH_MEDIA,
    Features.PLAY_MEDIA,
]


def _sanitize_name(name: str) -> str:
    sanitized = name.lower()
    sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
    return "_".join(filter(None, sanitized.split("_")))


def create_media_players(
    device_config: LMServerConfig, device: LMServerDevice
) -> list[LMSMediaPlayer]:
    entities = []
    for player in device_config.players:
        entities.append(LMSMediaPlayer(device_config, device, player))
    return entities


class LMSMediaPlayer(MediaPlayerEntity):

    def __init__(
        self, device_config: LMServerConfig, device: LMServerDevice, player: dict
    ) -> None:
        self._device = device
        self._device_config = device_config
        self._player_id = player.get("player_id", "")
        self._player_name = player.get("name", "Unknown")

        entity_id = f"media_player.{device_config.identifier}.{_sanitize_name(self._player_name)}"

        attributes = {
            Attributes.STATE: States.STANDBY,
            Attributes.VOLUME: 0,
            Attributes.MUTED: False,
        }

        super().__init__(
            entity_id,
            self._player_name,
            _FEATURES,
            attributes,
            device_class=DeviceClasses.SPEAKER,
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    @property
    def player_id(self) -> str:
        return self._player_id

    async def sync_state(self) -> None:
        ps = self._device.get_player_state(self._player_id)
        if not ps:
            self.update({Attributes.STATE: States.UNAVAILABLE})
            return

        state_str = ps.get("state", "off")
        if state_str == "playing":
            state = States.PLAYING
        elif state_str == "paused":
            state = States.PAUSED
        elif state_str == "off":
            state = States.OFF
        elif state_str == "unavailable":
            state = States.UNAVAILABLE
        else:
            state = States.ON

        repeat_val = ps.get("repeat", 0)
        if repeat_val == 1:
            repeat = RepeatMode.ONE
        elif repeat_val == 2:
            repeat = RepeatMode.ALL
        else:
            repeat = RepeatMode.OFF

        self.update({
            Attributes.STATE: state,
            Attributes.VOLUME: ps.get("volume", 0),
            Attributes.MUTED: ps.get("muted", False),
            Attributes.MEDIA_TITLE: ps.get("title", ""),
            Attributes.MEDIA_ARTIST: ps.get("artist", ""),
            Attributes.MEDIA_ALBUM: ps.get("album", ""),
            Attributes.MEDIA_IMAGE_URL: ps.get("image_url", ""),
            Attributes.MEDIA_POSITION: ps.get("position", 0),
            Attributes.MEDIA_DURATION: ps.get("duration", 0),
            Attributes.MEDIA_TYPE: MediaType.MUSIC,
            Attributes.REPEAT: repeat,
            Attributes.SHUFFLE: ps.get("shuffle", 0) == 1,
        })

    async def browse(self, options: BrowseOptions) -> BrowseResults | StatusCodes:
        return await browser.browse(self._device, self._player_id, options)

    async def search(self, options: SearchOptions) -> SearchResults | StatusCodes:
        return await browser.search(self._device, self._player_id, options)

    async def _handle_command(
        self, entity: MediaPlayerEntity, cmd_id: str, params: dict[str, Any] | None = None
    ) -> StatusCodes:
        dev = self._device
        pid = self._player_id
        params = params or {}

        try:
            if cmd_id == Commands.ON:
                await dev.cmd_power_on(pid)
            elif cmd_id == Commands.OFF:
                await dev.cmd_power_off(pid)
            elif cmd_id == Commands.PLAY_PAUSE:
                await dev.cmd_toggle_play_pause(pid)
            elif cmd_id == Commands.STOP:
                await dev.cmd_stop(pid)
            elif cmd_id == Commands.NEXT:
                await dev.cmd_next(pid)
            elif cmd_id == Commands.PREVIOUS:
                await dev.cmd_previous(pid)
            elif cmd_id == Commands.VOLUME:
                await dev.cmd_volume(pid, int(params.get("volume", 0)))
            elif cmd_id == Commands.VOLUME_UP:
                await dev.cmd_volume_up(pid)
            elif cmd_id == Commands.VOLUME_DOWN:
                await dev.cmd_volume_down(pid)
            elif cmd_id == Commands.MUTE_TOGGLE:
                await dev.cmd_toggle_mute(pid)
            elif cmd_id == Commands.MUTE:
                await dev.cmd_mute(pid)
            elif cmd_id == Commands.UNMUTE:
                await dev.cmd_unmute(pid)
            elif cmd_id == Commands.SEEK:
                pos = params.get("media_position", 0)
                await dev.cmd_seek(pid, int(pos))
            elif cmd_id == Commands.REPEAT:
                mode = params.get("repeat", "OFF")
                lms_val = {"OFF": "0", "ONE": "1", "ALL": "2"}.get(mode, "0")
                await dev.cmd_set_repeat(pid, lms_val)
            elif cmd_id == Commands.SHUFFLE:
                enabled = params.get("shuffle", False)
                await dev.cmd_set_shuffle(pid, "1" if enabled else "0")
            elif cmd_id == Commands.PLAY_MEDIA:
                return await self._handle_play_media(params)
            else:
                return StatusCodes.NOT_IMPLEMENTED

            return StatusCodes.OK

        except Exception as err:
            _LOG.error("Command %s failed for %s: %s", cmd_id, self._player_name, err)
            return StatusCodes.SERVER_ERROR

    async def _handle_play_media(self, params: dict[str, Any]) -> StatusCodes:
        media_type = params.get("media_type", "")
        media_id = params.get("media_id", "")
        dev = self._device
        pid = self._player_id

        if not media_id:
            return StatusCodes.BAD_REQUEST

        if media_type == "track":
            await dev.cmd_play_item(pid, media_id)
        elif media_type == "album":
            await dev.cmd_play_album(pid, media_id)
        elif media_type == "artist":
            await dev.cmd_play_artist(pid, media_id)
        elif media_type == "genre":
            await dev.cmd_play_genre(pid, media_id)
        elif media_type == "playlist":
            await dev.cmd_play_playlist(pid, media_id)
        elif media_type == "favorite":
            await dev.cmd_play_favorite(pid, media_id)
        else:
            return StatusCodes.BAD_REQUEST

        return StatusCodes.OK
