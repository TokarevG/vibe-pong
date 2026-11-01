"""User settings and the config file location.

This module must not import pygame. It never reads the real environment or
home directory itself; callers pass them in, so the logic can be tested.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pong.ai import Difficulty
from pong.game import Mode

CONFIG_DIR_NAME = "pong"
CONFIG_FILE_NAME = "config.json"


def _default_bindings() -> dict[str, str]:
    return {
        "p1_up": "w",
        "p1_down": "s",
        "p2_up": "up",
        "p2_down": "down",
    }


@dataclass
class Settings:
    """All user-adjustable settings with their starting values."""

    mode: Mode = Mode.SINGLE_PLAYER
    difficulty: Difficulty = Difficulty.MEDIUM
    audio_enabled: bool = True
    # Integer from 0 to 100.
    volume: int = 80
    # Action name to Pygame key name, e.g. "w", "up", "escape".
    bindings: dict[str, str] = field(default_factory=_default_bindings)


def default_settings() -> Settings:
    """Return a new Settings with the default values on every call."""
    return Settings()


def config_path(environ: Mapping[str, str], home: Path) -> Path:
    """Return the path of the config file.

    Uses ``$XDG_CONFIG_HOME/pong/config.json`` when ``XDG_CONFIG_HOME`` is a
    non-empty absolute path, otherwise ``<home>/.config/pong/config.json``.
    """
    xdg = environ.get("XDG_CONFIG_HOME", "")
    if xdg and Path(xdg).is_absolute():
        base = Path(xdg)
    else:
        base = home / ".config"
    return base / CONFIG_DIR_NAME / CONFIG_FILE_NAME
