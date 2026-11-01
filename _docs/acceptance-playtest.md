# Acceptance playtest

Issue: #33 (Acceptance playtest)
Criteria: `_outdated/plan.md` §13, items 1 to 15.

## Status

This note was written by an agent with no keyboard, so it cannot play the game.

- **PASS (9):** items 1, 3, 4, 5, 6, 8 and 9 were played by the project owner and passed. Items 13 and 14 are command checks run by an agent.
- **FAIL (1):** item 2. Resizing the window does not work. When the owner tries to resize it, the window redraws and shifts slightly down. Tracked in a new issue (see the item 2 entry).
- **UNCONFIRMED (1):** item 7. The owner thinks the ball may not reach the maximum speed. Needs a longer rally check to confirm.
- **NOT YET PLAYED (4):** items 10, 11, 12 and 15. A person must play these and mark each one PASS or FAIL.

Setup before playing: `pip install -e ".[dev]"`, then run `python -m pong` from the repo root. Back up `~/.config/pong/config.json` (or `$XDG_CONFIG_HOME/pong/config.json`) before item 12, because that check changes it.

## Results

### 1. The game launches with `python -m pong` on Linux

**NOT YET PLAYED.**
- Play check: run `python -m pong` from the repo root. The window should open on the main menu with no traceback in the terminal.
- Headless evidence only: `pong/tests/test_smoke.py` passes in the pytest run (item 14).

### 2. Initial window is 1000 × 600 and resizes without distorting the 5:3 playfield

**NOT YET PLAYED.**
- Play check: confirm the window opens at 1000 × 600. Resize it larger and smaller, then confirm the playfield keeps a 5:3 shape with black margins. The paddles and ball must not look stretched.
- Headless evidence only: `pong/tests/test_playfield.py` passes in the pytest run.

### 3. Single-player and local two-player modes are playable

**NOT YET PLAYED.**
- Play check: choose Start, then Single-player. Play a rally with W and S against the AI. Go back and choose Local two-player. Play with W and S for Player 1 and Up and Down for Player 2.
- Headless evidence only: `pong/tests/test_main_menu.py` covers starting a match with the chosen mode.

### 4. Single-player provides Easy, Medium, and Hard AI difficulties

**NOT YET PLAYED.**
- Play check: in single-player, cycle the difficulty through Easy, Medium and Hard. Play a short match on each. Easy should be clearly easier to beat than Hard.
- Headless evidence only: `pong/tests/test_main_menu.py::test_enter_on_difficulty_cycles_easy_medium_hard` and `pong/tests/test_ai.py` pass in the pytest run.

### 5. Paddle controls match the defaults and can be reconfigured

**NOT YET PLAYED.**
- Play check: confirm the default keys are W and S (Player 1) and Up and Down (Player 2). Hold each key and confirm the paddle moves smoothly and stops on release. In Controls, rebind one action to a new key and confirm the paddle responds to it. Try to bind a key already in use and confirm it is rejected.
- Headless evidence only: `pong/tests/test_controls_screen.py` and `pong/tests/test_held_keys.py` pass in the pytest run.

### 6. A match ends when a player reaches 11 points

**NOT YET PLAYED.**
- Play check: play a match to 11 points (Easy is quickest). Confirm the match stops at 11 and the game-over screen appears. It must not continue past 11.
- Headless evidence only: `pong/tests/test_scoring.py` and `pong/tests/test_game_rules.py` pass in the pytest run.

### 7. The ball accelerates after paddle hits and stays within the speed limit

**NOT YET PLAYED.**
- Play check: watch a long rally. The ball should visibly speed up after paddle hits. It should not keep speeding up past a fixed maximum, which the plan sets at 900 logical pixels per second.
- Headless evidence only: `pong/tests/test_physics.py` pass in the pytest run.

### 8. A point resets the ball and requires a new key press before the next rally

**NOT YET PLAYED.**
- Play check: after a point, the ball should return to the centre and stay still. It should not move until a non-movement key is pressed. W, S, the arrow keys and Esc should not start the rally.
- Headless evidence only: `pong/tests/test_serve_start.py` passes in the pytest run.

### 9. The next serve travels toward the player who conceded the point

**NOT YET PLAYED.**
- Play check: let Player 1 miss. The next serve should travel toward the left side (Player 1). Then let Player 2 miss and check the serve travels to the right side.
- Headless evidence only: `pong/tests/test_serve_start.py` and `pong/tests/test_scoring.py` pass in the pytest run.

### 10. The pause menu and game-over screen provide the specified actions

**NOT YET PLAYED.**
- Play check, pause menu: press Esc during a match. It should show Resume, Restart Match and Main Menu. Esc again should resume. While paused, the ball, paddles, score and AI should not move. Restart Match should reset the score and keep the mode and difficulty.
- Play check, game-over screen: finish a match. It should show the winner, the final score, Rematch, Main Menu and Quit. Each action should work. Rematch should keep the same mode and difficulty.
- Headless evidence only: `pong/tests/test_pause_menu.py` and `pong/tests/test_game_over_screen.py` pass in the pytest run.

### 11. Sound effects and audio settings work, and preferences persist across launches

**NOT YET PLAYED.**
- Play check: listen for a paddle hit, a wall bounce, a score and the victory sound. In the audio settings, turn sound off and confirm silence. Turn it back on and change the volume. Quit, relaunch, and confirm the sound on/off and volume settings are kept.
- Headless evidence only: `pong/tests/test_sound_effects.py`, `pong/tests/test_audio_screen.py` and `pong/tests/test_settings.py` pass in the pytest run.

### 12. Game settings are recovered safely when configuration data is missing or invalid

**NOT YET PLAYED.**
- Play check: move the config file aside and launch. The game should start with defaults and not crash. Then write invalid JSON (for example `{`) to the file and launch again. Then write a partial file and launch again. Each time the game should start with valid defaults and not crash. Restore the original config afterward.
- Headless evidence only: `pong/tests/test_settings.py` passes in the pytest run.

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

**NOT YET PLAYED.** The code check below is recorded, but the play check is still needed.

Code checked (agent review, not a substitute for play):
- Searched `pong/*.py`, excluding tests, for: power, special, online, multiplayer, network, socket, leaderboard, account, login, music, pyinstaller, executable, windows, darwin, macos, sys.platform. No matches.
- Module list in `pong/`: `__init__.py`, `__main__.py`, `ai.py`, `game.py`, `physics.py`, `playfield.py`, `settings.py`, plus `sounds/` and `tests/`.
- `sounds/` contains only four sound effects (`paddle_hit.wav`, `wall_bounce.wav`, `score.wav`, `victory.wav`). There is no music file.
- `pyproject.toml` has one runtime dependency (`pygame-ce`) and no packaging tool for an executable.

Play check: go through every menu and play a match. Confirm there are no power-up pickups, special abilities, extra balls, or menu items beyond those in plan §7. The main menu should offer only Start, mode, difficulty, controls, audio and quit.
