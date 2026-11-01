# Pong

Classic Pong for one or two players, built in Python with Pygame.

## Requirements

- Linux
- Python 3.12 or later (matches `requires-python` in `pyproject.toml`)

## Setup

Run these commands from the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the game in editable mode, along with the development tools (pytest, ruff, mypy).

## Run

With the virtualenv active:

```bash
python -m pong
```

This opens the game window at the main menu.

## Test

Run the whole test suite:

```bash
pytest
```

Run one test file:

```bash
pytest pong/tests/test_smoke.py
```

## Development

Format and lint the code before every commit:

```bash
ruff format && ruff check --fix
```

Run the type check:

```bash
mypy
```

## Settings

Settings are stored in a JSON file:

- `$XDG_CONFIG_HOME/pong/config.json` when `XDG_CONFIG_HOME` is set to an absolute path
- `~/.config/pong/config.json` otherwise

The game reads this file at start-up. It is written when you change a setting in the menus. If the file is missing or invalid, the game uses the default settings.
