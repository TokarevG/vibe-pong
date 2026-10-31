# Agent Instructions

Commands

- `pip install -e ".[dev]"` - install the package and dev dependencies
- `pytest` - the whole suite
- `pytest pong/tests/test_smoke.py` - one test file
- `ruff format && ruff check --fix` - format and lint the code, applying safe fixes automatically (run before every commit)

Rules

- Dependencies are added in `pyproject.toml`. Do not add one without
  asking
- Format and lint the code with `ruff format && ruff check --fix` before every commit
- Commit regularly