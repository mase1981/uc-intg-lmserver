"""
LMS sensor entities.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging

from ucapi.sensor import Attributes, States
from ucapi_framework import SensorEntity

from uc_intg_lmserver.config import LMServerConfig
from uc_intg_lmserver.device import LMServerDevice

_LOG = logging.getLogger(__name__)


def _sanitize_name(name: str) -> str:
    sanitized = name.lower()
    sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
    return "_".join(filter(None, sanitized.split("_")))


def create_sensors(
    device_config: LMServerConfig, device: LMServerDevice
) -> list[SensorEntity]:
    entities: list[SensorEntity] = []
    for player in device_config.players:
        pid = player.get("player_id", "")
        pname = player.get("name", "Unknown")
        entities.append(LMSSourceTypeSensor(device_config, device, pid, pname))
        entities.append(LMSVolumeSensor(device_config, device, pid, pname))
        entities.append(LMSPlaybackStateSensor(device_config, device, pid, pname))
    return entities


class _BaseSensor(SensorEntity):

    def __init__(
        self,
        device_config: LMServerConfig,
        device: LMServerDevice,
        player_id: str,
        player_name: str,
        suffix: str,
        label: str,
    ) -> None:
        self._device = device
        self._player_id = player_id

        attributes = {
            Attributes.STATE: States.UNKNOWN,
            Attributes.VALUE: "",
        }

        entity_id = f"sensor.{device_config.identifier}.{_sanitize_name(player_name)}_{suffix}"

        super().__init__(
            entity_id,
            f"{player_name} {label}",
            [],
            attributes,
            device_class=None,
        )
        self.subscribe_to_device(device)


class LMSSourceTypeSensor(_BaseSensor):

    def __init__(
        self, device_config: LMServerConfig, device: LMServerDevice,
        player_id: str, player_name: str,
    ) -> None:
        super().__init__(device_config, device, player_id, player_name, "source_type", "Source Type")

    async def sync_state(self) -> None:
        ps = self._device.get_player_state(self._player_id)
        if not ps:
            self.update({Attributes.STATE: States.UNKNOWN, Attributes.VALUE: ""})
            return

        is_remote = ps.get("is_remote", False)
        value = "Remote Stream" if is_remote else "Local Library"
        self.update({Attributes.STATE: States.ON, Attributes.VALUE: value})


class LMSVolumeSensor(_BaseSensor):

    def __init__(
        self, device_config: LMServerConfig, device: LMServerDevice,
        player_id: str, player_name: str,
    ) -> None:
        super().__init__(device_config, device, player_id, player_name, "volume", "Volume")

    async def sync_state(self) -> None:
        ps = self._device.get_player_state(self._player_id)
        if not ps:
            self.update({Attributes.STATE: States.UNKNOWN, Attributes.VALUE: ""})
            return

        volume = ps.get("volume", 0)
        self.update({Attributes.STATE: States.ON, Attributes.VALUE: str(volume)})


class LMSPlaybackStateSensor(_BaseSensor):

    def __init__(
        self, device_config: LMServerConfig, device: LMServerDevice,
        player_id: str, player_name: str,
    ) -> None:
        super().__init__(device_config, device, player_id, player_name, "playback_state", "Playback State")

    async def sync_state(self) -> None:
        ps = self._device.get_player_state(self._player_id)
        if not ps:
            self.update({Attributes.STATE: States.UNKNOWN, Attributes.VALUE: ""})
            return

        state_str = ps.get("state", "off")
        state_map = {
            "off": "Off",
            "playing": "Playing",
            "paused": "Paused",
            "on": "Idle",
        }
        value = state_map.get(state_str, "Unknown")
        self.update({Attributes.STATE: States.ON, Attributes.VALUE: value})
