# Task Backlog: Classic Pong

Tasks are listed in suggested order. Requirements are in [plan.md](plan.md) and the structure is in [architecture.md](architecture.md). Where a task needs another task's code, its description says so.

## 1. Set up empty project with a passing test
Goal: Create the package skeleton and a test run that passes with no game code.
Description: Add `pyproject.toml` (setuptools, `requires-python = ">=3.12"`, `pytest` as a dev dependency), an empty `pong/__init__.py`, and `pong/tests/` with one trivial passing test. Confirm that `pytest` passes in a fresh virtualenv. Do not add `pygame` yet.

## 2. Configure ruff and mypy
Goal: Make `ruff` and `mypy` run cleanly on the empty project.
Description: Add `ruff` and `mypy` as dev dependencies and configure them in `pyproject.toml`. Configure `mypy` to check the `pong` package. Both tools must report zero findings on the code from task 1.

## 3. Playfield scaling for the resizable window
Goal: Provide a pure function that gives the scaled playfield rectangle for any window size.
Description: Add `pong/playfield.py`, a core module with no Pygame import, that defines the logical playfield as 1000 × 600 units and returns the uniform scale and centered offset that fit it into a given window while keeping the 5:3 ratio. Black margins are the letterbox area left over. Add the new module to the structure in `architecture.md` §3. Tests cover exact-fit, wider-than-5:3, and taller-than-5:3 windows.

## 4. Paddle movement and boundary clamping
Goal: Move a paddle up or down over time and keep it inside the playfield.
Description: Add a `Paddle` class to `pong/physics.py` with a position, a height, and a `move(direction, dt, playfield_height)` method, where `direction` is -1, 0, or 1. The paddle moves at 420 logical px/s and stops at the top and bottom edges. Tests cover movement per time step, no movement when direction is 0, and clamping at both edges.

## 5. Ball movement and wall bounces
Goal: Advance the ball by velocity × dt and reflect it off the top and bottom edges.
Description: Add a `Ball` class to `pong/physics.py` with a position, a velocity, and a `step(dt, playfield_height)` method. When the ball reaches the top or bottom edge, move it back inside the playfield and reverse its vertical velocity. Tests cover straight-line motion, top and bottom bounces, and confirm that a wall bounce leaves horizontal velocity unchanged.

## 6. Paddle collision detection
Goal: Decide whether the ball overlaps a paddle while moving toward it.
Description: Add `ball_hits_paddle(ball_x, ball_y, ball_radius, paddle_x, paddle_y, paddle_w, paddle_h, ball_vx)` to `pong/physics.py`. It uses plain numbers so it does not depend on the classes in tasks 4 and 5. It returns True only when the ball overlaps the paddle and is moving toward that paddle. Tests cover a direct hit, a miss above and below, and a ball overlapping while moving away.

## 7. Bounce angle from impact position
Goal: Compute the returned ball's velocity from where the paddle was struck.
Description: Add a pure function in `pong/physics.py` that takes a normalized impact offset (-1 at the top edge of the paddle, 0 at the center, 1 at the bottom edge), a ball speed, and a direction of return. It returns the new velocity vector. Hits near the center return nearly horizontally, and hits near an edge return at a steeper angle up to a tunable maximum (start at 60°). Tests cover center returns, edge returns, and symmetry above and below center.

## 8. Paddle motion influence on bounce
Goal: Add the paddle's vertical velocity at impact to the returned ball's vertical velocity.
Description: Extend the bounce function from task 7 so it also takes the paddle's vertical velocity at the moment of impact and adds a tunable fraction of it to the ball's vertical velocity. This is an extension of task 7's function. Tests cover a stationary paddle (no change), a paddle moving down (downward push), a paddle moving up (upward push), and deterministic results for the same inputs.

## 9. Ball speed increase and cap
Goal: Speed the ball up after each paddle hit, up to a fixed maximum.
Description: Add a pure function in `pong/physics.py` that returns the new ball speed after a paddle hit: multiply by 1.05 and cap at 900 logical px/s. The starting serve speed is 300 px/s. Tests cover repeated hits compounding, reaching the cap, and staying at the cap after more hits.

## 10. Point assignment on a miss
Goal: Determine which player scored when the ball leaves the playfield horizontally.
Description: Add a pure function in `pong/game.py` that takes the ball's horizontal center and the playfield width. It returns the player who scored, or None while the ball is still in play. Leaving the left edge scores for Player 2, and leaving the right edge scores for Player 1. Tests cover both edges, the ball inside the field, and the exact boundary.

