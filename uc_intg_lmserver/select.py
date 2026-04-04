"""
LMS select entities for repeat and shuffle modes.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import Any

from ucapi import StatusCodes
from ucapi.select import Attributes, Commands, States
from ucapi_framework import SelectEntity

from uc_intg_lmserver.config import LMServerConfig
from uc_intg_lmserver.device import LMServerDevice

_LOG = logging.getLogger(__name__)


def _sanitize_name(name: str) -> str:
    sanitized = name.lower()
    sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
    return "_".join(filter(None, sanitized.split("_")))


def create_selects(
    device_config: LMServerConfig, device: LMServerDevice
) -> list[SelectEntity]:
    entities: list[SelectEntity] = []
    for player in device_config.players:
        pid = player.get("player_id", "")
        pname = player.get("name", "Unknown")
        entities.append(LMSRepeatModeSelect(device_config, device, pid, pname))
        entities.append(LMSShuffleModeSelect(device_config, device, pid, pname))
    return entities


REPEAT_OPTIONS = ["Off", "One", "All"]
REPEAT_TO_LMS = {"Off": "0", "One": "1", "All": "2"}
LMS_TO_REPEAT = {0: "Off", 1: "One", 2: "All"}

SHUFFLE_OPTIONS = ["Off", "Songs", "Albums"]
SHUFFLE_TO_LMS = {"Off": "0", "Songs": "1", "Albums": "2"}
LMS_TO_SHUFFLE = {0: "Off", 1: "Songs", 2: "Albums"}


class LMSRepeatModeSelect(SelectEntity):

    def __init__(
        self, device_config: LMServerConfig, device: LMServerDevice,
        player_id: str, player_name: str,
    ) -> None:
        self._device = device
        self._player_id = player_id

        entity_id = f"select.{device_config.identifier}.{_sanitize_name(player_name)}_repeat"

        attributes = {
            Attributes.STATE: States.UNKNOWN,
            Attributes.OPTIONS: [],
            Attributes.CURRENT_OPTION: "",
        }

        super().__init__(
            entity_id,
            f"{player_name} Repeat Mode",
            attributes,
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        ps = self._device.get_player_state(self._player_id)
        repeat_val = ps.get("repeat", 0) if ps else 0
        current = LMS_TO_REPEAT.get(repeat_val, "Off")
        self.update({
            Attributes.STATE: States.ON,
            Attributes.OPTIONS: REPEAT_OPTIONS,
            Attributes.CURRENT_OPTION: current,
        })

    async def _handle_command(
        self, entity: SelectEntity, cmd_id: str, params: dict[str, Any] | None = None
    ) -> StatusCodes:
        params = params or {}
        if cmd_id == Commands.SELECT_OPTION:
            option = params.get("option", "")
            lms_val = REPEAT_TO_LMS.get(option)
            if lms_val is not None:
                if await self._device.cmd_set_repeat(self._player_id, lms_val):
                    return StatusCodes.OK
                return StatusCodes.SERVER_ERROR
            return StatusCodes.BAD_REQUEST
        return StatusCodes.NOT_IMPLEMENTED


class LMSShuffleModeSelect(SelectEntity):

    def __init__(
        self, device_config: LMServerConfig, device: LMServerDevice,
        player_id: str, player_name: str,
    ) -> None:
        self._device = device
        self._player_id = player_id

        entity_id = f"select.{device_config.identifier}.{_sanitize_name(player_name)}_shuffle"

        attributes = {
            Attributes.STATE: States.UNKNOWN,
            Attributes.OPTIONS: [],
            Attributes.CURRENT_OPTION: "",
        }

        super().__init__(
            entity_id,
            f"{player_name} Shuffle Mode",
            attributes,
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        ps = self._device.get_player_state(self._player_id)
        shuffle_val = ps.get("shuffle", 0) if ps else 0
        current = LMS_TO_SHUFFLE.get(shuffle_val, "Off")
        self.update({
            Attributes.STATE: States.ON,
            Attributes.OPTIONS: SHUFFLE_OPTIONS,
            Attributes.CURRENT_OPTION: current,
        })

    async def _handle_command(
        self, entity: SelectEntity, cmd_id: str, params: dict[str, Any] | None = None
    ) -> StatusCodes:
        params = params or {}
        if cmd_id == Commands.SELECT_OPTION:
            option = params.get("option", "")
            lms_val = SHUFFLE_TO_LMS.get(option)
            if lms_val is not None:
                if await self._device.cmd_set_shuffle(self._player_id, lms_val):
                    return StatusCodes.OK
                return StatusCodes.SERVER_ERROR
            return StatusCodes.BAD_REQUEST
        return StatusCodes.NOT_IMPLEMENTED
