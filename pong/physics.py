"""Core game objects and their movement rules.

This module must not import pygame, so the rules can be tested without a window.
Coordinates are logical pixels with the y axis pointing down: a larger ``y`` is
lower on screen.
"""

import math


def _travel(velocity: float, dt: float) -> float:
    """Distance covered at ``velocity`` for ``dt``, with no travel at zero velocity.

    The zero check keeps ``0 * inf`` from producing ``nan``.
    """
    return 0.0 if velocity == 0 else velocity * dt


class Paddle:
    """A vertical paddle whose ``y`` is kept inside the playfield.

    ``x`` is the left edge and ``y`` is the top edge. After each ``move``,
    ``velocity`` holds the vertical velocity actually applied, in px/s.
    """

    def __init__(
        self,
        x: float,
        y: float,
        width: float = 12,
        height: float = 100,
        speed: float = 420.0,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.height = float(height)
        self.speed = float(speed)
        self.velocity = 0.0

    def move(self, direction: int, dt: float, playfield_height: float) -> None:
        """Move up (-1), stay (0) or move down (1) for ``dt`` seconds.

        The paddle moves ``direction * speed * dt`` pixels and is clamped so that
        ``0 <= y`` and ``y + height <= playfield_height``.

        Raises:
            ValueError: if ``direction`` is not -1, 0 or 1, or ``dt`` is negative.
        """
        if direction not in (-1, 0, 1):
            raise ValueError(f"direction must be -1, 0 or 1, got {direction}")
        if dt < 0:
            raise ValueError(f"dt must not be negative, got {dt}")

        if direction == 0:
            self.velocity = 0.0
            return

        old_y = self.y
        target_y = old_y + direction * self.speed * dt
        max_y = playfield_height - self.height
        self.y = min(max(target_y, 0.0), max_y)

        self.velocity = (self.y - old_y) / dt if dt > 0 else 0.0


class Ball:
    """A ball whose ``x`` and ``y`` are its centre, bouncing off the top and bottom.

    ``vx`` and ``vy`` are in px/s. The ball's centre stays within
    ``[radius, playfield_height - radius]`` on the y axis.
    """

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        radius: float = 8,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.radius = float(radius)

    def step(self, dt: float, playfield_height: float) -> bool:
        """Advance the ball by ``dt`` seconds and bounce it off the top and bottom walls.

        The ball moves by ``(vx * dt, vy * dt)``. Each time the centre goes past a
        wall it is reflected back across that wall and ``vy`` flips sign. ``vx`` is
        never changed by a bounce. Returns ``True`` if at least one wall bounce
        happened during this step, otherwise ``False``.

        The reflections are computed in constant time, so a very large ``dt`` is
        cheap. An infinite travel (``dt`` infinite with nonzero velocity, or an
        overflow) has no finite resting point, so the centre is put on the wall it
        was heading for.

        Raises:
            ValueError: if ``dt`` is negative or ``nan``, or the playfield is not a
                finite height greater than the ball's diameter
                (``playfield_height > 2 * radius``).
        """
        if math.isnan(dt):
            raise ValueError("dt must be a number, got nan")
        if dt < 0:
            raise ValueError(f"dt must not be negative, got {dt}")
        if not math.isfinite(playfield_height) or playfield_height <= 2 * self.radius:
            raise ValueError(
                f"playfield height must be finite and greater than 2 * radius, "
                f"got {playfield_height} for radius {self.radius}"
            )

        self.x += _travel(self.vx, dt)

        top = self.radius
        bottom = playfield_height - self.radius
        span = bottom - top
        travel = _travel(self.vy, dt)
        y_raw = self.y + travel

        # Position relative to the top wall, before any reflection.
        offset = y_raw - top
        ratio = offset / span if math.isfinite(y_raw) else math.inf
        if not math.isfinite(ratio):
            self.y = bottom if travel > 0 else top
            return True

        # Each reflection is a fold back into [top, bottom]. Folding the unbounded
        # line with period 2 * span gives the same point as reflecting one wall
        # at a time, and the number of folds sets the sign of vy.
        if offset >= 0:
            bounces = max(0, math.ceil(ratio) - 1)
        else:
            bounces = math.ceil(-ratio)

        phase = offset % (2 * span)
        if phase > span:
            phase = 2 * span - phase
        self.y = min(max(top + phase, top), bottom)

        if bounces % 2 == 1:
            self.vy = -self.vy
        return bounces > 0


def ball_hits_paddle(
    ball_x: float,
    ball_y: float,
    ball_radius: float,
    paddle_x: float,
    paddle_y: float,
    paddle_w: float,
    paddle_h: float,
    ball_vx: float,
) -> bool:
    """Return ``True`` if the ball touches the paddle while moving toward it.

    ``(paddle_x, paddle_y)`` is the paddle's top-left corner. The paddle is on the
    left when its centre ``x`` is less than ``ball_x``, otherwise on the right. A
    hit needs ``ball_vx < 0`` for a paddle on the left and ``ball_vx > 0`` for a
    paddle on the right, so ``ball_vx == 0`` is never a hit.

    The ball overlaps the paddle when the distance from the ball centre to the
    nearest point of the paddle rectangle is at most ``ball_radius``. A distance
    exactly equal to the radius counts as a hit.

    This function does not change any state.
    """
    paddle_on_left = paddle_x + paddle_w / 2 < ball_x
    if paddle_on_left:
        if not ball_vx < 0:
            return False
    elif not ball_vx > 0:
        return False

    nearest_x = min(max(ball_x, paddle_x), paddle_x + paddle_w)
    nearest_y = min(max(ball_y, paddle_y), paddle_y + paddle_h)
    dx = ball_x - nearest_x
    dy = ball_y - nearest_y
    return dx * dx + dy * dy <= ball_radius * ball_radius