## 11. Score tracking and match victory at 11
Goal: Track each player's points and report the winner once someone reaches 11.
Description: Add a `Score` class to `pong/game.py` with a method that awards a point to a player and a `winner()` method. `winner()` returns the player who has reached 11 points, or None otherwise. Tests cover increments, no winner at 10 points, and a winner at exactly 11.

## 12. Serve state and serve direction
Goal: Reset the ball to center, keep it still until a rally starts, and serve toward the player who conceded.
Description: Add serve handling to `pong/game.py` that centers the ball with zero velocity after a point and waits in a serving state. When the rally starts, the ball moves toward the player who conceded the point, at the starting speed from task 9. This uses the `Ball` class from task 5. Tests cover the centered and stationary ball, the serve direction for each conceding player, and no movement until the rally starts.

## 13. Match update step
Goal: Advance one time step of a match by combining movement, collisions, scoring, and serving.
Description: Add a `Match` class in `pong/game.py` with an `update(dt, p1_direction, p2_direction)` method. Each call moves both paddles, steps the ball, handles wall and paddle collisions, awards points, and enters the serving state after a point. This is an integration task and depends on tasks 4 through 12. Tests run scripted sequences: a missed ball gives the correct score and a centered serve, and a returned ball speeds up.

## 14. Pause freezes match updates
Goal: Make a paused match ignore all updates until it is resumed.
Description: Add a paused flag and `toggle_pause()` to `Match` in `pong/game.py`. While paused, `update` changes nothing: the ball, paddles, score, and serve state stay the same. This depends on task 13. Tests run many updates while paused and confirm that the state is unchanged, then confirm that play continues after resuming.

## 15. Match restart keeps mode and difficulty
Goal: Reset a match's score and ball while keeping its mode and AI difficulty.
Description: Add a `restart()` method to `Match` that resets the score, paddles, ball, and serve state, and keeps the selected mode and AI difficulty. The pause menu's Restart Match and the game-over Rematch both use it. This depends on task 13. Tests verify a zero score, a centered ball waiting to serve, and unchanged mode and difficulty.

## 16. AI difficulty parameters
Goal: Define the Easy, Medium, and Hard AI tuning values in one table.
Description: Create `pong/ai.py` with a difficulty enum and a table that gives each level a reaction delay, a maximum paddle speed, and an aiming error. Hard is the most capable on every value and Easy the least. The values are starting points that can be tuned during playtesting. Tests check that the ordering holds on each value.

## 17. AI paddle decision logic
Goal: Compute the computer paddle's movement direction from the ball state and difficulty.
Description: Add an AI controller class to `pong/ai.py` that returns -1, 0, or 1 for each update. It acts on the ball's position only after the reaction delay for its difficulty, moves no faster than the maximum speed, and applies the aiming error to its target. It depends on the difficulty table from task 16. Tests run a fixed simulation to confirm that Hard tracks a ball better than Easy and that the output is always -1, 0, or 1.

## 18. Default settings and config path
Goal: Define the default settings and find the config file location.
Description: In `pong/settings.py`, define the default values for key bindings, audio enabled, volume, and AI difficulty. Add a function that returns the config path from `XDG_CONFIG_HOME`, falling back to `~/.config/pong/config.json`, using `pathlib`. Tests pass in the environment and home directory as arguments instead of reading the real ones.

## 19. Load settings with validation and fallback
Goal: Load the config file and replace any missing or invalid value with its default.
Description: Add `load_settings(path)` to `pong/settings.py`. It returns the full default set when the file is missing, unreadable, or not valid JSON. It replaces each field with the wrong type or an out-of-range value with that field's default, and it never raises. Tests cover a missing file, corrupt JSON, wrong types, an out-of-range volume, and a partly valid file.

## 20. Save settings to the config file
Goal: Write settings to disk so they are restored on the next launch.
Description: Add `save_settings(path, settings)` to `pong/settings.py`, which creates the parent directory if needed and writes JSON. It must write only values that are valid, using the same field definitions as task 19. Tests save and then load, checking that the result is equal, and check that a missing directory is created.

