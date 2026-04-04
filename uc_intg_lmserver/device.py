"""
LMS device wrapper using ucapi-framework.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ucapi_framework.device import ExternalClientDevice, DeviceEvents

from uc_intg_lmserver.client import LMSClient
from uc_intg_lmserver.config import LMServerConfig
from uc_intg_lmserver.const import (
    CONNECT_RETRIES,
    CONNECT_RETRY_DELAY,
    MAX_POLL_FAILURES,
    POLL_INTERVAL,
    RECONNECT_DELAY,
    WATCHDOG_INTERVAL,
)

_LOG = logging.getLogger(__name__)


class LMServerDevice(ExternalClientDevice):

    def __init__(self, device_config: LMServerConfig, **kwargs) -> None:
        super().__init__(
            device_config=device_config,
            enable_watchdog=True,
            watchdog_interval=WATCHDOG_INTERVAL,
            reconnect_delay=RECONNECT_DELAY,
            max_reconnect_attempts=0,
            **kwargs,
        )
        self._client = LMSClient(device_config.host, device_config.port)
        self._poll_task: asyncio.Task | None = None
        self._consecutive_failures: int = 0

        self._player_states: dict[str, dict[str, Any]] = {}
        self._favorites: list[dict] = list(device_config.favorites) if device_config.favorites else []

    @property
    def identifier(self) -> str:
        return self._device_config.identifier

    @property
    def name(self) -> str:
        return self._device_config.name

    @property
    def address(self) -> str | None:
        return self._device_config.host

    @property
    def log_id(self) -> str:
        return f"LMS-{self._device_config.host}"

    @property
    def config(self) -> LMServerConfig:
        return self._device_config

    @property
    def client(self) -> LMSClient:
        return self._client

    @property
    def favorites(self) -> list[dict]:
        return self._favorites

    def get_player_state(self, player_id: str) -> dict[str, Any]:
        return self._player_states.get(player_id, {})

    def get_all_players(self) -> list[dict]:
        return list(self._device_config.players) if self._device_config.players else []

    # --- Connection lifecycle ---

    async def create_client(self) -> Any:
        self._client = LMSClient(self._device_config.host, self._device_config.port)
        return self._client

    async def connect_client(self) -> None:
        last_err: Exception | None = None
        for attempt in range(CONNECT_RETRIES):
            try:
                if not await self._client.connect():
                    raise ConnectionError(
                        f"Cannot connect to LMS at {self._device_config.host}:{self._device_config.port}"
                    )

                try:
                    self._favorites = await self._client.get_favorites()
                except Exception as err:
                    _LOG.warning("[%s] Failed to load favorites: %s", self.log_id, err)

                await self._poll_all_players()
                self._consecutive_failures = 0
                self._start_polling()

                _LOG.info(
                    "[%s] Connected, %d players, %d favorites",
                    self.log_id,
                    len(self._device_config.players),
                    len(self._favorites),
                )
                return

            except Exception as err:
                last_err = err
                if attempt < CONNECT_RETRIES - 1:
                    _LOG.warning(
                        "[%s] Connect attempt %d/%d failed: %s",
                        self.log_id, attempt + 1, CONNECT_RETRIES, err,
                    )
                    await asyncio.sleep(CONNECT_RETRY_DELAY)

        raise last_err  # type: ignore[misc]

    async def disconnect_client(self) -> None:
        self._stop_polling()
        await self._client.disconnect()

    def check_client_connected(self) -> bool:
        return self._client.is_connected

    # --- Polling ---

    def _start_polling(self) -> None:
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._poll_loop())

    def _stop_polling(self) -> None:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            self._poll_task = None

    async def _poll_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL)
                await self._poll_all_players()
                self._consecutive_failures = 0
            except asyncio.CancelledError:
                break
            except Exception as err:
                self._consecutive_failures += 1
                _LOG.error(
                    "[%s] Poll error (%d/%d): %s",
                    self.log_id, self._consecutive_failures, MAX_POLL_FAILURES, err,
                )
                if self._consecutive_failures >= MAX_POLL_FAILURES:
                    _LOG.warning("[%s] Too many poll failures, triggering reconnect", self.log_id)
                    self._client._connected = False
                    self.events.emit(DeviceEvents.DISCONNECTED, self.identifier)
                    break
                await asyncio.sleep(POLL_INTERVAL)

    async def _poll_all_players(self) -> None:
        changed = False
        for player_cfg in self._device_config.players:
            pid = player_cfg.get("player_id", "")
            if not pid:
                continue
            try:
                status = await self._client.get_player_status(pid)
                old_state = self._player_states.get(pid, {})
                new_state = self._parse_player_status(pid, status)
                if new_state != old_state:
                    self._player_states[pid] = new_state
                    changed = True
            except Exception as err:
                _LOG.debug("[%s] Failed to poll player %s: %s", self.log_id, pid, err)
                if pid in self._player_states:
                    self._player_states[pid]["state"] = "unavailable"
                    changed = True
                raise

        if changed:
            self.push_update()

    def _parse_player_status(self, player_id: str, status: dict[str, Any]) -> dict[str, Any]:
        mode = status.get("mode", "stop")
        power = status.get("power", 0)

        if power == 0:
            state = "off"
        elif mode == "play":
            state = "playing"
        elif mode == "pause":
            state = "paused"
        else:
            state = "on"

        volume = int(status.get("mixer volume", 0))
        muted = status.get("mixer muting", 0) == 1

        current_track = None
        is_remote = False

        if "remoteMeta" in status:
            current_track = status["remoteMeta"]
            is_remote = True
        elif "playlist_loop" in status and status["playlist_loop"]:
            current_track = status["playlist_loop"][0]
            is_remote = current_track.get("remote", 0) == 1

        title = ""
        artist = ""
        album = ""
        image_url = ""

        if current_track:
            title = current_track.get("title", "")
            artist = current_track.get("artist", "")
            album = current_track.get("album", "")
            if not title and is_remote:
                title = current_track.get("remote_title", "")

            artwork_url_raw = current_track.get("artwork_url", "")
            coverid = current_track.get("coverid", "")
            if artwork_url_raw or coverid:
                image_url = self._client.get_artwork_url(
                    player_id,
                    coverid=str(coverid) if coverid else None,
                    artwork_url=artwork_url_raw,
                )

        position = int(status.get("time", 0))
        duration = int(status.get("duration", 0))

        repeat_mode = status.get("playlist repeat", 0)
        shuffle_mode = status.get("playlist shuffle", 0)

        return {
            "state": state,
            "volume": volume,
            "muted": muted,
            "is_remote": is_remote,
            "title": title,
            "artist": artist,
            "album": album,
            "image_url": image_url,
            "position": position,
            "duration": duration,
            "repeat": repeat_mode,
            "shuffle": shuffle_mode,
            "power": power,
            "mode": mode,
            "raw_status": status,
        }

    # --- Player commands ---

    async def cmd_play(self, player_id: str) -> bool:
        try:
            await self._client.play(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Play failed: %s", self.log_id, err)
            return False

    async def cmd_pause(self, player_id: str) -> bool:
        try:
            await self._client.pause(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Pause failed: %s", self.log_id, err)
            return False

    async def cmd_stop(self, player_id: str) -> bool:
        try:
            await self._client.stop(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Stop failed: %s", self.log_id, err)
            return False

    async def cmd_toggle_play_pause(self, player_id: str) -> bool:
        try:
            await self._client.toggle_play_pause(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Toggle play/pause failed: %s", self.log_id, err)
            return False

    async def cmd_next(self, player_id: str) -> bool:
        try:
            await self._client.next_track(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Next failed: %s", self.log_id, err)
            return False

    async def cmd_previous(self, player_id: str) -> bool:
        try:
            await self._client.previous_track(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Previous failed: %s", self.log_id, err)
            return False

    async def cmd_seek(self, player_id: str, position: int) -> bool:
        try:
            await self._client.seek(player_id, position)
            return True
        except Exception as err:
            _LOG.error("[%s] Seek failed: %s", self.log_id, err)
            return False

    async def cmd_volume(self, player_id: str, volume: int) -> bool:
        try:
            await self._client.set_volume(player_id, volume)
            ps = self._player_states.get(player_id, {})
            ps["volume"] = volume
            self.push_update()
            return True
        except Exception as err:
            _LOG.error("[%s] Volume failed: %s", self.log_id, err)
            return False

    async def cmd_volume_up(self, player_id: str) -> bool:
        try:
            await self._client.volume_up(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Volume up failed: %s", self.log_id, err)
            return False

    async def cmd_volume_down(self, player_id: str) -> bool:
        try:
            await self._client.volume_down(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Volume down failed: %s", self.log_id, err)
            return False

    async def cmd_mute(self, player_id: str) -> bool:
        try:
            await self._client.mute(player_id)
            ps = self._player_states.get(player_id, {})
            ps["muted"] = True
            self.push_update()
            return True
        except Exception as err:
            _LOG.error("[%s] Mute failed: %s", self.log_id, err)
            return False

    async def cmd_unmute(self, player_id: str) -> bool:
        try:
            await self._client.unmute(player_id)
            ps = self._player_states.get(player_id, {})
            ps["muted"] = False
            self.push_update()
            return True
        except Exception as err:
            _LOG.error("[%s] Unmute failed: %s", self.log_id, err)
            return False

    async def cmd_toggle_mute(self, player_id: str) -> bool:
        try:
            await self._client.toggle_mute(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Toggle mute failed: %s", self.log_id, err)
            return False

    async def cmd_power_on(self, player_id: str) -> bool:
        try:
            await self._client.power_on(player_id)
            self.push_update()
            return True
        except Exception as err:
            _LOG.error("[%s] Power on failed: %s", self.log_id, err)
            return False

    async def cmd_power_off(self, player_id: str) -> bool:
        try:
            await self._client.power_off(player_id)
            self.push_update()
            return True
        except Exception as err:
            _LOG.error("[%s] Power off failed: %s", self.log_id, err)
            return False

    async def cmd_toggle_power(self, player_id: str) -> bool:
        try:
            await self._client.toggle_power(player_id)
            self.push_update()
            return True
        except Exception as err:
            _LOG.error("[%s] Toggle power failed: %s", self.log_id, err)
            return False

    async def cmd_sync(self, player_id: str, target_id: str) -> bool:
        try:
            await self._client.sync_players(player_id, target_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Sync failed: %s", self.log_id, err)
            return False

    async def cmd_unsync(self, player_id: str) -> bool:
        try:
            await self._client.unsync_player(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Unsync failed: %s", self.log_id, err)
            return False

    async def cmd_play_favorite(self, player_id: str, favorite_id: str) -> bool:
        try:
            await self._client.play_favorite(player_id, favorite_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Play favorite failed: %s", self.log_id, err)
            return False

    async def cmd_sleep_timer(self, player_id: str, minutes: int) -> bool:
        try:
            await self._client.set_sleep_timer(player_id, minutes)
            return True
        except Exception as err:
            _LOG.error("[%s] Sleep timer failed: %s", self.log_id, err)
            return False

    async def cmd_playlist_clear(self, player_id: str) -> bool:
        try:
            await self._client.playlist_clear(player_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Playlist clear failed: %s", self.log_id, err)
            return False

    async def cmd_playlist_random_songs(self, player_id: str, count: int = 10) -> bool:
        try:
            await self._client.playlist_add_random_songs(player_id, count)
            return True
        except Exception as err:
            _LOG.error("[%s] Random songs failed: %s", self.log_id, err)
            return False

    async def cmd_playlist_random_albums(self, player_id: str, count: int = 5) -> bool:
        try:
            await self._client.playlist_add_random_albums(player_id, count)
            return True
        except Exception as err:
            _LOG.error("[%s] Random albums failed: %s", self.log_id, err)
            return False

    async def cmd_set_repeat(self, player_id: str, value: str) -> bool:
        try:
            await self._client.set_repeat(player_id, value)
            return True
        except Exception as err:
            _LOG.error("[%s] Set repeat failed: %s", self.log_id, err)
            return False

    async def cmd_set_shuffle(self, player_id: str, value: str) -> bool:
        try:
            await self._client.set_shuffle(player_id, value)
            return True
        except Exception as err:
            _LOG.error("[%s] Set shuffle failed: %s", self.log_id, err)
            return False

    async def cmd_play_item(self, player_id: str, item_id: str) -> bool:
        try:
            await self._client.play_item(player_id, item_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Play item failed: %s", self.log_id, err)
            return False

    async def cmd_play_album(self, player_id: str, album_id: str) -> bool:
        try:
            await self._client.play_album(player_id, album_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Play album failed: %s", self.log_id, err)
            return False

    async def cmd_play_artist(self, player_id: str, artist_id: str) -> bool:
        try:
            await self._client.play_artist(player_id, artist_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Play artist failed: %s", self.log_id, err)
            return False

    async def cmd_play_genre(self, player_id: str, genre_id: str) -> bool:
        try:
            await self._client.play_genre(player_id, genre_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Play genre failed: %s", self.log_id, err)
            return False

    async def cmd_play_playlist(self, player_id: str, playlist_id: str) -> bool:
        try:
            await self._client.play_playlist(player_id, playlist_id)
            return True
        except Exception as err:
            _LOG.error("[%s] Play playlist failed: %s", self.log_id, err)
            return False
