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

The project is split into two layers:

- **Core layer** (`pong/core/`, `pong/ai/`, `pong/config/`): game rules, physics, scoring, AI decisions, and settings handling. This layer must not import `pygame` or any other windowing or audio module, so it can be tested without a display.
- **Interface layer** (`pong/interface/`): everything that touches Pygame. This includes the window, drawing, keyboard events, menus, and sound playback.

The interface layer calls into the core layer. The core layer never calls back into the interface layer. The game loop reads input, asks the core to advance one time step, and then asks the interface to draw the result.

## 3. Package Structure

```text
pong/
├── __init__.py
├── __main__.py          # Entry point for `python -m pong`
├── core/
│   ├── game.py          # Game state machine: serve, rally, pause, match over
│   ├── physics.py       # Ball movement, wall and paddle collisions, bounce angles, speed
│   ├── entities.py      # Ball and paddle data and their basic updates
│   └── scoring.py       # Score tracking and match-winner rules
├── ai/
│   └── opponent.py      # Computer paddle logic, parameterised by difficulty
├── interface/
│   ├── renderer.py      # Draws the playfield with 5:3 letterboxing
│   ├── input.py         # Maps key events to paddle and command actions
│   ├── menus.py         # Main, pause, settings, and game-over menus
│   └── audio.py         # Loads and plays sound effects, applies volume
├── config/
│   └── settings.py      # Loads, validates, and saves the JSON settings file
└── tests/
    ├── test_physics.py
    ├── test_scoring.py
    └── test_game_rules.py
```

The layout follows the suggestion in [plan.md](plan.md), section 10. Module boundaries may change during implementation.

## 4. Game Loop and Timing

- The loop targets 60 frames per second.
- Each frame computes `dt`, the elapsed time in seconds, and passes it to the core. All movement is `velocity × dt`, so speeds stay the same regardless of frame rate.
- Paused games do not advance the core state, so the ball, paddles, scoring, and AI stay frozen.

## 5. Settings

- The settings file lives at `$XDG_CONFIG_HOME/pong/config.json`, or `~/.config/pong/config.json` when `XDG_CONFIG_HOME` is unset.
- `config/settings.py` reads the file, checks each value against its expected type and range, and substitutes the default for any value that fails. A missing or unreadable file yields the full default set.
- Bindings are validated for conflicts before they are saved.

## 6. Testing Strategy

- Tests live in `pong/tests/` and run with `pytest`.
- Core tests must not import `pygame` and must not open a window. This is enforced by the layer boundary above.
- Interface code is checked by running the game manually; it is not covered by unit tests.

## 7. Quality Tooling

- `ruff` handles linting and formatting.
- `mypy` checks type annotations, primarily in the core layer.
- Both are development dependencies declared in `pyproject.toml`.
