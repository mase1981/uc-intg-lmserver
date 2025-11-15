"""
Main driver for LMS integration.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

import ucapi
from ucapi import (
    AbortDriverSetup,
    DeviceStates,
    DriverSetupRequest,
    Events,
    IntegrationAPI,
    UserDataResponse,
    SetupError,
)
from ucapi.api_definitions import SetupAction, SetupComplete

from uc_intg_lmserver.config import LMSConfig
from uc_intg_lmserver.lms_client import LMSClient
from uc_intg_lmserver.lms_media_player import LMSMediaPlayer
from uc_intg_lmserver.lms_remote import LMSRemote
from uc_intg_lmserver.setup_flow import SetupFlow

_LOG = logging.getLogger(__name__)

api: IntegrationAPI | None = None
config: LMSConfig | None = None
client: LMSClient | None = None
media_players: dict[str, LMSMediaPlayer] = {}
remotes: dict[str, LMSRemote] = {}
entities_ready: bool = False
initialization_lock = asyncio.Lock()
setup_flow: SetupFlow | None = None


async def setup_handler(msg: ucapi.SetupDriver) -> ucapi.SetupAction:
    """Handle setup flow."""
    global setup_flow

    if isinstance(msg, DriverSetupRequest):
        if not setup_flow:
            setup_flow = SetupFlow(config)
        return await setup_flow.handle_setup(msg)

    elif isinstance(msg, UserDataResponse):
        if setup_flow:
            action = await setup_flow.handle_user_data(msg)
            
            if isinstance(action, SetupComplete):
                _LOG.info("Setup complete - initializing entities")
                await _initialize_entities()
            
            return action
        return SetupError()

    elif isinstance(msg, AbortDriverSetup):
        _LOG.info("Setup aborted")
        if setup_flow and setup_flow._client:
            await setup_flow._client.close()
        setup_flow = None
        return SetupError()

    return SetupError()


async def _initialize_entities() -> bool:
    """
    Initialize entities for all configured players.

    :return: True if initialization successful
    """
    global media_players, remotes, entities_ready, client, api

    async with initialization_lock:
        if entities_ready:
            _LOG.debug("Entities already initialized")
            return True

        if not config.is_configured():
            _LOG.info("Integration not configured yet")
            return False

        _LOG.info("Initializing entities for configured players")
        await api.set_device_state(DeviceStates.CONNECTING)

        api.available_entities.clear()
        media_players.clear()
        remotes.clear()

        client = LMSClient(config.server_host, config.server_port)

        try:
            version = await client.get_server_version()
            _LOG.info("Connected to LMS version %s", version)

            _LOG.info("Loading favorites from LMS...")
            try:
                favorites = await client.get_favorites()
                _LOG.info("Loaded %d favorites from LMS", len(favorites))
            except Exception as e:
                _LOG.error("Failed to load favorites: %s", e)
                favorites = []

        except Exception as e:
            _LOG.error("Failed to connect to LMS during initialization: %s", e)
            await api.set_device_state(DeviceStates.ERROR)
            return False

        players_config = config.players
        _LOG.info("Creating entities for %d players", len(players_config))

        for player_config in players_config:
            if not player_config.get("enabled", True):
                _LOG.info("Skipping disabled player: %s", player_config["name"])
                continue

            player_id = player_config["player_id"]
            player_name = player_config["name"]
            player_model = player_config.get("model", "unknown")

            try:
                media_player = LMSMediaPlayer(
                    player_id=player_id,
                    player_name=player_name,
                    player_model=player_model,
                    client=client,
                )
                
                media_player._integration_api = api
                
                media_players[player_id] = media_player
                api.available_entities.add(media_player)
                api.configured_entities.add(media_player)
                _LOG.info("Added media player entity: %s", media_player.id)

                remote = LMSRemote(
                    player_id=player_id,
                    player_name=player_name,
                    client=client,
                    all_players=players_config,
                    favorites=favorites,
                )
                
                remote._integration_api = api
                
                remotes[player_id] = remote
                api.available_entities.add(remote)
                api.configured_entities.add(remote)
                _LOG.info("Added remote entity: %s with %d favorites", remote.id, len(favorites))

            except Exception as e:
                _LOG.error("Failed to create entities for player %s: %s", player_name, e, exc_info=True)
                continue

        entities_ready = True
        _LOG.info("Entity initialization complete: %d media players, %d remotes", 
                 len(media_players), len(remotes))

        await api.set_device_state(DeviceStates.CONNECTED)
        return True


async def on_connect():
    """Handle connect event."""
    global entities_ready, config
    
    _LOG.info("Remote connected")

    if config:
        config.load()

    if config and config.is_configured():
        if not entities_ready:
            _LOG.info("Initializing entities on connect")
            await _initialize_entities()
        else:
            await api.set_device_state(DeviceStates.CONNECTED)
    else:
        await api.set_device_state(DeviceStates.DISCONNECTED)


async def on_disconnect():
    """
    Handle disconnect event.
    
    CRITICAL: DO NOT close the LMS client session here!
    The client HTTP session must persist across Remote WebSocket reconnections.
    Only stop the polling loops to pause entity updates during disconnect.
    """
    _LOG.info("Remote disconnected - stopping polling loops")

    # Stop polling but keep client session alive
    for player in media_players.values():
        await player.stop_polling()

    for remote in remotes.values():
        await remote.stop_polling()

    # DO NOT close the client session - it will be reused on reconnect
    # The session is only closed during final shutdown in main()


async def on_subscribe_entities(entity_ids: list[str]):
    """
    Handle entity subscription - CRITICAL TIMING.
    
    Push initial state IMMEDIATELY before starting background monitoring.
    """
    global media_players, remotes, entities_ready, config, api
    
    _LOG.info(f"Entities subscribed: {entity_ids}. Pushing initial state.")

    if not entities_ready:
        _LOG.warning("Subscription before entities ready - attempting recovery")
        
        if config and config.is_configured():
            await _initialize_entities()
            
            if not entities_ready:
                _LOG.error("Recovery failed - entities still not ready")
                return
        else:
            _LOG.error("Cannot recover - no configuration available")
            return

    subscribed_count = 0
    for entity_id in entity_ids:
        for player in media_players.values():
            if player.id == entity_id:
                _LOG.info("Subscribing media player: %s", entity_id)
                
                await player.update_attributes()
                
                await player.start_polling()
                
                subscribed_count += 1
                break

        for remote in remotes.values():
            if remote.id == entity_id:
                _LOG.info("Subscribing remote: %s", entity_id)
                
                await remote.update_sync_status()
                
                await remote.start_polling()
                
                subscribed_count += 1
                break
    
    _LOG.info(f"Subscribed to {subscribed_count}/{len(entity_ids)} entities with initial state pushed")


async def on_unsubscribe_entities(entity_ids: list[str]):
    """
    Handle entity unsubscription.

    :param entity_ids: List of entity IDs to unsubscribe
    """
    _LOG.info(f"Unsubscribed from {len(entity_ids)} entities")

    for entity_id in entity_ids:
        for player in media_players.values():
            if player.id == entity_id:
                _LOG.info("Stopping polling for media player: %s", entity_id)
                await player.stop_polling()
                break

        for remote in remotes.values():
            if remote.id == entity_id:
                _LOG.info("Stopping polling for remote: %s", entity_id)
                await remote.stop_polling()
                break


async def main():
    """Main driver entry point."""
    global api, config, setup_flow

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    _LOG.info("Starting LMS integration driver")

    try:
        loop = asyncio.get_running_loop()
        api = IntegrationAPI(loop)

        driver_path = Path(__file__).parent.parent / "driver.json"
        
        if not driver_path.exists():
            _LOG.error(f"driver.json not found at {driver_path}")
            sys.exit(1)

        api.add_listener(Events.CONNECT, on_connect)
        api.add_listener(Events.DISCONNECT, on_disconnect)
        api.add_listener(Events.SUBSCRIBE_ENTITIES, on_subscribe_entities)
        api.add_listener(Events.UNSUBSCRIBE_ENTITIES, on_unsubscribe_entities)

        config = LMSConfig()

        await api.init(str(driver_path.resolve()), setup_handler)

        config._data_path = Path(api.config_dir_path)
        config._config_file = config._data_path / "config.json"
        
        try:
            config._data_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        config.load()

        if config.is_configured():
            _LOG.info("Found existing configuration, pre-initializing entities")
            asyncio.create_task(_initialize_entities())
        else:
            await api.set_device_state(DeviceStates.DISCONNECTED)

        _LOG.info("Driver initialization complete, waiting for connections...")
        
        await asyncio.Event().wait()

    except KeyboardInterrupt:
        _LOG.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        _LOG.error(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        _LOG.info("Shutting down...")
        # Close client session only during final shutdown
        if client:
            await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass