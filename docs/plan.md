# Project Specification: Classic Pong

**Version:** 1.0  
**Status:** Initial specification  
**Language:** Python  
**Rendering:** Pygame  
**Target platform:** Linux

## 1. Project Overview

Develop a classic Pong game in Python using Pygame. The game must support single-player matches against a computer-controlled opponent and local two-player matches on the same computer.

The game should preserve the visual simplicity and core mechanics of classic Pong while providing configurable controls, audio settings, persistent preferences, and a straightforward menu system.

## 2. Runtime and Distribution

- The game must run on Linux.
- Python and required dependencies must be installed separately.
- The project must be launchable from the terminal using `python -m pong`.
- The initial window size must be 1000 × 600 pixels.
- The window must be resizable.
- The game must target 60 frames per second.
- Dependencies and setup instructions must be documented.

## 3. Game Modes

### Single-player
- Player 1 controls the left paddle.
- The computer controls the right paddle.
- The player can choose Easy, Medium, or Hard AI difficulty before starting a match.

### Local two-player
- Both players use the same keyboard.
- Player 1 controls the left paddle.
- Player 2 controls the right paddle.

### Scoring and victory
- A player scores when the opponent fails to return the ball.
- The first player to reach 11 points wins.
- The game must display the current score throughout the match.
- The game must display the winner and final score when the match ends.

## 4. Controls

Default paddle controls:

| Action | Default key |
|---|---|
| Player 1 up | `W` |
| Player 1 down | `S` |
| Player 2 up | `Up Arrow` |
| Player 2 down | `Down Arrow` |
| Pause / resume | `Esc` |

Paddle movement must be smooth and continuous while a movement key is held, stopping when the key is released.

Players must be able to configure key bindings through the settings menu. Bindings must be validated to prevent conflicting assignments.

When the game is waiting for a serve, any key press other than a paddle movement key or a reserved application command must start the rally.

## 5. Gameplay and Physics

### Paddles
- Default paddle speed: 420 logical pixels per second.
- Paddles must remain inside the playfield.
- Both human-controlled paddles must use the same default speed.
- Paddle movement must be time-based rather than dependent on frame count.

### Ball
- The ball must move continuously during a rally.
- The ball must bounce off the top and bottom boundaries.
- The ball must bounce off paddles according to the impact position and paddle movement.
- Hitting near the center of a paddle should produce a relatively straight return.
- Hitting near a paddle's edge should produce a steeper return angle.
- Paddle movement at the moment of impact must influence the return trajectory.
- The ball must accelerate after every paddle hit.
- Ball speed must be capped at a defined maximum so rallies remain playable.

**Initial implementation defaults:** Use a ball speed of 300 logical pixels per second, increase speed by 5% after each paddle hit, and cap the speed at 900 logical pixels per second. These values are initial tuning parameters and may be adjusted during playtesting.

### Serving and rally restarts
- The first rally must wait for player input.
- After a point is scored, the ball must return to the center.
- The ball must remain stationary until a player starts the next rally.
- After a point, the next serve must travel toward the player who conceded that point.
- The score must be updated before the next serve can begin.

### Computer opponent
AI difficulty must affect reaction speed, paddle movement capability, and aiming accuracy. Easy must be the least challenging and Hard the most challenging.

The AI must operate through the same core game rules as a human-controlled paddle. It must not deliberately ignore collisions or violate playfield boundaries.

Exact AI tuning values may be set during implementation and playtesting.

## 6. Visual Design and Window Behavior

The game must use a classic Pong visual style:

- Black background.
- White ball and paddles.
- White score display.
- Dashed vertical center line.
- No decorative backgrounds or power-up effects.

The game must preserve a 5:3 playfield aspect ratio when the window is resized. The playfield must be scaled uniformly to fit the available window space, with black margins where necessary. Game elements must not be stretched disproportionately.

## 7. Menus and Game States

### Main menu
The main menu must provide:
- Start game.
- Select single-player or local two-player mode.
- Select AI difficulty for single-player matches.
- Configure keyboard controls.
- Configure audio.
- Quit game.

