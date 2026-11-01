"""AI opponent tuning for the single-player game.

This module has no pygame dependency, so the tuning can be tested without a window.
The values here are starting points and may change during playtesting.
"""

import math
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

AIM_SMOOTHING_TIME = 10.0
"""Time constant, in seconds, for the aim error to move toward each new draw.

Each look draws a new aim error, and the controller eases toward it over this time
rather than jumping. A new draw is never reached in one step, so the paddle does not
chase every look across the dead zone and jitter.
"""


def predict_contact_y(
    ball_x: float,
    ball_y: float,
    ball_vx: float,
    ball_vy: float,
    ball_radius: float,
    paddle_x: float,
    playfield_height: float,
) -> float | None:
    """Return the ball's y where its centre reaches a paddle's face, or ``None``.

    The paddle is on the right, with its left edge at ``paddle_x``. The ball's
    centre makes contact when its x is ``paddle_x - ball_radius``. The prediction
    assumes ``ball_vx`` and ``ball_vy`` stay as they are, apart from bounces off
    the top and bottom walls. Each wall bounce reflects the centre across the wall
    and flips ``vy``, exactly as ``pong.physics.Ball.step`` does, so the unfolded
    y is folded back into ``[radius, playfield_height - radius]``.

    Returns ``None`` when no prediction is made: the ball is not moving toward the
    paddle (``ball_vx <= 0``), it is already at or past the contact x, or the
    result is not finite.
    """
    if ball_vx <= 0:
        return None
    contact_x = paddle_x - ball_radius
    if ball_x >= contact_x:
        return None
    time_to_contact = (contact_x - ball_x) / ball_vx
    unfolded_y = ball_y + ball_vy * time_to_contact
    if not math.isfinite(unfolded_y):
        return None

    top = ball_radius
    span = playfield_height - 2 * ball_radius
    # Position from the top wall, folded with period 2 * span. The second half of
    # each period is the reflected return trip.
    offset = (unfolded_y - top) % (2 * span)
    if offset > span:
        offset = 2 * span - offset
    return top + offset


class AIController:
    """Decides which way the computer paddle should move.

    The controller takes a look on its first ``update`` and then again each
    ``reaction_delay`` seconds. At each look it fixes a base y and draws a new
    aim error from ``rng``, within ``aim_error``. Between looks it keeps the base
    it last saw.

    The base depends on the difficulty. Easy and Medium use the ball's current y.
    Hard uses the y where the ball will reach the paddle's face, from
    ``predict_contact_y``, when the ball is moving toward the paddle. Otherwise
    Hard uses the ball's current y, as the others do.

    The aim error does not jump to each new draw. It moves toward the draw with the
    time constant ``AIM_SMOOTHING_TIME``, so the target drifts instead of jumping,
    and the paddle does not reverse on every look. The first look sets the error
    straight to its draw.

    The controller returns a direction only; how fast the paddle moves is up to the
    caller, using ``max_speed``.
    """

    def __init__(self, difficulty: Difficulty, rng: random.Random) -> None:
        self._difficulty = difficulty
        self._settings = AI_SETTINGS[difficulty]
        self._rng = rng
        self._has_looked = False
        self._base = 0.0
        self._goal_error = 0.0
        self._error = 0.0
        self._since_look = 0.0

    @property
    def max_speed(self) -> float:
        """Fastest the AI paddle can move, in px/s, for this difficulty."""
        return self._settings.max_speed

    @property
    def target(self) -> float | None:
        """The y the controller is aiming at now, or ``None`` before the first look."""
        if not self._has_looked:
            return None
        return self._base + self._error

    def update(
        self,
        dt: float,
        ball_x: float,
        ball_y: float,
        ball_vx: float,
        ball_vy: float,
        ball_radius: float,
        paddle_x: float,
        paddle_center_y: float,
        playfield_height: float,
    ) -> int:
        """Return -1 to move up, 1 to move down, or 0 to hold still.

        Args:
            dt: seconds since the previous call. 0 means no time has passed.
            ball_x, ball_y: the ball's centre, in px.
            ball_vx, ball_vy: the ball's velocity, in px/s. Positive ``ball_vx``
                means the ball is moving toward the AI paddle on the right.
            ball_radius: the ball's radius, in px.
            paddle_x: the AI paddle's left edge, in px.
            paddle_center_y: the AI paddle's current centre y, in px.
            playfield_height: the playfield's height, in px.

        The ball inputs are read only at a look. Between looks the base does not
        change.
        """
        self._since_look += dt
        first_look = not self._has_looked
        if first_look or (
            dt > 0
            and self._since_look >= self._settings.reaction_delay - _LOOK_TOLERANCE
        ):
            base = ball_y
            if self._difficulty is Difficulty.HARD:
                predicted = predict_contact_y(
                    ball_x,
                    ball_y,
                    ball_vx,
                    ball_vy,
                    ball_radius,
                    paddle_x,
                    playfield_height,
                )
                if predicted is not None:
                    base = predicted
            self._base = base
            self._has_looked = True
            aim_error = self._settings.aim_error
            self._goal_error = self._rng.uniform(-aim_error, aim_error)
            if first_look:
                self._error = self._goal_error
            self._since_look = 0.0

        if dt > 0:
            pull = 1 - math.exp(-dt / AIM_SMOOTHING_TIME)
            self._error += (self._goal_error - self._error) * pull

        target = self._base + self._error
        if target - paddle_center_y > DEAD_ZONE:
            return 1
        if paddle_center_y - target > DEAD_ZONE:
            return -1
        return 0
