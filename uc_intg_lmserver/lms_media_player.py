"""
Media player entity for LMS players.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any

from ucapi import EntityTypes, StatusCodes
from ucapi.media_player import (
    Attributes,
    Commands,
    DeviceClasses,
    Features,
    MediaPlayer,
    MediaType,
    RepeatMode,
    States,
)

from uc_intg_lmserver.lms_client import LMSClient

_LOG = logging.getLogger(__name__)


class LMSMediaPlayer(MediaPlayer):
    """Media player entity for LMS player."""

    def __init__(
        self,
        player_id: str,
        player_name: str,
        player_model: str,
        client: LMSClient,
    ):
        """Initialize LMS media player entity."""
        self._player_id = player_id
        self._player_name = player_name
        self._player_model = player_model
        self._client = client
        self._integration_api = None
        self._polling_task: asyncio.Task | None = None
        self._polling_active = False

        entity_id = self._sanitize_name(player_name)

        features = [
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
        ]

        attributes = {
            Attributes.STATE: States.UNKNOWN,
            Attributes.VOLUME: 0,
            Attributes.MUTED: False,
            Attributes.MEDIA_POSITION: 0,
            Attributes.MEDIA_DURATION: 0,
            Attributes.MEDIA_TITLE: "",
            Attributes.MEDIA_ARTIST: "",
            Attributes.MEDIA_ALBUM: "",
            Attributes.MEDIA_IMAGE_URL: "",
            Attributes.MEDIA_TYPE: MediaType.MUSIC,
            Attributes.REPEAT: RepeatMode.OFF,
            Attributes.SHUFFLE: False,
        }

        super().__init__(
            identifier=entity_id,
            name=player_name,
            features=features,
            attributes=attributes,
            device_class=DeviceClasses.SPEAKER,
        )

        _LOG.info("Created media player entity: %s (ID: %s, Model: %s)",
                 player_name, entity_id, player_model)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert player name to valid entity ID."""
        sanitized = name.lower()
        sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
        sanitized = "_".join(filter(None, sanitized.split("_")))
        return f"media_player.{sanitized}"

    def _force_integration_update(self):
        """Force update to integration API."""
        if self._integration_api and hasattr(self._integration_api, 'configured_entities'):
            try:
                self._integration_api.configured_entities.update_attributes(
                    self.id, self.attributes
                )
            except Exception as e:
                _LOG.debug("Could not update integration API for %s: %s", self.id, e)

    async def command(self, cmd_id: str, params: dict[str, Any] | None = None) -> StatusCodes:
        """Execute a media player command."""
        _LOG.info("Executing command: %s with params: %s", cmd_id, params)

        try:
            if cmd_id == Commands.VOLUME:
                if params and "volume" in params:
                    await self._client.set_volume(self._player_id, params["volume"])
                    self.attributes[Attributes.VOLUME] = params["volume"]
                    self._force_integration_update()
                    return StatusCodes.OK

            elif cmd_id == Commands.VOLUME_UP:
                await self._client.volume_up(self._player_id, step=1)
                return StatusCodes.OK

            elif cmd_id == Commands.VOLUME_DOWN:
                await self._client.volume_down(self._player_id, step=1)
                return StatusCodes.OK

            elif cmd_id == Commands.MUTE_TOGGLE:
                await self._client.toggle_mute(self._player_id)
                return StatusCodes.OK

            elif cmd_id == Commands.MUTE:
                await self._client.mute(self._player_id)
                self.attributes[Attributes.MUTED] = True
                self._force_integration_update()
                return StatusCodes.OK

            elif cmd_id == Commands.UNMUTE:
                await self._client.unmute(self._player_id)
                self.attributes[Attributes.MUTED] = False
                self._force_integration_update()
                return StatusCodes.OK

            elif cmd_id == Commands.ON:
                await self._client.power_on(self._player_id)
                return StatusCodes.OK

            elif cmd_id == Commands.OFF:
                await self._client.power_off(self._player_id)
                return StatusCodes.OK

            elif cmd_id == Commands.PLAY_PAUSE:
                await self._client.toggle_play_pause(self._player_id)
                return StatusCodes.OK

            elif cmd_id == Commands.STOP:
                await self._client.stop(self._player_id)
                return StatusCodes.OK

            elif cmd_id == Commands.NEXT:
                await self._client.next_track(self._player_id)
                return StatusCodes.OK

            elif cmd_id == Commands.PREVIOUS:
                await self._client.previous_track(self._player_id)
                return StatusCodes.OK

            elif cmd_id == Commands.SEEK:
                if params and "media_position" in params:
                    await self._client.seek(self._player_id, params["media_position"])
                    return StatusCodes.OK
                return StatusCodes.BAD_REQUEST

            else:
                _LOG.warning("Unsupported command: %s", cmd_id)
                return StatusCodes.NOT_IMPLEMENTED

        except Exception as e:
            _LOG.error("Error executing command %s: %s", cmd_id, e, exc_info=True)
            return StatusCodes.SERVER_ERROR

    async def _deferred_update(self, skip_for_volume: bool = False):
        if skip_for_volume:
            return
            
        await asyncio.sleep(0.1)
        
        try:
            await self.update_attributes()
        except Exception as e:
            _LOG.debug("Deferred update failed: %s", e)

    async def start_polling(self):
        """Start polling loop for state updates."""
        if self._polling_active:
            _LOG.warning("Polling already active for %s", self.id)
            return

        self._polling_active = True
        self._polling_task = asyncio.create_task(self._polling_loop())
        _LOG.info("Started polling for %s", self.id)

    async def stop_polling(self):
        """Stop polling loop."""
        self._polling_active = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                _LOG.info("Polling loop cancelled for %s", self.id)
            self._polling_task = None
        _LOG.info("Stopped polling for %s", self.id)

    async def _polling_loop(self):
        """Continuous polling loop for state updates."""
        _LOG.info("Polling loop started for %s", self.id)
        
        while self._polling_active:
            try:
                await self.update_attributes()

                if self.attributes[Attributes.STATE] == States.PLAYING:
                    interval = 2
                elif self.attributes[Attributes.STATE] == States.PAUSED:
                    interval = 5
                else:
                    interval = 10

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOG.error("Polling error for %s: %s", self.id, e, exc_info=True)
                await asyncio.sleep(10)

    async def update_attributes(self):
        """Update entity attributes from LMS player status."""
        try:
            status = await self._client.get_player_status(self._player_id)

            mode = status.get("mode", "stop")
            power = status.get("power", 0)

            if power == 0:
                new_state = States.OFF
            elif mode == "play":
                new_state = States.PLAYING
            elif mode == "pause":
                new_state = States.PAUSED
            elif mode == "stop":
                new_state = States.ON
            else:
                new_state = States.IDLE

            self.attributes[Attributes.STATE] = new_state
            self.attributes[Attributes.VOLUME] = status.get("mixer volume", 0)
            self.attributes[Attributes.MUTED] = status.get("mixer muting", 0) == 1

            if "playlist_loop" in status and status["playlist_loop"]:
                track = status["playlist_loop"][0]
                
                title = track.get("title", "")
                artist = track.get("artist", "")
                album = track.get("album", "")
                coverid = track.get("coverid", "")

                self.attributes[Attributes.MEDIA_TITLE] = title
                self.attributes[Attributes.MEDIA_ARTIST] = artist
                self.attributes[Attributes.MEDIA_ALBUM] = album

                # CRITICAL FIX: Use artwork URL instead of base64 to avoid WebSocket payload size limit
                if coverid:
                    artwork_url = self._client.get_artwork_url(self._player_id, coverid)
                    self.attributes[Attributes.MEDIA_IMAGE_URL] = artwork_url
                else:
                    self.attributes[Attributes.MEDIA_IMAGE_URL] = ""

                _LOG.info("State update for %s: state=%s, vol=%d, title='%s', artist='%s', album='%s'",
                         self.id, new_state, self.attributes[Attributes.VOLUME],
                         title, artist, album)
            else:
                self.attributes[Attributes.MEDIA_TITLE] = ""
                self.attributes[Attributes.MEDIA_ARTIST] = ""
                self.attributes[Attributes.MEDIA_ALBUM] = ""
                self.attributes[Attributes.MEDIA_IMAGE_URL] = ""

            self.attributes[Attributes.MEDIA_POSITION] = int(status.get("time", 0))
            self.attributes[Attributes.MEDIA_DURATION] = int(status.get("duration", 0))

            repeat_mode = status.get("playlist repeat", 0)
            if repeat_mode == 0:
                self.attributes[Attributes.REPEAT] = RepeatMode.OFF
            elif repeat_mode == 1:
                self.attributes[Attributes.REPEAT] = RepeatMode.ONE
            elif repeat_mode == 2:
                self.attributes[Attributes.REPEAT] = RepeatMode.ALL
            else:
                self.attributes[Attributes.REPEAT] = RepeatMode.OFF

            self.attributes[Attributes.SHUFFLE] = status.get("playlist shuffle", 0) == 1

            self._force_integration_update()

        except Exception as e:
            _LOG.error("Failed to update attributes for %s: %s", self.id, e, exc_info=True)
            self.attributes[Attributes.STATE] = States.UNAVAILABLE
            self._force_integration_update()

    @property
    def player_id(self) -> str:
        """Get LMS player ID (MAC address)."""
        return self._player_id