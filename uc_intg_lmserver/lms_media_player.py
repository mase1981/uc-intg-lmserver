"""
Media Player entity for LMS integration.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any

from ucapi import EntityTypes, StatusCodes
from ucapi.media_player import Attributes, Commands, Features, MediaPlayer, MediaType, RepeatMode, States

from uc_intg_lmserver.lms_client import LMSClient

_LOG = logging.getLogger(__name__)


class LMSMediaPlayer(MediaPlayer):
    """Media Player entity for LMS player."""

    def __init__(
        self,
        player_id: str,
        player_name: str,
        player_model: str,
        client: LMSClient,
    ):
        self._player_id = player_id
        self._player_model = player_model
        self._client = client
        self._integration_api = None
        self._polling_task: asyncio.Task | None = None
        self._polling_active = False

        entity_id = self._sanitize_name(player_name)

        features = [
            Features.ON_OFF,
            Features.TOGGLE,
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
            Features.REPEAT,
            Features.SHUFFLE,
            Features.MEDIA_DURATION,
            Features.MEDIA_POSITION,
            Features.MEDIA_TITLE,
            Features.MEDIA_ARTIST,
            Features.MEDIA_ALBUM,
            Features.MEDIA_IMAGE_URL,
            Features.MEDIA_TYPE,
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
            device_class=None,
            options=None,
            area=None,
        )

        _LOG.info("Created media player entity: %s (ID: %s, Player: %s)", player_name, entity_id, player_id)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """
        Convert player name to valid entity ID.

        :param name: Player name
        :return: Sanitized entity ID
        """
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
        """
        Handle media player commands.

        :param cmd_id: Command ID
        :param params: Command parameters
        :return: Status code
        """
        _LOG.info("Handling command: %s with params: %s for %s", cmd_id, params, self.id)

        try:
            if cmd_id == Commands.ON:
                await self._client.power_on(self._player_id)
                await self._client.play(self._player_id)
            elif cmd_id == Commands.OFF:
                await self._client.power_off(self._player_id)
            elif cmd_id == Commands.TOGGLE:
                await self._client.toggle_power(self._player_id)
            elif cmd_id == Commands.PLAY_PAUSE:
                await self._client.toggle_play_pause(self._player_id)
            elif cmd_id == Commands.STOP:
                await self._client.stop(self._player_id)
            elif cmd_id == Commands.PREVIOUS:
                await self._client.previous_track(self._player_id)
            elif cmd_id == Commands.NEXT:
                await self._client.next_track(self._player_id)
            elif cmd_id == Commands.VOLUME:
                if params and "volume" in params:
                    volume = int(params["volume"])
                    await self._client.set_volume(self._player_id, volume)
                else:
                    return StatusCodes.BAD_REQUEST
            elif cmd_id == Commands.VOLUME_UP:
                await self._client.volume_up(self._player_id)
            elif cmd_id == Commands.VOLUME_DOWN:
                await self._client.volume_down(self._player_id)
            elif cmd_id == Commands.MUTE_TOGGLE:
                await self._client.toggle_mute(self._player_id)
            elif cmd_id == Commands.MUTE:
                await self._client.mute(self._player_id)
            elif cmd_id == Commands.UNMUTE:
                await self._client.unmute(self._player_id)
            elif cmd_id == Commands.SEEK:
                if params and "media_position" in params:
                    position = int(params["media_position"])
                    await self._client.seek(self._player_id, position)
                else:
                    return StatusCodes.BAD_REQUEST
            elif cmd_id == Commands.REPEAT:
                if params and "repeat" in params:
                    await self._handle_repeat_command(params["repeat"])
                else:
                    return StatusCodes.BAD_REQUEST
            elif cmd_id == Commands.SHUFFLE:
                if params and "shuffle" in params:
                    await self._handle_shuffle_command(params["shuffle"])
                else:
                    return StatusCodes.BAD_REQUEST
            else:
                _LOG.warning("Unsupported command: %s", cmd_id)
                return StatusCodes.NOT_IMPLEMENTED

            # Skip deferred update for volume commands - polling will catch them quickly
            if cmd_id not in [Commands.VOLUME, Commands.VOLUME_UP, Commands.VOLUME_DOWN]:
                asyncio.create_task(self._deferred_update())
            
            return StatusCodes.OK

        except Exception as e:
            _LOG.error("Error executing command %s: %s", cmd_id, e, exc_info=True)
            return StatusCodes.SERVER_ERROR

    async def _handle_repeat_command(self, repeat_mode: str):
        """Handle repeat mode command."""
        mode_map = {
            "OFF": "0",
            "ONE": "1",
            "ALL": "2",
        }
        
        lms_mode = mode_map.get(repeat_mode, "0")
        await self._client.send_command(self._player_id, ["playlist", "repeat", lms_mode])
        _LOG.info("Set repeat mode to: %s (LMS: %s)", repeat_mode, lms_mode)

    async def _handle_shuffle_command(self, shuffle: bool):
        """Handle shuffle command."""
        shuffle_mode = "1" if shuffle else "0"
        await self._client.send_command(self._player_id, ["playlist", "shuffle", shuffle_mode])
        _LOG.info("Set shuffle to: %s", shuffle)

    async def _deferred_update(self):
        """Update attributes after a short delay."""
        await asyncio.sleep(0.1)
        await self.update_attributes()

    async def start_polling(self):
        """Start status polling loop."""
        if self._polling_active:
            _LOG.warning("Polling already active for %s", self.id)
            return

        self._polling_active = True
        self._polling_task = asyncio.create_task(self._polling_loop())
        _LOG.info("Started polling for %s", self.id)

    async def stop_polling(self):
        """Stop status polling loop."""
        self._polling_active = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
        _LOG.info("Stopped polling for %s", self.id)

    async def _polling_loop(self):
        """Continuous status polling loop with adaptive intervals."""
        _LOG.info("Polling loop started for %s", self.id)
        
        while self._polling_active:
            try:
                await self.update_attributes()

                # Adaptive polling interval based on state
                if self.attributes[Attributes.STATE] == States.PLAYING:
                    interval = 2
                elif self.attributes[Attributes.STATE] == States.PAUSED:
                    interval = 5
                else:
                    interval = 10

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                _LOG.info("Polling loop cancelled for %s", self.id)
                break
            except Exception as e:
                _LOG.error("Polling error for %s: %s", self.id, e, exc_info=True)
                await asyncio.sleep(10)

    async def update_attributes(self):
        """Update entity attributes from LMS and push to Remote."""
        if not self._client:
            return

        try:
            _LOG.debug("Updating attributes for %s", self.id)
            status = await self._client.get_player_status(self._player_id)

            power = status.get("power", 0)
            if power == 0:
                self.attributes[Attributes.STATE] = States.OFF
            else:
                mode = status.get("mode", "stop")
                if mode == "play":
                    self.attributes[Attributes.STATE] = States.PLAYING
                elif mode == "pause":
                    self.attributes[Attributes.STATE] = States.PAUSED
                else:
                    self.attributes[Attributes.STATE] = States.ON

            volume = status.get("mixer volume")
            if volume is not None:
                self.attributes[Attributes.VOLUME] = int(volume)

            muting = status.get("mixer muting", 0)
            self.attributes[Attributes.MUTED] = bool(muting)

            repeat_mode = status.get("playlist repeat", 0)
            repeat_map = {
                0: RepeatMode.OFF,
                1: RepeatMode.ONE,
                2: RepeatMode.ALL,
            }
            self.attributes[Attributes.REPEAT] = repeat_map.get(int(repeat_mode), RepeatMode.OFF)

            shuffle_mode = status.get("playlist shuffle", 0)
            self.attributes[Attributes.SHUFFLE] = int(shuffle_mode) > 0

            playlist_loop = status.get("playlist_loop", [])
            coverid = None
            
            if playlist_loop and len(playlist_loop) > 0:
                track = playlist_loop[0]
                
                title = track.get("title", "")
                self.attributes[Attributes.MEDIA_TITLE] = title if title else ""
                
                artist = track.get("artist")
                self.attributes[Attributes.MEDIA_ARTIST] = artist if artist else ""
                
                album = track.get("album")
                self.attributes[Attributes.MEDIA_ALBUM] = album if album else ""
                
                coverid = track.get("coverid")
                
                _LOG.debug("Track info - Title: '%s', Artist: '%s', Album: '%s', CoverID: '%s'",
                          title, artist, album, coverid)
            else:
                self.attributes[Attributes.MEDIA_TITLE] = ""
                self.attributes[Attributes.MEDIA_ARTIST] = ""
                self.attributes[Attributes.MEDIA_ALBUM] = ""

            time = status.get("time")
            if time is not None:
                self.attributes[Attributes.MEDIA_POSITION] = int(float(time))
            else:
                self.attributes[Attributes.MEDIA_POSITION] = 0

            duration = status.get("duration")
            if duration is not None:
                self.attributes[Attributes.MEDIA_DURATION] = int(float(duration))
            else:
                self.attributes[Attributes.MEDIA_DURATION] = 0

            # Fetch artwork if track info exists, regardless of play state
            # This fixes the issue where stopped/paused players don't show artwork
            if coverid:
                artwork = await self._client.fetch_artwork_as_base64(self._player_id, coverid)
                self.attributes[Attributes.MEDIA_IMAGE_URL] = artwork
            else:
                self.attributes[Attributes.MEDIA_IMAGE_URL] = ""

            _LOG.info("State update for %s: state=%s, vol=%s, title='%s', artist='%s', album='%s'", 
                      self.id, self.attributes[Attributes.STATE], self.attributes[Attributes.VOLUME],
                      self.attributes[Attributes.MEDIA_TITLE], 
                      self.attributes[Attributes.MEDIA_ARTIST],
                      self.attributes[Attributes.MEDIA_ALBUM])

            self._force_integration_update()

        except Exception as e:
            _LOG.error("Failed to update attributes for %s: %s", self.id, e, exc_info=True)
            self.attributes[Attributes.STATE] = States.UNAVAILABLE
            self._force_integration_update()

    @property
    def player_id(self) -> str:
        """Get LMS player ID (MAC address)."""
        return self._player_id