### Pause menu
Pressing `Esc` during a match must pause the game and display:
- Resume.
- Restart Match.
- Main Menu.

Pressing `Esc` again must resume the match. The ball, paddles, scoring, and AI must remain frozen while the game is paused.

Restarting a match must reset the score and ball state while preserving the selected game mode and AI difficulty.

### Rally-ready state
When waiting for the initial serve or a subsequent serve, the game must display the current score and stationary ball. The rally must not progress until the required key press.

### Game-over screen
When a player reaches 11 points, display:
- Winner.
- Final score.
- Rematch.
- Main Menu.
- Quit.

Rematch must start a new match using the same mode and AI difficulty.

## 8. Audio

The game must provide short sound effects for:
- Paddle hits.
- Wall bounces.
- Scoring.
- Match victory.

The settings menu must allow the user to enable or disable sound and adjust the volume.

Audio settings must persist between launches. Music is not required.

## 9. Settings Persistence

All game settings must be saved in a local configuration file and restored on the next launch.

Persisted settings must include:
- Keyboard bindings.
- Audio enabled/disabled state.
- Audio volume.
- AI difficulty.
- Other user-adjustable settings introduced by the implementation.

Use a Linux-appropriate configuration location, respecting `XDG_CONFIG_HOME` and defaulting to `~/.config/pong/config.json` when it is not set.

If the configuration file does not exist, create or use default settings. If the file is invalid or incomplete, recover using valid defaults rather than crashing.

## 10. Architecture

The project must use a layered architecture that separates core game rules from Pygame-specific functionality.

Suggested package structure:

```text id="pl8x8x"
pong/
├── __init__.py
├── __main__.py
├── core/
│   ├── game.py
│   ├── physics.py
│   ├── entities.py
│   └── scoring.py
├── ai/
│   └── opponent.py
├── interface/
│   ├── renderer.py
│   ├── input.py
│   ├── menus.py
│   └── audio.py
├── config/
│   └── settings.py
└── tests/
    ├── test_physics.py
    ├── test_scoring.py
    └── test_game_rules.py
```

This is a suggested layout; exact module boundaries may change as implementation progresses.

Core game logic must not depend on Pygame. It must be possible to test scoring, movement, collisions, ball acceleration, and match completion without opening a graphical window.

Pygame-specific rendering, keyboard handling, window management, and audio playback must remain in the interface layer.

## 11. Automated Testing

The project must include automated unit tests for the core game rules. Tests must run without starting Pygame or opening a display window.

At minimum, test:
- Ball collisions with the top and bottom boundaries.
- Paddle collision detection.
- Bounce-angle behavior based on impact position.
- Influence of paddle movement on bounce direction.
- Ball acceleration and maximum speed.
- Paddle boundary constraints.
- Correct score assignment when a player misses.
- Match completion at 11 points.
- Ball reset and serve direction after a point.
- Paused game state preventing game progression.

The project must document how to run the tests.

## 12. Out of Scope

The initial version must not include:
- Power-ups or special abilities.
- Online multiplayer.
- User accounts or leaderboards.
- A standalone packaged executable.
- Music.
- Windows or macOS support.
- A graphical settings editor beyond the in-game menus required by this specification.

## 13. Acceptance Criteria

The project is complete when all of the following are true:

1. The game launches with `python -m pong` on Linux.
2. The initial window is 1000 × 600 pixels and can be resized without distorting the 5:3 playfield.
3. Single-player and local two-player modes are playable.
4. Single-player mode provides Easy, Medium, and Hard AI difficulties.
5. Paddle controls match the defaults and can be reconfigured.
6. A match ends when a player reaches 11 points.
7. The ball accelerates after paddle hits and remains within the defined speed limit.
8. A point resets the ball and requires a new key press before the next rally.
9. The next serve travels toward the player who conceded the point.
10. The pause menu and game-over screen provide the specified actions.
11. Sound effects and audio settings work, and preferences persist across launches.
12. Game settings are recovered safely when configuration data is missing or invalid.
13. Core game rules can be tested without launching Pygame.
14. All required automated unit tests pass.
15. No power-ups or other out-of-scope features are present.
