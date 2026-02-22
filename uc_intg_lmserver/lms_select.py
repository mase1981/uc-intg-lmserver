"""
LMS Select entities for player settings.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import logging
from typing import Any

from ucapi import StatusCodes
from ucapi.select import Attributes, Commands, Select, States

from uc_intg_lmserver.lms_client import LMSClient

_LOG = logging.getLogger(__name__)


class LMSRepeatModeSelect(Select):
    """Select entity for repeat mode."""

    REPEAT_OPTIONS = ["Off", "One", "All"]

    OPTION_TO_LMS = {"Off": "0", "One": "1", "All": "2"}
    LMS_TO_OPTION = {"0": "Off", "1": "One", "2": "All"}

    def __init__(self, player_id: str, player_name: str, client: LMSClient):
        self._player_id = player_id
        self._player_name = player_name
        self._client = client
        self._integration_api = None

        sanitized = self._sanitize_name(player_name)
        entity_id = f"select.{sanitized}_repeat_mode"

        attributes = {
            Attributes.STATE: States.UNKNOWN,
            Attributes.OPTIONS: self.REPEAT_OPTIONS,
            Attributes.CURRENT_OPTION: "Off",
        }

        super().__init__(
            identifier=entity_id,
            name=f"{player_name} Repeat Mode",
            attributes=attributes,
            cmd_handler=self.handle_command,
        )

        _LOG.info("Created repeat mode select: %s", entity_id)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert player name to valid entity ID component."""
        sanitized = name.lower()
        sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
        return "_".join(filter(None, sanitized.split("_")))

    async def handle_command(
        self,
        entity: Select,
        cmd_id: str,
        params: dict[str, Any] | None = None,
    ) -> StatusCodes:
        """Handle select commands."""
        _LOG.info("Repeat mode select command: %s, params: %s", cmd_id, params)

        try:
            if cmd_id == Commands.SELECT_OPTION:
                option = params.get("option") if params else None
                if option in self.REPEAT_OPTIONS:
                    lms_value = self.OPTION_TO_LMS[option]
                    await self._client.send_command(
                        self._player_id, ["playlist", "repeat", lms_value]
                    )
                    self.attributes[Attributes.CURRENT_OPTION] = option
                    self.attributes[Attributes.STATE] = States.ON
                    self._force_integration_update()
                    return StatusCodes.OK
                return StatusCodes.BAD_REQUEST

            elif cmd_id == Commands.SELECT_NEXT:
                return await self._select_relative(1)

            elif cmd_id == Commands.SELECT_PREVIOUS:
                return await self._select_relative(-1)

            else:
                return StatusCodes.NOT_IMPLEMENTED

        except Exception as e:
            _LOG.error("Error executing command %s: %s", cmd_id, e, exc_info=True)
            return StatusCodes.SERVER_ERROR

    async def _select_relative(self, direction: int) -> StatusCodes:
        """Select next or previous option."""
        current = self.attributes[Attributes.CURRENT_OPTION]
        try:
            idx = self.REPEAT_OPTIONS.index(current)
            new_idx = (idx + direction) % len(self.REPEAT_OPTIONS)
            return await self.handle_command(
                self, Commands.SELECT_OPTION, {"option": self.REPEAT_OPTIONS[new_idx]}
            )
        except (ValueError, IndexError):
            return StatusCodes.SERVER_ERROR

    def update_from_status(self, status: dict[str, Any]) -> None:
        """Update select from player status."""
        repeat_mode = str(status.get("playlist repeat", 0))
        self.attributes[Attributes.CURRENT_OPTION] = self.LMS_TO_OPTION.get(
            repeat_mode, "Off"
        )
        self.attributes[Attributes.STATE] = States.ON
        self._force_integration_update()

    def _force_integration_update(self) -> None:
        """Force update to integration API."""
        if self._integration_api and hasattr(self._integration_api, "configured_entities"):
            try:
                self._integration_api.configured_entities.update_attributes(
                    self.id, self.attributes
                )
            except Exception as e:
                _LOG.debug("Could not update integration API for %s: %s", self.id, e)


