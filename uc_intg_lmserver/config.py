"""
Configuration for LMS integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from uc_intg_lmserver.const import DEFAULT_PORT


@dataclass
class LMServerConfig:
    identifier: str
    name: str
    host: str
    port: int = DEFAULT_PORT
    players: list[dict] = field(default_factory=list)
    favorites: list[dict] = field(default_factory=list)