## 21. Key binding conflict validation
Goal: Reject key binding assignments that clash with another action.
Description: Add a function to `pong/settings.py` that checks a proposed set of bindings for five actions: Player 1 up and down, Player 2 up and down, and pause. Each key may be used at most once, and no action may use the reserved Esc key. The function returns the conflicting actions, or an empty result when the set is valid. Tests cover duplicate keys, a valid set, and Esc used as a paddle key.

## 22. Pygame window and 60 FPS loop
Goal: Open a resizable 1000 × 600 window and run a 60 FPS loop that quits cleanly.
Description: Add `pygame-ce` as a dependency and create `pong/__main__.py`. It opens a resizable 1000 × 600 window, runs a loop capped at 60 FPS that computes `dt` in seconds, and exits when the window is closed. `__main__.py` is the only module that imports `pygame`. Check it manually with `python -m pong`, since this module is not unit tested.

## 23. Render the playfield
Goal: Draw the classic Pong visuals inside the 5:3 playfield at any window size.
Description: In `pong/__main__.py`, draw a black background, white paddles and ball, a dashed center line, and the score. Use the scale and offset from task 3 to position everything, so the game is never stretched. Check it manually by resizing the window to a wide, a tall, and a 5:3 size.

## 24. Held-key paddle control
Goal: Move each paddle smoothly while its bound movement key is held.
Description: In `pong/__main__.py`, read the held-key state each frame, map it through the configured bindings to -1, 0, or 1 for each paddle, and pass the directions to `Match.update`. The defaults are W and S for Player 1 and the arrow keys for Player 2. Check manually that paddles stop when the key is released.

## 25. Start rally on key press during serve
Goal: Start the next rally with any key that is not a paddle key or Esc.
Description: In `pong/__main__.py`, while the match is waiting to serve, any key press that is not a bound paddle key or Esc calls the match's rally start. This uses the serve state from task 12. Check manually in single-player and two-player modes.

## 26. Pause menu
Goal: Show Resume, Restart Match, and Main Menu when Esc is pressed during a match.
Description: Pressing Esc during a match pauses it through task 14 and shows a menu with those three options. Esc again resumes play. Restart Match uses task 15, and Main Menu returns to the main menu from task 27. Menu items are selected with the keyboard.

## 27. Main menu
Goal: Provide the main menu with start, mode, difficulty, controls, audio, and quit.
Description: Build the main menu in `pong/__main__.py` with the six items listed in `plan.md` §7. Mode and difficulty changes update the settings and are saved through task 20. The Controls and Audio items open screens from tasks 28 and 29, and they can be stubs until those tasks are done.

## 28. Key binding settings screen
Goal: Let players rebind paddle keys in the game, with conflicts rejected.
Description: Add a Controls screen to `pong/__main__.py` that lists the five bindable actions. Selecting an action waits for the next key press, checks it with task 21, and shows a message if the key conflicts. A valid binding is saved through task 20.

## 29. Audio settings screen
Goal: Let players turn sound on or off and adjust its volume, with the choice saved.
Description: Add an Audio screen to `pong/__main__.py` with an on/off toggle and a volume control in steps from 0 to 100. Changes are saved through task 20 so they persist across launches. Check manually that the saved values are restored after a restart.

## 30. Sound effects
Goal: Play short sounds for paddle hits, wall bounces, scoring, and match victory.
Description: Add four short sound files, either bundled under a license that allows reuse or generated by a script in the repository. Load them with `pygame.mixer` in `pong/__main__.py` and play each one when the matching event happens in `Match.update`. Playback must respect the enabled flag and volume, and the game must keep running with no error if no audio device is available.

## 31. Game-over screen
Goal: Show the winner, final score, and Rematch, Main Menu, and Quit options when a match ends.
Description: When `Score.winner()` reports a winner from task 11, show the winner and the final score in `pong/__main__.py`. Rematch calls `Match.restart()` from task 15, Main Menu returns to the main menu, and Quit exits the game. The victory sound from task 30 plays when this screen appears.

## 32. Setup and run documentation
Goal: Document how to install, run, and test the game on Linux.
Description: Write `README.md` covering the Python version, creating a virtualenv, installing the dependencies, launching with `python -m pong`, and running `pytest`. Follow those steps in a clean virtualenv to confirm they work. Include the settings file location from task 18.

## 33. Acceptance playtest
Goal: Check the finished game against the acceptance criteria in `plan.md` §13.
Description: Go through all fifteen items in `plan.md` §13 by playing the game and running the test suite. Record each item as pass or fail in a short note in `docs/`. File a new task for each failure rather than fixing it in this task.