class LMSShuffleModeSelect(Select):
    """Select entity for shuffle mode."""

    SHUFFLE_OPTIONS = ["Off", "Songs", "Albums"]

    OPTION_TO_LMS = {"Off": "0", "Songs": "1", "Albums": "2"}
    LMS_TO_OPTION = {"0": "Off", "1": "Songs", "2": "Albums"}

    def __init__(self, player_id: str, player_name: str, client: LMSClient):
        self._player_id = player_id
        self._player_name = player_name
        self._client = client
        self._integration_api = None

        sanitized = self._sanitize_name(player_name)
        entity_id = f"select.{sanitized}_shuffle_mode"

        attributes = {
            Attributes.STATE: States.UNKNOWN,
            Attributes.OPTIONS: self.SHUFFLE_OPTIONS,
            Attributes.CURRENT_OPTION: "Off",
        }

        super().__init__(
            identifier=entity_id,
            name=f"{player_name} Shuffle Mode",
            attributes=attributes,
            cmd_handler=self.handle_command,
        )

        _LOG.info("Created shuffle mode select: %s", entity_id)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert player name to valid entity ID component."""
        sanitized = name.lower()
        sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
        return "_".join(filter(None, sanitized.split("_")))

    async def handle_command(
        self,
        entity: Select,
        cmd_id: str,
        params: dict[str, Any] | None = None,
    ) -> StatusCodes:
        """Handle select commands."""
        _LOG.info("Shuffle mode select command: %s, params: %s", cmd_id, params)

        try:
            if cmd_id == Commands.SELECT_OPTION:
                option = params.get("option") if params else None
                if option in self.SHUFFLE_OPTIONS:
                    lms_value = self.OPTION_TO_LMS[option]
                    await self._client.send_command(
                        self._player_id, ["playlist", "shuffle", lms_value]
                    )
                    self.attributes[Attributes.CURRENT_OPTION] = option
                    self.attributes[Attributes.STATE] = States.ON
                    self._force_integration_update()
                    return StatusCodes.OK
                return StatusCodes.BAD_REQUEST

            elif cmd_id == Commands.SELECT_NEXT:
                return await self._select_relative(1)

            elif cmd_id == Commands.SELECT_PREVIOUS:
                return await self._select_relative(-1)

            else:
                return StatusCodes.NOT_IMPLEMENTED

        except Exception as e:
            _LOG.error("Error executing command %s: %s", cmd_id, e, exc_info=True)
            return StatusCodes.SERVER_ERROR

    async def _select_relative(self, direction: int) -> StatusCodes:
        """Select next or previous option."""
        current = self.attributes[Attributes.CURRENT_OPTION]
        try:
            idx = self.SHUFFLE_OPTIONS.index(current)
            new_idx = (idx + direction) % len(self.SHUFFLE_OPTIONS)
            return await self.handle_command(
                self, Commands.SELECT_OPTION, {"option": self.SHUFFLE_OPTIONS[new_idx]}
            )
        except (ValueError, IndexError):
            return StatusCodes.SERVER_ERROR

    def update_from_status(self, status: dict[str, Any]) -> None:
        """Update select from player status."""
        shuffle_mode = str(status.get("playlist shuffle", 0))
        self.attributes[Attributes.CURRENT_OPTION] = self.LMS_TO_OPTION.get(
            shuffle_mode, "Off"
        )
        self.attributes[Attributes.STATE] = States.ON
        self._force_integration_update()

    def _force_integration_update(self) -> None:
        """Force update to integration API."""
        if self._integration_api and hasattr(self._integration_api, "configured_entities"):
            try:
                self._integration_api.configured_entities.update_attributes(
                    self.id, self.attributes
                )
            except Exception as e:
                _LOG.debug("Could not update integration API for %s: %s", self.id, e)
