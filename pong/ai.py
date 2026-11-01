"""AI opponent tuning for the single-player game.

This module has no pygame dependency, so the tuning can be tested without a window.
The values here are starting points and may change during playtesting.
"""

import random
from dataclasses import dataclass
from enum import Enum


class Difficulty(Enum):
    """How capable the AI opponent is. ``EASY`` is the least capable."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class AISettings:
    """Tuning for one difficulty level.

    Attributes:
        reaction_delay: seconds between the ball changing direction and the AI
            reacting to it.
        max_speed: fastest the AI paddle can move, in px/s.
        aim_error: how far off centre the AI aims, in px.
    """

    reaction_delay: float
    max_speed: float
    aim_error: float


AI_SETTINGS: dict[Difficulty, AISettings] = {
    Difficulty.EASY: AISettings(reaction_delay=0.40, max_speed=240.0, aim_error=60.0),
    Difficulty.MEDIUM: AISettings(reaction_delay=0.25, max_speed=330.0, aim_error=30.0),
    Difficulty.HARD: AISettings(reaction_delay=0.10, max_speed=420.0, aim_error=10.0),
}
"""Tuning values for each difficulty. This is the only place they are defined."""

DEAD_ZONE = 4.0
"""Distance in px within which the AI paddle holds still, so it does not jitter."""

_LOOK_TOLERANCE = 1e-9
"""Seconds of slack when checking the reaction delay.

Summing a frame step such as 1/60 s six times gives 0.09999999999999999, not 0.1.
Without this slack a look would slip one frame late.
"""


class AIController:
    """Decides which way the computer paddle should move.

    The controller takes a look at the ball's y position on its first ``update``
    and then again each ``reaction_delay`` seconds. Between looks it keeps aiming
    at the position it last saw. Each look adds a random aim error drawn from
    ``rng``. It returns a direction only; how fast the paddle moves is up to the
    caller, using ``max_speed``.
    """

    def __init__(self, difficulty: Difficulty, rng: random.Random) -> None:
        self._settings = AI_SETTINGS[difficulty]
        self._rng = rng
        self._target: float | None = None
        self._since_look = 0.0

    @property
    def max_speed(self) -> float:
        """Fastest the AI paddle can move, in px/s, for this difficulty."""
        return self._settings.max_speed

    def update(self, dt: float, ball_y: float, paddle_center_y: float) -> int:
        """Return -1 to move up, 1 to move down, or 0 to hold still.

        Args:
            dt: seconds since the previous call. 0 means no time has passed.
            ball_y: the ball's current y position, in px.
            paddle_center_y: the AI paddle's current centre y, in px.
        """
        self._since_look += dt
        if self._target is None or (
            dt > 0
            and self._since_look >= self._settings.reaction_delay - _LOOK_TOLERANCE
        ):
            aim_error = self._settings.aim_error
            self._target = ball_y + self._rng.uniform(-aim_error, aim_error)
            self._since_look = 0.0
        target = self._target

        if target - paddle_center_y > DEAD_ZONE:
            return 1
        if paddle_center_y - target > DEAD_ZONE:
            return -1
        return 0
