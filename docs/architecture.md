# Architecture: Classic Pong

This document describes the technical architecture and the technology stack for the project. Requirements are defined in [plan.md](plan.md).

## 1. Technology Stack

| Area | Choice |
|---|---|
| Python | 3.13 (`requires-python = ">=3.12"`) |
| Rendering and input | `pygame-ce` (2.5.8 or later) |
| Tests | `pytest` |
| Settings | Standard library (`json`, `pathlib`) with hand-written validation |
| Packaging | `pyproject.toml` with setuptools, installed with `pip` |
| Linting and formatting | `ruff` |
| Type checking | `mypy` |

Dependencies are installed separately. The `pygame-ce` package is imported under the `pygame` name.

## 2. Layers

The project uses a flat package with one level of modules and no nested layer directories. Game rules are kept separate from Pygame by convention:

- **Core modules** (`game.py`, `physics.py`, `ai.py`, `settings.py`): game rules, physics, scoring, AI decisions, and settings handling. These must not import `pygame`, so they can be tested without a display.
- **Pygame module** (`__main__.py`): the window, drawing, keyboard events, menus, sound playback, and the main loop. It is the only module that imports `pygame`.

The Pygame module calls into the core modules. The core modules never import the Pygame module. The game loop reads input, asks the core to advance one time step, and then draws the result.

## 3. Package Structure

```text
pong/
├── __init__.py
├── __main__.py     # Pygame loop, input, drawing, menus, sound (only module importing pygame)
├── game.py         # Match state: serve, rally, pause, game over (no Pygame)
├── physics.py      # Ball movement, collisions, bounce angles, speed (no Pygame)
├── ai.py           # Computer paddle, parameterised by difficulty (no Pygame)
├── settings.py     # Load, validate, and save the JSON settings file (no Pygame)
└── tests/
    ├── test_physics.py
    ├── test_scoring.py
    └── test_game_rules.py
```

The layout follows the suggestion in [plan.md](plan.md), section 10. Module boundaries may change during implementation, but the rule that core modules do not import Pygame must hold.

## 4. Game Loop and Timing

- The loop targets 60 frames per second.
- Each frame computes `dt`, the elapsed time in seconds, and passes it to the core. All movement is `velocity × dt`, so speeds stay the same regardless of frame rate.
- Paused games do not advance the core state, so the ball, paddles, scoring, and AI stay frozen.

## 5. Settings

- The settings file lives at `$XDG_CONFIG_HOME/pong/config.json`, or `~/.config/pong/config.json` when `XDG_CONFIG_HOME` is unset.
- `settings.py` reads the file, checks each value against its expected type and range, and substitutes the default for any value that fails. A missing or unreadable file yields the full default set.
- Bindings are validated for conflicts before they are saved.

## 6. Testing Strategy

- Tests live in `pong/tests/` and run with `pytest`.
- Core tests must not import `pygame` and must not open a window. This holds because no core module imports `pygame`.
- `__main__.py` is checked by running the game manually; it is not covered by unit tests.

## 7. Quality Tooling

- `ruff` handles linting and formatting.
- `mypy` checks type annotations, primarily in the core layer.
- Both are development dependencies declared in `pyproject.toml`.
