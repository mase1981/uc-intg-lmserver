"""
LMS JSON-RPC client for communication with Lyrion Music Server.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import base64
import logging
from typing import Any

import aiohttp

_LOG = logging.getLogger(__name__)


class LMSClient:
    """Client for communicating with Lyrion Music Server via JSON-RPC."""

    def __init__(self, host: str, port: int = 9000):
        self._host = host
        self._port = port
        self._base_url = f"http://{host}:{port}"
        self._jsonrpc_url = f"{self._base_url}/jsonrpc.js"
        self._session: aiohttp.ClientSession | None = None
        self._request_id = 0

    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_request_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    async def send_command(self, player_id: str, command: list[str]) -> dict[str, Any]:
        """
        Send JSON-RPC command to LMS.

        :param player_id: Player MAC address or "" for server commands
        :param command: List of command parameters
        :return: Parsed JSON response
        :raises: aiohttp.ClientError on connection failure
        """
        await self._ensure_session()

        payload = {
            "id": self._get_request_id(),
            "method": "slim.request",
            "params": [player_id, command]
        }

        _LOG.debug("Sending command to LMS: player=%s, command=%s", player_id, command)

        try:
            async with self._session.post(
                self._jsonrpc_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                _LOG.debug("Received response from LMS: %s", data)
                return data

        except aiohttp.ClientError as e:
            _LOG.error("Failed to communicate with LMS: %s", e)
            raise

    async def get_server_version(self) -> str:
        """
        Get LMS server version.

        :return: Server version string
        """
        result = await self.send_command("", ["version", "?"])
        return result.get("result", {}).get("_version", "Unknown")

    async def get_server_status(self) -> dict[str, Any]:
        """
        Get LMS server status.

        :return: Server status information
        """
        result = await self.send_command("", ["serverstatus", "0", "100"])
        return result.get("result", {})

    async def get_players(self) -> list[dict[str, Any]]:
        """
        Discover all players connected to LMS.

        :return: List of player dictionaries with id, name, model, ip, connected
        """
        result = await self.send_command("", ["players", "0", "999"])
        players_data = result.get("result", {}).get("players_loop", [])
        
        players = []
        for player in players_data:
            players.append({
                "playerid": player.get("playerid", ""),
                "name": player.get("name", "Unknown Player"),
                "model": player.get("model", "unknown"),
                "modelname": player.get("modelname", "Unknown Model"),
                "ip": player.get("ip", ""),
                "connected": player.get("connected", 0)
            })
        
        _LOG.info("Discovered %d players on LMS", len(players))
        return players

    async def get_player_status(self, player_id: str) -> dict[str, Any]:
        """
        Get comprehensive player status with metadata.

        :param player_id: Player MAC address
        :return: Player status dictionary
        """
        # Tags: A=artist (uppercase!), l=album, t=title, d=duration, c=coverid, K=artwork_url
        result = await self.send_command(
            player_id, 
            ["status", "-", "1", "tags:Aaltdc"]
        )
        
        response = result.get("result", {})
        
        if "playlist_loop" in response and response["playlist_loop"]:
            track = response["playlist_loop"][0]
            _LOG.info("Track metadata - Title: %s, Artist: %s, Album: %s, CoverID: %s", 
                     track.get("title"), track.get("artist"), 
                     track.get("album"), track.get("coverid"))
        
        return response

    def get_artwork_url(self, player_id: str, coverid: str = None) -> str:
        """
        Get URL for track artwork.

        :param player_id: Player MAC address
        :param coverid: Optional cover ID from track metadata
        :return: Artwork URL or empty string
        """
        if coverid:
            return f"{self._base_url}/music/{coverid}/cover.jpg"
        else:
            return f"{self._base_url}/music/current/cover.jpg?player={player_id}"

    async def fetch_artwork_as_base64(self, player_id: str, coverid: str = None) -> str:
        """
        Fetch track artwork and convert to base64 data URL.

        :param player_id: Player MAC address
        :param coverid: Optional cover ID from track metadata
        :return: Base64 data URL or empty string
        """
        await self._ensure_session()
        artwork_url = self.get_artwork_url(player_id, coverid)
        
        _LOG.debug("Fetching artwork from: %s", artwork_url)

        try:
            async with self._session.get(
                artwork_url,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    image_data = await response.read()
                    content_type = response.headers.get("Content-Type", "image/jpeg")
                    
                    b64_data = base64.b64encode(image_data).decode("utf-8")
                    data_url = f"data:{content_type};base64,{b64_data}"
                    _LOG.debug("Successfully fetched artwork, size: %d bytes", len(image_data))
                    return data_url
                else:
                    _LOG.debug("Artwork not available: HTTP %d", response.status)
                    return ""

        except Exception as e:
            _LOG.debug("Failed to fetch artwork: %s", e)
            return ""

    async def play(self, player_id: str):
        """Start playback."""
        await self.send_command(player_id, ["play"])

    async def pause(self, player_id: str):
        """Pause playback."""
        await self.send_command(player_id, ["pause", "1"])

    async def stop(self, player_id: str):
        """Stop playback."""
        await self.send_command(player_id, ["stop"])

    async def toggle_play_pause(self, player_id: str):
        """Toggle between play and pause."""
        await self.send_command(player_id, ["pause"])

    async def next_track(self, player_id: str):
        """Skip to next track."""
        await self.send_command(player_id, ["playlist", "index", "+1"])

    async def previous_track(self, player_id: str):
        """Go to previous track."""
        await self.send_command(player_id, ["playlist", "index", "-1"])

    async def set_volume(self, player_id: str, volume: int):
        """
        Set volume (0-100).

        :param player_id: Player MAC address
        :param volume: Volume level 0-100
        """
        volume = max(0, min(100, volume))
        await self.send_command(player_id, ["mixer", "volume", str(volume)])

    async def volume_up(self, player_id: str, step: int = 5):
        """Increase volume."""
        await self.send_command(player_id, ["mixer", "volume", f"+{step}"])

    async def volume_down(self, player_id: str, step: int = 5):
        """Decrease volume."""
        await self.send_command(player_id, ["mixer", "volume", f"-{step}"])

    async def mute(self, player_id: str):
        """Mute player."""
        await self.send_command(player_id, ["mixer", "muting", "1"])

    async def unmute(self, player_id: str):
        """Unmute player."""
        await self.send_command(player_id, ["mixer", "muting", "0"])

    async def toggle_mute(self, player_id: str):
        """Toggle mute state."""
        await self.send_command(player_id, ["mixer", "muting", "toggle"])

    async def seek(self, player_id: str, position: int):
        """Seek to position in seconds."""
        await self.send_command(player_id, ["time", str(position)])

    async def sync_players(self, player_id: str, target_player_id: str):
        """Sync player to another player's group."""
        _LOG.info("Syncing player %s with %s", player_id, target_player_id)
        await self.send_command(player_id, ["sync", target_player_id])

    async def unsync_player(self, player_id: str):
        """Remove player from sync group."""
        _LOG.info("Unsyncing player %s", player_id)
        await self.send_command(player_id, ["sync", "-"])

    async def get_sync_groups(self) -> dict[str, Any]:
        """Get all sync groups and their members."""
        result = await self.send_command("", ["syncgroups", "?"])
        return result.get("result", {})

    async def power_on(self, player_id: str):
        """Power on player."""
        await self.send_command(player_id, ["power", "1"])

    async def power_off(self, player_id: str):
        """Power off player."""
        await self.send_command(player_id, ["power", "0"])

    async def toggle_power(self, player_id: str):
        """Toggle power state."""
        await self.send_command(player_id, ["power"])

    async def play_favorite(self, player_id: str, favorite_id: str):
        """
        Play a favorite by ID.
        
        :param player_id: Player MAC address
        :param favorite_id: Favorite hierarchical ID (e.g., "ecd2e8b9.0" or "1.1")
        """
        await self.send_command(player_id, ["favorites", "playlist", "play", f"item_id:{favorite_id}"])

    async def get_favorites(self) -> list[dict[str, Any]]:
        """Get list of favorites."""
        result = await self.send_command("", ["favorites", "items", "0", "100"])
        return result.get("result", {}).get("loop_loop", [])

    async def set_sleep_timer(self, player_id: str, minutes: int):
        """Set sleep timer."""
        seconds = minutes * 60
        await self.send_command(player_id, ["sleep", str(seconds)])

    async def playlist_clear(self, player_id: str):
        """Clear current playlist."""
        await self.send_command(player_id, ["playlist", "clear"])

    async def playlist_add_random_songs(self, player_id: str, count: int = 10):
        """Add random songs to playlist."""
        await self.send_command(player_id, ["randomplay", "tracks", str(count)])

    async def playlist_add_random_albums(self, player_id: str, count: int = 5):
        """Add random albums to playlist."""
        await self.send_command(player_id, ["randomplay", "albums", str(count)])