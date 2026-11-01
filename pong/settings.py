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

# The four bindable actions. Pause is fixed to Esc, so it is not bindable.
BINDABLE_ACTIONS = frozenset({"p1_up", "p1_down", "p2_up", "p2_down"})
# Esc is reserved for pause and may not be bound to any action.
RESERVED_KEY = "escape"


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


def find_binding_conflicts(bindings: Mapping[str, str]) -> list[str]:
    """Return the sorted action names whose binding is invalid.

    An action is listed when it shares its key with another action, or when
    it is bound to the reserved Esc key. Key names are compared ignoring case.
    Raises ValueError unless ``bindings`` has exactly the four paddle actions.
    """
    if set(bindings) != BINDABLE_ACTIONS:
        raise ValueError(
            f"bindings must have exactly the actions {sorted(BINDABLE_ACTIONS)}, "
            f"got {sorted(bindings)}"
        )
    keys = {action: key.lower() for action, key in bindings.items()}
    conflicts: set[str] = set()
    for action, key in keys.items():
        if key == RESERVED_KEY:
            conflicts.add(action)
        if any(
            other != action and other_key == key for other, other_key in keys.items()
        ):
            conflicts.add(action)
    return sorted(conflicts)
