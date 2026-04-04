"""
LMS integration driver using ucapi-framework.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging

from ucapi_framework import BaseIntegrationDriver

from uc_intg_lmserver.config import LMServerConfig
from uc_intg_lmserver.device import LMServerDevice
from uc_intg_lmserver.media_player import create_media_players
from uc_intg_lmserver.remote import create_remotes
from uc_intg_lmserver.select import create_selects
from uc_intg_lmserver.sensor import create_sensors

_LOG = logging.getLogger(__name__)


class LMServerDriver(BaseIntegrationDriver[LMServerDevice, LMServerConfig]):

    def __init__(self) -> None:
        super().__init__(
            device_class=LMServerDevice,
            entity_classes=[
                lambda cfg, dev: create_media_players(cfg, dev),
                lambda cfg, dev: create_remotes(cfg, dev),
                lambda cfg, dev: create_selects(cfg, dev),
                lambda cfg, dev: create_sensors(cfg, dev),
            ],
            driver_id="lmserver",
            require_connection_before_registry=False,
        )
