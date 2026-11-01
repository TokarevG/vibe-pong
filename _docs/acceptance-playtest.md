# Acceptance playtest

Issue: #33 (Acceptance playtest)

## Status

- **PASS (13):** items 1, 3, 4, 5, 6, 7, 8, 9, 10, 12 and 15 were played by the project owner and reported PASS. Items 13 and 14 are command checks run by the agent.
- **FAIL (2):** item 2 (window resize, issue #39) and item 11 (victory sound during an unfinished match, issue #38).

Setup before playing: `pip install -e ".[dev]"`, then run `python -m pong` from the repo root. Back up `~/.config/pong/config.json` (or `$XDG_CONFIG_HOME/pong/config.json`) before item 12, because that check changes it.

## Results

### 1. The game launches with `python -m pong` on Linux

**PASS.** Played by the project owner.

### 2. Initial window is 1000 × 600 and resizes without distorting the 5:3 playfield

**FAIL.** Observed: the window opens at 1000 × 600. Resizing did not work. When a resize started, the window appeared to redraw and shifted slightly down. Tracked in #39.

### 3. Single-player and local two-player modes are playable

**PASS.** Played by the project owner.

### 4. Single-player provides Easy, Medium, and Hard AI difficulties

**PASS.** Played by the project owner.

### 5. Paddle controls match the defaults and can be reconfigured

**PASS.** Played by the project owner.

### 6. A match ends when a player reaches 11 points

**PASS.** Played by the project owner.

### 7. The ball accelerates after paddle hits and stays within the speed limit

**PASS.** Played by the project owner.

### 8. A point resets the ball and requires a new key press before the next rally

**PASS.** Played by the project owner.

### 9. The next serve travels toward the player who conceded the point

**PASS.** Played by the project owner.

### 10. The pause menu and game-over screen provide the specified actions

**PASS.** Played by the project owner.

### 11. Sound effects and audio settings work, and preferences persist across launches

**FAIL.** Observed: the owner heard the sound of the end (victory) screen while alt-tabbing away during a match that was not finished. Tracked in #38. The owner reported the other sound and audio checks as OK.

### 12. Game settings are recovered safely when configuration data is missing or invalid

**PASS.** Played by the project owner.

### 13. Core game rules can be tested without launching Pygame

**PASS.** Evidence: `grep -rn "import pygame" pong/` returns only `pong/__main__.py`, which matches the criterion.

```
pong/__main__.py:14:import pygame
```

### 14. All required automated unit tests pass

**PASS.** Evidence: `.venv/bin/pytest` reports 855 passed, with no failures. The output below is the tail of the run (the run was piped through `tail -25`).

```
pong/tests/test_sound_effects.py .............                           [100%]

============================= 855 passed in 20.73s =============================
```

### 15. No power-ups or other out-of-scope features are present

**PASS.** Played by the project owner.
