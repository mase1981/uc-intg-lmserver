"""
LMS JSON-RPC client for communication with Lyrion Music Server.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from uc_intg_lmserver.const import REQUEST_TIMEOUT

_LOG = logging.getLogger(__name__)


class LMSClient:

    def __init__(self, host: str, port: int = 9000) -> None:
        self._host = host
        self._port = port
        self._base_url = f"http://{host}:{port}"
        self._jsonrpc_url = f"{self._base_url}/jsonrpc.js"
        self._session: aiohttp.ClientSession | None = None
        self._request_id = 0
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def base_url(self) -> str:
        return self._base_url

    async def connect(self) -> bool:
        await self._ensure_session()
        try:
            version = await self.get_server_version()
            self._connected = True
            _LOG.info("Connected to LMS %s at %s:%d", version, self._host, self._port)
            return True
        except Exception as err:
            self._connected = False
            _LOG.error("Cannot connect to LMS at %s:%d: %s", self._host, self._port, err)
            return False

    async def disconnect(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        self._connected = False

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    def _get_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def send_command(self, player_id: str, command: list) -> dict[str, Any]:
        await self._ensure_session()
        payload = {
            "id": self._get_request_id(),
            "method": "slim.request",
            "params": [player_id, command],
        }
        _LOG.debug("LMS command: player=%s cmd=%s", player_id, command)
        async with self._session.post(
            self._jsonrpc_url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data

    # --- Server queries ---

    async def get_server_version(self) -> str:
        result = await self.send_command("", ["version", "?"])
        return result.get("result", {}).get("_version", "Unknown")

    async def get_players(self) -> list[dict[str, Any]]:
        result = await self.send_command("", ["players", "0", "999"])
        players_data = result.get("result", {}).get("players_loop", [])
        players = []
        for p in players_data:
            players.append({
                "playerid": p.get("playerid", ""),
                "name": p.get("name", "Unknown Player"),
                "model": p.get("model", "unknown"),
                "modelname": p.get("modelname", "Unknown Model"),
                "ip": p.get("ip", ""),
                "connected": p.get("connected", 0),
            })
        return players

    async def get_player_status(self, player_id: str) -> dict[str, Any]:
        result = await self.send_command(
            player_id, ["status", "-", "1", "tags:AaltdcKxN"]
        )
        return result.get("result", {})

    async def get_favorites(self) -> list[dict[str, Any]]:
        result = await self.send_command("", ["favorites", "items", "0", "100"])
        return result.get("result", {}).get("loop_loop", [])

    # --- Playback control ---

    async def play(self, player_id: str) -> None:
        await self.send_command(player_id, ["play"])

    async def pause(self, player_id: str) -> None:
        await self.send_command(player_id, ["pause", "1"])

    async def stop(self, player_id: str) -> None:
        await self.send_command(player_id, ["stop"])

    async def toggle_play_pause(self, player_id: str) -> None:
        await self.send_command(player_id, ["pause"])

    async def next_track(self, player_id: str) -> None:
        await self.send_command(player_id, ["playlist", "index", "+1"])

    async def previous_track(self, player_id: str) -> None:
        await self.send_command(player_id, ["playlist", "index", "-1"])

    async def seek(self, player_id: str, position: int) -> None:
        await self.send_command(player_id, ["time", str(position)])

    # --- Volume ---

    async def set_volume(self, player_id: str, volume: int) -> None:
        volume = max(0, min(100, volume))
        await self.send_command(player_id, ["mixer", "volume", str(volume)])

    async def volume_up(self, player_id: str, step: int = 1) -> None:
        await self.send_command(player_id, ["mixer", "volume", f"+{step}"])

    async def volume_down(self, player_id: str, step: int = 1) -> None:
        await self.send_command(player_id, ["mixer", "volume", f"-{step}"])

    async def mute(self, player_id: str) -> None:
        await self.send_command(player_id, ["mixer", "muting", "1"])

    async def unmute(self, player_id: str) -> None:
        await self.send_command(player_id, ["mixer", "muting", "0"])

    async def toggle_mute(self, player_id: str) -> None:
        await self.send_command(player_id, ["mixer", "muting", "toggle"])

    # --- Power ---

    async def power_on(self, player_id: str) -> None:
        await self.send_command(player_id, ["power", "1"])

    async def power_off(self, player_id: str) -> None:
        await self.send_command(player_id, ["power", "0"])

    async def toggle_power(self, player_id: str) -> None:
        await self.send_command(player_id, ["power"])

    # --- Sync ---

    async def sync_players(self, player_id: str, target_player_id: str) -> None:
        await self.send_command(player_id, ["sync", target_player_id])

    async def unsync_player(self, player_id: str) -> None:
        await self.send_command(player_id, ["sync", "-"])

    # --- Playlist ---

    async def play_favorite(self, player_id: str, favorite_id: str) -> None:
        await self.send_command(
            player_id, ["favorites", "playlist", "play", f"item_id:{favorite_id}"]
        )

    async def set_sleep_timer(self, player_id: str, minutes: int) -> None:
        await self.send_command(player_id, ["sleep", str(minutes * 60)])

    async def playlist_clear(self, player_id: str) -> None:
        await self.send_command(player_id, ["playlist", "clear"])

    async def playlist_add_random_songs(self, player_id: str, count: int = 10) -> None:
        await self.send_command(player_id, ["randomplay", "tracks", str(count)])

    async def playlist_add_random_albums(self, player_id: str, count: int = 5) -> None:
        await self.send_command(player_id, ["randomplay", "albums", str(count)])

    async def set_repeat(self, player_id: str, value: str) -> None:
        await self.send_command(player_id, ["playlist", "repeat", value])

    async def set_shuffle(self, player_id: str, value: str) -> None:
        await self.send_command(player_id, ["playlist", "shuffle", value])

    async def play_item(self, player_id: str, item_id: str) -> None:
        await self.send_command(
            player_id, ["playlistcontrol", "cmd:load", f"track_id:{item_id}"]
        )

    async def play_album(self, player_id: str, album_id: str) -> None:
        await self.send_command(
            player_id, ["playlistcontrol", "cmd:load", f"album_id:{album_id}"]
        )

    async def play_artist(self, player_id: str, artist_id: str) -> None:
        await self.send_command(
            player_id, ["playlistcontrol", "cmd:load", f"artist_id:{artist_id}"]
        )

    async def play_genre(self, player_id: str, genre_id: str) -> None:
        await self.send_command(
            player_id, ["playlistcontrol", "cmd:load", f"genre_id:{genre_id}"]
        )

    async def play_playlist(self, player_id: str, playlist_id: str) -> None:
        await self.send_command(
            player_id,
            ["playlistcontrol", "cmd:load", f"playlist_id:{playlist_id}"],
        )

    # --- Library browsing ---

    async def get_artists(self, start: int = 0, limit: int = 50) -> dict[str, Any]:
        result = await self.send_command(
            "", ["artists", str(start), str(limit)]
        )
        return result.get("result", {})

    async def get_albums(
        self, start: int = 0, limit: int = 50, artist_id: str | None = None,
        genre_id: str | None = None,
    ) -> dict[str, Any]:
        cmd: list = ["albums", str(start), str(limit), "tags:aljy"]
        if artist_id:
            cmd.append(f"artist_id:{artist_id}")
        if genre_id:
            cmd.append(f"genre_id:{genre_id}")
        result = await self.send_command("", cmd)
        return result.get("result", {})

    async def get_tracks(
        self, start: int = 0, limit: int = 50, album_id: str | None = None,
        artist_id: str | None = None, genre_id: str | None = None,
        playlist_id: str | None = None,
    ) -> dict[str, Any]:
        cmd: list = ["titles", str(start), str(limit), "tags:adltcK"]
        if album_id:
            cmd.append(f"album_id:{album_id}")
        if artist_id:
            cmd.append(f"artist_id:{artist_id}")
        if genre_id:
            cmd.append(f"genre_id:{genre_id}")
        result = await self.send_command("", cmd)
        return result.get("result", {})

    async def get_genres(self, start: int = 0, limit: int = 50) -> dict[str, Any]:
        result = await self.send_command("", ["genres", str(start), str(limit)])
        return result.get("result", {})

    async def get_playlists(self, start: int = 0, limit: int = 50) -> dict[str, Any]:
        result = await self.send_command(
            "", ["playlists", str(start), str(limit)]
        )
        return result.get("result", {})

    async def get_playlist_tracks(
        self, playlist_id: str, start: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        result = await self.send_command(
            "",
            ["playlists", "tracks", str(start), str(limit),
             f"playlist_id:{playlist_id}", "tags:adltcK"],
        )
        return result.get("result", {})

    async def search(self, query: str, start: int = 0, limit: int = 50) -> dict[str, Any]:
        result = await self.send_command(
            "", ["search", str(start), str(limit), f"term:{query}"]
        )
        return result.get("result", {})

    # --- Artwork ---

    def get_artwork_url(
        self, player_id: str, coverid: str | None = None, artwork_url: str | None = None
    ) -> str:
        if artwork_url:
            if artwork_url.startswith("http"):
                return artwork_url
            return f"{self._base_url}{artwork_url}"
        if coverid:
            return f"{self._base_url}/music/{coverid}/cover.jpg"
        return f"{self._base_url}/music/current/cover.jpg?player={player_id}"

    def get_album_artwork_url(self, artwork_track_id: str | None = None) -> str:
        if artwork_track_id:
            return f"{self._base_url}/music/{artwork_track_id}/cover.jpg"
        return ""
