"""
LMS Sensor entities for player status.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import logging
from typing import Any

from ucapi.sensor import Attributes, DeviceClasses, Sensor, States

_LOG = logging.getLogger(__name__)


class LMSSourceTypeSensor(Sensor):
    """Sensor showing whether current source is local library or remote stream."""

    def __init__(self, player_id: str, player_name: str):
        self._player_id = player_id
        self._player_name = player_name
        self._integration_api = None

        sanitized = self._sanitize_name(player_name)
        entity_id = f"sensor.{sanitized}_source_type"

        super().__init__(
            entity_id,
            f"{player_name} Source Type",
            [],
            {
                Attributes.STATE: States.UNAVAILABLE,
                Attributes.VALUE: "Unknown",
            },
            device_class=DeviceClasses.CUSTOM,
            options={"custom_unit": ""},
        )

        _LOG.info("Created source type sensor: %s", entity_id)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert player name to valid entity ID component."""
        sanitized = name.lower()
        sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
        return "_".join(filter(None, sanitized.split("_")))

    def update_from_status(self, status: dict[str, Any]) -> None:
        """Update sensor from player status."""
        is_remote = False

        if "remoteMeta" in status:
            is_remote = True
        elif "playlist_loop" in status and status["playlist_loop"]:
            is_remote = status["playlist_loop"][0].get("remote", 0) == 1

        self.attributes[Attributes.STATE] = States.ON
        self.attributes[Attributes.VALUE] = "Remote Stream" if is_remote else "Local Library"

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


class LMSVolumeSensor(Sensor):
    """Sensor showing current volume level."""

    def __init__(self, player_id: str, player_name: str):
        self._player_id = player_id
        self._player_name = player_name
        self._integration_api = None

        sanitized = self._sanitize_name(player_name)
        entity_id = f"sensor.{sanitized}_volume"

        super().__init__(
            entity_id,
            f"{player_name} Volume",
            [],
            {
                Attributes.STATE: States.UNAVAILABLE,
                Attributes.VALUE: 0,
                Attributes.UNIT: "%",
            },
            device_class=DeviceClasses.CUSTOM,
            options={"native_unit": "%", "decimals": 0},
        )

        _LOG.info("Created volume sensor: %s", entity_id)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert player name to valid entity ID component."""
        sanitized = name.lower()
        sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
        return "_".join(filter(None, sanitized.split("_")))

    def update_from_status(self, status: dict[str, Any]) -> None:
        """Update sensor from player status."""
        volume = status.get("mixer volume", 0)
        self.attributes[Attributes.STATE] = States.ON
        self.attributes[Attributes.VALUE] = volume

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


class LMSPlaybackStateSensor(Sensor):
    """Sensor showing current playback state."""

    def __init__(self, player_id: str, player_name: str):
        self._player_id = player_id
        self._player_name = player_name
        self._integration_api = None

        sanitized = self._sanitize_name(player_name)
        entity_id = f"sensor.{sanitized}_playback_state"

        super().__init__(
            entity_id,
            f"{player_name} Playback State",
            [],
            {
                Attributes.STATE: States.UNAVAILABLE,
                Attributes.VALUE: "Unknown",
            },
            device_class=DeviceClasses.CUSTOM,
            options={"custom_unit": ""},
        )

        _LOG.info("Created playback state sensor: %s", entity_id)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert player name to valid entity ID component."""
        sanitized = name.lower()
        sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
        return "_".join(filter(None, sanitized.split("_")))

    def update_from_status(self, status: dict[str, Any]) -> None:
        """Update sensor from player status."""
        mode = status.get("mode", "stop")
        power = status.get("power", 0)

        if power == 0:
            state_value = "Off"
        elif mode == "play":
            state_value = "Playing"
        elif mode == "pause":
            state_value = "Paused"
        elif mode == "stop":
            state_value = "Stopped"
        else:
            state_value = "Idle"

        self.attributes[Attributes.STATE] = States.ON
        self.attributes[Attributes.VALUE] = state_value

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
