"""User settings and the config file location.

This module must not import pygame. It never reads the real environment or
home directory itself; callers pass them in, so the logic can be tested.
"""

import contextlib
import json
import tempfile
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

# Stored names for the enums in the config file.
_MODE_NAMES = {"single_player": Mode.SINGLE_PLAYER, "two_player": Mode.TWO_PLAYER}
_DIFFICULTY_NAMES = {difficulty.value: difficulty for difficulty in Difficulty}
_MODE_TO_NAME = {mode: name for name, mode in _MODE_NAMES.items()}


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


def _parse_mode(value: object) -> Mode | None:
    if isinstance(value, str):
        return _MODE_NAMES.get(value)
    return None


def _parse_difficulty(value: object) -> Difficulty | None:
    if isinstance(value, str):
        return _DIFFICULTY_NAMES.get(value)
    return None


def _parse_volume(value: object) -> int | None:
    # bool is a subclass of int, so it must be excluded explicitly.
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100:
        return value
    return None


def _parse_bindings(value: object) -> dict[str, str] | None:
    """Return the valid action bindings, with defaults for the rest.

    Returns None when ``value`` is not an object at all.
    """
    if not isinstance(value, dict):
        return None
    defaults = _default_bindings()
    bindings: dict[str, str] = {}
    for action, default_key in defaults.items():
        key = value.get(action)
        bindings[action] = key if isinstance(key, str) and key else default_key
    return bindings


def load_settings(path: Path) -> Settings:
    """Load settings from ``path``, falling back to defaults for bad values.

    Never raises for any file content. A missing or unreadable file, invalid
    UTF-8, invalid JSON, or a top-level value that is not an object gives
    ``default_settings()``. Each field is checked on its own, so a bad field
    gets only its own default. If the bindings conflict, all four are reset.
    """
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return default_settings()
    if not isinstance(data, dict):
        return default_settings()

    settings = default_settings()
    mode = _parse_mode(data.get("mode"))
    if mode is not None:
        settings.mode = mode
    difficulty = _parse_difficulty(data.get("difficulty"))
    if difficulty is not None:
        settings.difficulty = difficulty
    audio_enabled = data.get("audio_enabled")
    if isinstance(audio_enabled, bool):
        settings.audio_enabled = audio_enabled
    volume = _parse_volume(data.get("volume"))
    if volume is not None:
        settings.volume = volume
    bindings = _parse_bindings(data.get("bindings"))
    if bindings is not None and not find_binding_conflicts(bindings):
        settings.bindings = bindings
    return settings


def _settings_to_data(settings: Settings) -> dict[str, object]:
    """Return the config-file object for ``settings``.

    Applies the same rules as ``load_settings``. Raises ValueError for any
    field that the loader would reject, so only valid settings reach disk.
    """
    if settings.mode not in _MODE_TO_NAME:
        raise ValueError(f"mode must be a Mode, got {settings.mode!r}")
    if not isinstance(settings.difficulty, Difficulty):
        raise ValueError(  # noqa: TRY004 - the spec requires ValueError
            f"difficulty must be a Difficulty, got {settings.difficulty!r}"
        )
    if not isinstance(settings.audio_enabled, bool):
        raise ValueError(  # noqa: TRY004 - the spec requires ValueError
            f"audio_enabled must be a bool, got {settings.audio_enabled!r}"
        )
    if _parse_volume(settings.volume) is None:
        raise ValueError(
            f"volume must be an int from 0 to 100, got {settings.volume!r}"
        )
    if not isinstance(settings.bindings, Mapping):
        raise ValueError(  # noqa: TRY004 - the spec requires ValueError
            f"bindings must be a mapping, got {settings.bindings!r}"
        )
    for action, key in settings.bindings.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"binding for {action!r} must be a non-empty string")
    conflicts = find_binding_conflicts(settings.bindings)
    if conflicts:
        raise ValueError(f"bindings conflict for actions {conflicts}")
    return {
        "mode": _MODE_TO_NAME[settings.mode],
        "difficulty": settings.difficulty.value,
        "audio_enabled": settings.audio_enabled,
        "volume": settings.volume,
        "bindings": dict(settings.bindings),
    }


def save_settings(path: Path, settings: Settings) -> bool:
    """Write ``settings`` to ``path`` as JSON. Return True on success.

    Raises ValueError, and writes nothing, if any setting is invalid. Creates
    missing parent directories. The file is written to a temporary file in
    the same directory and then moved over ``path``, so a failed write never
    leaves a truncated config. Returns False on OSError instead of raising.
    """
    data = _settings_to_data(settings)
    text = json.dumps(data, indent=2) + "\n"
    tmp: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp = Path(handle.name)
            handle.write(text)
        tmp.replace(path)
    except OSError:
        if tmp is not None:
            with contextlib.suppress(OSError):
                tmp.unlink()
        return False
    return True
