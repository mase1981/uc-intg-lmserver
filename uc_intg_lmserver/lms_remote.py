"""
Remote entity for LMS player grouping/synchronization.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any

from ucapi import EntityTypes, StatusCodes
from ucapi.remote import Attributes, Commands, Features, Remote, States

from uc_intg_lmserver.lms_client import LMSClient

_LOG = logging.getLogger(__name__)


class LMSRemote(Remote):
    """Remote entity for LMS player synchronization control."""

    def __init__(
        self,
        player_id: str,
        player_name: str,
        client: LMSClient,
        all_players: list[dict[str, Any]],
        favorites: list[dict[str, Any]] = None,
    ):
        self._player_id = player_id
        self._player_name = player_name
        self._client = client
        self._all_players = all_players
        self._integration_api = None
        self._polling_task: asyncio.Task | None = None
        self._polling_active = False
        self._sync_group_members: list[str] = []
        
        self._favorites = favorites if favorites is not None else []
        
        _LOG.info("Creating remote for %s with %d players and %d favorites", 
                 player_name, len(all_players), len(self._favorites))

        entity_id = self._sanitize_name(player_name)

        features = [
            Features.ON_OFF,
            Features.TOGGLE,
            Features.SEND_CMD,
        ]

        attributes = {
            Attributes.STATE: States.UNKNOWN,
        }

        super().__init__(
            identifier=entity_id,
            name=f"{player_name} Control",
            features=features,
            attributes=attributes,
            simple_commands=[],
            button_mapping=[],
            ui_pages=[],
            area=None,
        )

        all_pages = self._create_all_pages()
        
        _LOG.info("Created %d UI pages for %s: %s", 
                 len(all_pages), player_name, [p['name'] for p in all_pages])

        self.options = {
            "simple_commands": self._build_all_commands(),
            "button_mapping": self._create_button_mapping(),
            "user_interface": {"pages": all_pages}
        }

        _LOG.info("Created remote entity: %s (ID: %s) with %d commands and %d favorites", 
                 f"{player_name} Control", entity_id, 
                 len(self.options["simple_commands"]), len(self._favorites))

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert player name to valid entity ID."""
        sanitized = name.lower()
        sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
        sanitized = "_".join(filter(None, sanitized.split("_")))
        return f"remote.{sanitized}_control"

    def _build_all_commands(self) -> list[str]:
        """Build complete command list including favorites and sync."""
        commands = [
            "play", "pause", "stop", "next", "previous", 
            "play_pause", "volume_up", "volume_down", "mute_toggle",
            
            "UNSYNC",
            
            "sleep_15", "sleep_30", "sleep_60", "sleep_90", "sleep_cancel",
            
            "playlist_clear", "playlist_add_10_songs", "playlist_add_5_albums",
            
            "power_on", "power_off", "power_toggle",
            
            "favorite_1", "favorite_2", "favorite_3", "favorite_4", "favorite_5",
            "favorite_6", "favorite_7", "favorite_8", "favorite_9", "favorite_10",
            "favorite_11", "favorite_12", "favorite_13", "favorite_14", "favorite_15",
            "favorite_16", "favorite_17", "favorite_18", "favorite_19", "favorite_20",
        ]
        
        for player in self._all_players:
            if player["player_id"] != self._player_id:
                player_cmd = self._sanitize_player_name(player["name"])
                sync_cmd = f"SYNC_{player_cmd}"
                commands.append(sync_cmd)
                _LOG.debug("Added sync command: %s", sync_cmd)
        
        return commands

    @staticmethod
    def _sanitize_player_name(name: str) -> str:
        """Sanitize player name for command identifier."""
        sanitized = name.lower()
        sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
        sanitized = "_".join(filter(None, sanitized.split("_")))
        return sanitized

    def _get_player_id_by_name(self, name: str) -> str | None:
        """Get player ID by sanitized name."""
        for player in self._all_players:
            if self._sanitize_player_name(player["name"]) == name:
                return player["player_id"]
        return None

    def _create_button_mapping(self) -> list[dict]:
        """Create physical button mappings for Remote Two/3."""
        mappings = [
            {
                'button': 'PLAY',
                'short_press': {'cmd_id': 'send_cmd', 'params': {'command': 'play_pause'}},
                'long_press': None
            },
            {
                'button': 'PREV',
                'short_press': {'cmd_id': 'send_cmd', 'params': {'command': 'previous'}},
                'long_press': None
            },
            {
                'button': 'NEXT',
                'short_press': {'cmd_id': 'send_cmd', 'params': {'command': 'next'}},
                'long_press': None
            },
            
            {
                'button': 'VOLUME_UP',
                'short_press': {'cmd_id': 'send_cmd', 'params': {'command': 'volume_up'}},
                'long_press': None
            },
            {
                'button': 'VOLUME_DOWN',
                'short_press': {'cmd_id': 'send_cmd', 'params': {'command': 'volume_down'}},
                'long_press': None
            },
            {
                'button': 'MUTE',
                'short_press': {'cmd_id': 'send_cmd', 'params': {'command': 'mute_toggle'}},
                'long_press': None
            },
            
            {
                'button': 'POWER',
                'short_press': {'cmd_id': 'send_cmd', 'params': {'command': 'power_toggle'}},
                'long_press': {'cmd_id': 'send_cmd', 'params': {'command': 'power_off'}}
            },
            
            {
                'button': 'CHANNEL_UP',
                'short_press': {'cmd_id': 'send_cmd', 'params': {'command': 'favorite_1'}},
                'long_press': None
            },
            {
                'button': 'CHANNEL_DOWN',
                'short_press': {'cmd_id': 'send_cmd', 'params': {'command': 'favorite_2'}},
                'long_press': None
            },
        ]
        
        return mappings

    def _create_all_pages(self) -> list[dict[str, Any]]:
        """Create ALL UI pages including sync and favorites."""
        pages = [
            self._create_main_page(),
        ]
        
        if len(self._all_players) > 1:
            sync_page = self._create_sync_page()
            if sync_page:
                pages.append(sync_page)
                _LOG.info("Added sync page with %d items", len(sync_page['items']))
        
        if self._favorites:
            fav_page = self._create_favorites_page()
            if fav_page:
                pages.append(fav_page)
                _LOG.info("Added favorites page with %d items", len(fav_page['items']))
        
        pages.append(self._create_playlist_page())
        
        return pages

    def _create_main_page(self) -> dict[str, Any]:
        """Create main control page."""
        return {
            'page_id': 'main',
            'name': 'Playback',
            'grid': {'width': 4, 'height': 6},
            'items': [
                {'type': 'text', 'location': {'x': 0, 'y': 0}, 'text': 'PREV',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'previous'}}},
                {'type': 'text', 'location': {'x': 1, 'y': 0}, 'text': 'PLAY',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'play'}}},
                {'type': 'text', 'location': {'x': 2, 'y': 0}, 'text': 'PAUSE',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'pause'}}},
                {'type': 'text', 'location': {'x': 3, 'y': 0}, 'text': 'NEXT',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'next'}}},
                
                {'type': 'text', 'location': {'x': 0, 'y': 1}, 'text': 'VOL-',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'volume_down'}}},
                {'type': 'text', 'location': {'x': 1, 'y': 1}, 'text': 'VOL+',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'volume_up'}}},
                {'type': 'text', 'location': {'x': 2, 'y': 1}, 'text': 'MUTE',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'mute_toggle'}}},
                {'type': 'text', 'location': {'x': 3, 'y': 1}, 'text': 'STOP',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'stop'}}},
                
                {'type': 'text', 'location': {'x': 0, 'y': 2}, 'text': 'ON',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'power_on'}}},
                {'type': 'text', 'location': {'x': 1, 'y': 2}, 'text': 'OFF',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'power_off'}}},
                
                {'type': 'text', 'location': {'x': 0, 'y': 3}, 'text': 'Sleep 15',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'sleep_15'}}},
                {'type': 'text', 'location': {'x': 1, 'y': 3}, 'text': 'Sleep 30',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'sleep_30'}}},
                {'type': 'text', 'location': {'x': 2, 'y': 3}, 'text': 'Sleep 60',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'sleep_60'}}},
                {'type': 'text', 'location': {'x': 3, 'y': 3}, 'text': 'Cancel',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'sleep_cancel'}}},
            ]
        }

    def _create_sync_page(self) -> dict[str, Any]:
        """Create player sync/grouping page."""
        page = {
            'page_id': 'sync',
            'name': 'Group Players',
            'grid': {'width': 4, 'height': 6},
            'items': [
                {'type': 'text', 'location': {'x': 0, 'y': 0}, 'text': 'UNGROUP',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'UNSYNC'}}},
            ]
        }
        
        row, col = 0, 1
        sync_button_count = 0
        
        for player in self._all_players:
            if player["player_id"] != self._player_id:
                if col >= 4:
                    col = 0
                    row += 1
                if row >= 6:
                    break
                
                player_cmd = self._sanitize_player_name(player["name"])
                sync_cmd = f"SYNC_{player_cmd}"
                label = f"→{player['name'][:8]}"
                
                page['items'].append({
                    'type': 'text',
                    'location': {'x': col, 'y': row},
                    'text': label,
                    'command': {'cmd_id': 'send_cmd', 'params': {'command': sync_cmd}}
                })
                
                _LOG.debug("Added sync button: %s at (%d,%d)", label, col, row)
                sync_button_count += 1
                col += 1
        
        return page if sync_button_count > 0 else None

    def _create_favorites_page(self) -> dict[str, Any]:
        """Create favorites page with real favorites."""
        page = {
            'page_id': 'favorites',
            'name': 'Favorites',
            'grid': {'width': 4, 'height': 6},
            'items': []
        }
        
        if not self._favorites:
            return None
        
        row, col = 0, 0
        for i, fav in enumerate(self._favorites[:24], 1):
            if row >= 6:
                break
            
            name = fav.get('name', f'Fav {i}')
            display_name = name[:10] if len(name) > 10 else name
            
            page['items'].append({
                'type': 'text',
                'location': {'x': col, 'y': row},
                'text': display_name,
                'command': {'cmd_id': 'send_cmd', 'params': {'command': f'favorite_{i}'}}
            })
            
            _LOG.debug("Added favorite button: %s -> favorite_%d", display_name, i)
            
            col += 1
            if col >= 4:
                col = 0
                row += 1
        
        return page if page['items'] else None

    def _create_playlist_page(self) -> dict[str, Any]:
        """Create playlist management page."""
        return {
            'page_id': 'playlist',
            'name': 'Playlist',
            'grid': {'width': 4, 'height': 6},
            'items': [
                {'type': 'text', 'location': {'x': 0, 'y': 0}, 'text': 'Clear',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'playlist_clear'}}},
                {'type': 'text', 'location': {'x': 1, 'y': 0}, 'text': '+10 Songs',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'playlist_add_10_songs'}}},
                {'type': 'text', 'location': {'x': 2, 'y': 0}, 'text': '+5 Albums',
                 'command': {'cmd_id': 'send_cmd', 'params': {'command': 'playlist_add_5_albums'}}},
            ]
        }

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
        """Handle remote commands."""
        _LOG.info("Remote command: %s with params: %s", cmd_id, params)

        try:
            if cmd_id == Commands.ON:
                await self._client.power_on(self._player_id)
                return StatusCodes.OK
            elif cmd_id == Commands.OFF:
                await self._client.power_off(self._player_id)
                return StatusCodes.OK
            elif cmd_id == Commands.TOGGLE:
                await self._client.toggle_power(self._player_id)
                return StatusCodes.OK
            elif cmd_id == Commands.SEND_CMD:
                if params and "command" in params:
                    return await self._handle_send_command(params["command"])
                return StatusCodes.BAD_REQUEST
            else:
                return StatusCodes.NOT_IMPLEMENTED

        except Exception as e:
            _LOG.error("Error executing remote command %s: %s", cmd_id, e, exc_info=True)
            return StatusCodes.SERVER_ERROR

    async def _handle_send_command(self, command: str) -> StatusCodes:
        """Handle send_cmd commands."""
        _LOG.info("Executing send_cmd: %s for player %s", command, self._player_id)
        
        if command == "play":
            await self._client.play(self._player_id)
        elif command == "pause":
            await self._client.pause(self._player_id)
        elif command == "stop":
            await self._client.stop(self._player_id)
        elif command == "play_pause":
            await self._client.toggle_play_pause(self._player_id)
        elif command == "next":
            await self._client.next_track(self._player_id)
        elif command == "previous":
            await self._client.previous_track(self._player_id)
        elif command == "volume_up":
            await self._client.volume_up(self._player_id)
        elif command == "volume_down":
            await self._client.volume_down(self._player_id)
        elif command == "mute_toggle":
            await self._client.toggle_mute(self._player_id)
        
        elif command == "UNSYNC":
            _LOG.info("UNGROUP: Unsyncing player %s", self._player_id)
            await self._client.unsync_player(self._player_id)
        elif command.startswith("SYNC_"):
            target_name = command.replace("SYNC_", "")
            target_id = self._get_player_id_by_name(target_name)
            if target_id:
                _LOG.info("GROUP: Syncing %s with %s", self._player_id, target_id)
                await self._client.sync_players(self._player_id, target_id)
            else:
                _LOG.error("Target player not found: %s", target_name)
                return StatusCodes.NOT_FOUND
        
        elif command.startswith("favorite_"):
            try:
                fav_num = int(command.split("_")[1]) - 1
                
                if 0 <= fav_num < len(self._favorites):
                    fav = self._favorites[fav_num]
                    fav_id = fav.get("id", "")
                    fav_name = fav.get("name", f"Favorite {fav_num + 1}")
                    
                    if fav_id:
                        _LOG.info("Playing favorite: %s (ID: %s)", fav_name, fav_id)
                        await self._client.play_favorite(self._player_id, fav_id)
                        return StatusCodes.OK
                    else:
                        _LOG.error("Favorite %d has no ID", fav_num + 1)
                        return StatusCodes.NOT_FOUND
                else:
                    _LOG.warning("Favorite %d not found (have %d favorites)", 
                               fav_num + 1, len(self._favorites))
                    return StatusCodes.NOT_FOUND
            except (ValueError, IndexError) as e:
                _LOG.error("Invalid favorite command format: %s - %s", command, e)
                return StatusCodes.BAD_REQUEST
        
        elif command == "sleep_cancel":
            await self._client.set_sleep_timer(self._player_id, 0)
        elif command.startswith("sleep_"):
            try:
                minutes = int(command.split("_")[1])
                await self._client.set_sleep_timer(self._player_id, minutes)
            except (ValueError, IndexError) as e:
                _LOG.error("Invalid sleep timer command: %s - %s", command, e)
                return StatusCodes.BAD_REQUEST
        
        elif command == "playlist_clear":
            await self._client.playlist_clear(self._player_id)
        elif command == "playlist_add_10_songs":
            await self._client.playlist_add_random_songs(self._player_id, 10)
        elif command == "playlist_add_5_albums":
            await self._client.playlist_add_random_albums(self._player_id, 5)
        
        elif command == "power_on":
            await self._client.power_on(self._player_id)
        elif command == "power_off":
            await self._client.power_off(self._player_id)
        elif command == "power_toggle":
            await self._client.toggle_power(self._player_id)
        
        else:
            _LOG.warning("Unknown command: %s", command)
            return StatusCodes.NOT_IMPLEMENTED
        
        return StatusCodes.OK

    async def start_polling(self):
        """Start polling loop."""
        if self._polling_active:
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
                pass
            self._polling_task = None
        _LOG.info("Stopped polling for %s", self.id)

    async def _polling_loop(self):
        """Polling loop for status updates."""
        while self._polling_active:
            try:
                await self.update_sync_status()
                await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOG.error("Polling error for %s: %s", self.id, e, exc_info=True)
                await asyncio.sleep(10)

    async def update_sync_status(self):
        """Update sync group status."""
        try:
            status = await self._client.get_player_status(self._player_id)
            
            power = status.get("power", 0)
            self.attributes[Attributes.STATE] = States.ON if power == 1 else States.OFF
            
            sync_master = status.get("sync_master")
            sync_slaves = status.get("sync_slaves", "")
            
            if sync_master or sync_slaves:
                self._sync_group_members = sync_slaves.split(",") if sync_slaves else []
                _LOG.debug("Player %s is synced with: %s", self._player_id, self._sync_group_members)
            else:
                self._sync_group_members = []

            self._force_integration_update()

        except Exception as e:
            _LOG.error("Failed to update status for %s: %s", self.id, e, exc_info=True)
            self.attributes[Attributes.STATE] = States.UNAVAILABLE
            self._force_integration_update()

    @property
    def player_id(self) -> str:
        """Get LMS player ID (MAC address)."""
        return self._player_id

    def update_available_players(self, players: list[dict[str, Any]]):
        """Update list of available players for syncing."""
        self._all_players = players
        if hasattr(self, 'options') and self.options:
            self.options["simple_commands"] = self._build_all_commands()